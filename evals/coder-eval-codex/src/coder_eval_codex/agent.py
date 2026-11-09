"""The `codex-daily-driver` agent kind: `coder_eval`'s Codex agent, retagged.

Unlike the Omp arm, this is not a harness driver. `coder_eval` 0.11.6 already
ships a `codex` kind that drives the Codex SDK, links a `plugins:` root's skills
into `<cwd>/.agents/skills/`, and records command telemetry in the vocabulary
the criteria are written in. All of that is inherited unchanged. What is added
is two corrections the built-in does not make, and the fields that say what the
session actually got.

**Why a new kind rather than `agent: {type: codex}`.** The registry rejects two
implementations claiming one kind, and shadowing a built-in would change what
every other `coder_eval` user's `codex` means. A distinct kind also makes the
arm's routing readable: `agent.type` and the experiment arm tag must agree.

**The first correction** is `transcript.render_agent_output`, applied to the
`TurnRecord` this agent hands back. `transcript.py` says what it is for; the
short version is that every judge rubric under `evals/tasks/` locates the reply
at the last `[RESULT - …]` tag and scores 0.0 where there is none, and
`coder_eval` builds that shape for its Claude Code agent alone.

**The second** is `plugins.resolve_local_plugins`, applied to the plugin roots
before `start()` delegates. `plugins.py` says what it is for; the short version
is that `_setup_skills` symlinks each skill by the path it was handed, so the
relative root an experiment naturally writes links every skill back at itself.

**Neither of them is the normalisation issue #185 expected.** It asked for a
`skill://<name>` mapping, the spelling Omp uses. The spike in #181 measured
that Codex does not use that spelling, and `coder_eval`'s `skill_triggered`
already detects the spelling Codex does use — a shell read of
`.agents/skills/<name>/SKILL.md`, whose command string carries the
`skills/<name>/` substring the criterion matches on. Adding a mapping would have
been a rename of something already named.

Nothing here can be exercised without a `coder_eval` install and the Codex SDK.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from coder_eval.agents.codex_agent import CodexAgent
from coder_eval.errors import AgentConfigError
from coder_eval.models import ApiRoute, CodexAgentConfig, TurnRecord

from .plugins import PluginPathError, resolve_local_plugins
from .transcript import is_already_tagged, render_agent_output


logger = logging.getLogger(__name__)

#: The kind string this agent registers under, and the value a task's or an
#: experiment's `agent: {type: …}` carries.
AGENT_KIND = "codex-daily-driver"

#: Where `CodexAgent._setup_skills` links a `plugins:` root's skills. Read back
#: after `start()` so a run records what the session was actually given.
SKILLS_DIR = Path(".agents") / "skills"


class CodexDailyDriverAgentConfig(CodexAgentConfig):
    """Configuration for the `codex-daily-driver` kind.

    The inherited fields keep their existing meaning. Focused delivery
    comparisons opt into trusted lifecycle hooks and offline fixture confinement.
    """

    type: Literal["codex-daily-driver"]  # type: ignore[assignment]

    #: Activate native lifecycle hooks in an explicitly prepared CODEX_HOME.
    lifecycle_hooks: bool = False
    #: Confine fixture writes and disable non-fixture native capabilities.
    offline_fixture: bool = False
    #: Reviewed hook payload selects frozen hooks without changing native account lookup.
    reviewed_hook_payload: str | None = None
    #: Permit native worktree creation in a controller-marked private DIRECT_WRITE artifacts envelope.
    fixture_worktree_envelope: bool = False


class CodexDailyDriverAgent(CodexAgent):
    """`coder_eval`'s Codex agent with the judge's transcript anchor restored."""

    def __init__(
        self,
        config: CodexDailyDriverAgentConfig,
        route: ApiRoute | None = None,
        *,
        instance_name: str = "codex-daily-driver",
    ):
        """Construct the built-in agent, relabelled in the logs.

        Args:
            config: The `codex-daily-driver` configuration.
            route: API routing configuration, unused by Codex and passed through
                for interface compatibility.
            instance_name: Short label prefixing this instance's log records.
        """
        super().__init__(config, route, instance_name=instance_name)
        self.config: CodexDailyDriverAgentConfig
        self._linked_skills: list[str] = []
        self._retagged_turns = 0
        self._already_tagged_turns = 0
        self._reviewed_hook_payload: dict[str, Any] | None = None
        self._fixture_envelope_roots: tuple[Path, Path] | None = None
        self._fixture_envelope_identity: tuple[int, int, int, int] | None = None
        self._fixture_git_directories: tuple[Path, ...] = ()

    async def start(
        self,
        working_directory: str,
        *,
        env_path_prepend: list[str] | None = None,
        plugin_tools_dir: str | None = None,
    ) -> None:
        """Resolve the plugin roots, start the session, then check what it got.

        **The roots are made absolute first**, and `plugins.py` says why at
        length: `CodexAgent._setup_skills` symlinks each skill by the path it was
        handed, so a relative root — which is what these experiments write, and
        what the Claude agent never sees because `coder_eval` resolves it before
        that agent is built — produces one broken link per skill.

        **Then the count is checked, and an empty one is fatal.** The Omp arm
        raises in the same place and for the same reason: an arm that declared
        plugins and loaded none runs untreated and reports zeros, which reads
        exactly like a skill that never fires. `_setup_skills` only warns, and
        only when it had sources to link from — those broken links are still
        `iterdir()` entries, so its own warning stays silent on exactly
        the failure above.

        The reading is done from the directory rather than from the session: the
        Codex app-server exposes no query for the skills it discovered, so unlike
        the Omp arm's `omp_skills_loaded` this says what was offered rather than
        what was taken up. Requiring a readable `SKILL.md` is what makes it an
        answer at all rather than a count of directory entries.
        """
        self._reviewed_hook_payload = None
        self._fixture_envelope_roots = None
        self._fixture_envelope_identity = None
        self._fixture_git_directories = ()
        if self.config.fixture_worktree_envelope:
            self._validate_fixture_worktree_envelope(Path(working_directory), require_git=False)
        if self.config.reviewed_hook_payload is not None:
            self._reviewed_hook_payload = self._load_reviewed_hook_payload()
        elif self.config.lifecycle_hooks:
            home = os.environ.get("CODEX_HOME")
            if not home or not (Path(home) / "hooks.json").is_file():
                raise AgentConfigError(
                    "codex-daily-driver: lifecycle_hooks needs an explicit, "
                    "pre-reviewed CODEX_HOME/hooks.json for this frozen arm"
                )
        if self.config.plugins:
            try:
                self.config.plugins = resolve_local_plugins(list(self.config.plugins), base=Path.cwd())
            except PluginPathError as failure:
                # Typed on the way out. `coder_eval` categorises a bare
                # `RuntimeError` as the retryable `AGENT_API_ERROR` -- three
                # retries at 5/10/20s, the Codex client re-spawned each time,
                # and a deterministic path failure finally reported as a network
                # problem. `AgentConfigError` is routed by `isinstance` to the
                # non-retryable `AGENT_CONFIG_ERROR`, which is what a mistyped
                # plugin root actually is.
                raise AgentConfigError(str(failure)) from failure
        await super().start(
            working_directory,
            env_path_prepend=env_path_prepend,
            plugin_tools_dir=plugin_tools_dir,
        )
        self._linked_skills = self._read_linked_skills()
        if self.config.plugins and not self._linked_skills:
            # `AgentConfigError` for the reason above: retrying a plugin root
            # that linked nothing links nothing again, three times over.
            raise AgentConfigError(
                "codex-daily-driver: plugins were declared but no skill with a readable SKILL.md is under "
                f"{SKILLS_DIR}; the arm would run untreated"
            )

    @staticmethod
    def _canonical_fixture_directory(value: Any) -> Path:
        """Reject noncanonical, missing, symlinked or non-owned fixture roots."""
        if not isinstance(value, str):
            raise AgentConfigError("Fixture envelope paths must be canonical absolute strings")
        path = Path(value)
        if not path.is_absolute() or str(path) != value or path.resolve(strict=True) != path:
            raise AgentConfigError("Fixture envelope paths must be canonical and must not contain symlinks")
        details = path.stat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.getuid():
            raise AgentConfigError("Fixture envelope roots must be current-user owned directories")
        return path

    def _validate_fixture_worktree_envelope(self, working_directory: Path, *, require_git: bool) -> None:
        """Bind a private runner envelope to this task before granting native writes."""
        if not self.config.offline_fixture or self.config.allowed_tools is None:
            raise AgentConfigError("fixture_worktree_envelope requires offline_fixture and explicit allowed_tools")
        allowed = set(self.config.allowed_tools) - set(self.config.disallowed_tools or [])
        if not allowed & {"Bash", "Write", "Edit"}:
            raise AgentConfigError("fixture_worktree_envelope requires write-capable allowed_tools")
        try:
            task = self._canonical_fixture_directory(str(working_directory))
            artifacts = self._canonical_fixture_directory(str(task.parent))
            if artifacts.name != "artifacts" or stat.S_IMODE(artifacts.stat().st_mode) != 0o700:
                raise AgentConfigError("Fixture artifacts envelope must be named artifacts and have mode0700")
            marker = artifacts.parent / "fixture-envelope.json"
            details = marker.lstat()
            if (
                not stat.S_ISREG(details.st_mode)
                or details.st_uid != os.getuid()
                or stat.S_IMODE(details.st_mode) != 0o600
            ):
                raise AgentConfigError("Fixture envelope marker must be an owned regular mode0600 file")
            payload = json.loads(marker.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != {"task_root", "artifacts_root"}:
                raise AgentConfigError("Fixture envelope marker must contain exactly task_root and artifacts_root")
            roots = (
                self._canonical_fixture_directory(payload["task_root"]),
                self._canonical_fixture_directory(payload["artifacts_root"]),
            )
            if roots != (task, artifacts):
                raise AgentConfigError("Fixture envelope marker does not match the actual task directory")
            task_stat, artifacts_stat = task.stat(), artifacts.stat()
            identity = (task_stat.st_dev, task_stat.st_ino, artifacts_stat.st_dev, artifacts_stat.st_ino)
            if self._fixture_envelope_roots is None:
                if set(artifacts.iterdir()) != {task}:
                    raise AgentConfigError("Fresh fixture envelope must contain only its declared task directory")
                self._fixture_envelope_roots = roots
                self._fixture_envelope_identity = identity
            elif roots != self._fixture_envelope_roots or identity != self._fixture_envelope_identity:
                raise AgentConfigError("Fixture envelope roots changed after agent start")
            if require_git:
                result = subprocess.run(
                    ["git", "-C", str(task), "rev-parse", "--path-format=absolute",
                     "--git-common-dir", "--absolute-git-dir", "--show-toplevel"],
                    check=True, capture_output=True, text=True, timeout=5,
                )
                paths = result.stdout.splitlines()
                if len(paths) != 3 or paths[2] != str(task):
                    raise AgentConfigError("Fixture Git metadata does not describe the declared task root")
                directories = tuple(self._canonical_fixture_directory(value) for value in paths[:2])
                if any(not directory.is_relative_to(artifacts) or directory == artifacts for directory in directories):
                    raise AgentConfigError("Fixture Git metadata must remain inside its owned artifacts envelope")
                self._fixture_git_directories = directories
        except AgentConfigError:
            raise
        except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as failure:
            raise AgentConfigError("Unable to validate fixture worktree envelope and Git metadata") from failure

    def _load_reviewed_hook_payload(self) -> dict[str, Any]:
        """Reject settings outside the reviewed hook and native-isolation contract."""
        if not self.config.lifecycle_hooks or not self.config.offline_fixture:
            raise AgentConfigError("reviewed_hook_payload requires lifecycle_hooks and offline_fixture")
        if self.config.allowed_tools is None:
            raise AgentConfigError("reviewed_hook_payload requires an explicit allowed_tools list")
        try:
            payload = json.loads(Path(self.config.reviewed_hook_payload or "").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as failure:
            raise AgentConfigError("Unable to read reviewed_hook_payload JSON") from failure
        if not isinstance(payload, dict) or set(payload) != {"hooks", "mcp_servers", "features"}:
            raise AgentConfigError("reviewed_hook_payload must contain exactly hooks, mcp_servers, and features")
        features = payload["features"]
        if (
            not isinstance(features, dict)
            or set(features) != {"plugins", "plugin_hooks", "apps"}
            or any(value is not False for value in features.values())
        ):
            raise AgentConfigError("reviewed_hook_payload may only disable plugins, plugin_hooks, and apps")
        servers = payload["mcp_servers"]
        if not isinstance(servers, dict) or any(
            not isinstance(name, str) or not name
            or not isinstance(server, dict) or set(server) != {"enabled"}
            or server["enabled"] is not False
            for name, server in servers.items()
        ):
            raise AgentConfigError("reviewed_hook_payload MCP entries must contain only enabled=false")
        from openai_codex.generated.v2_all import HookEventName

        hooks = payload["hooks"]
        events = {event.value[0].upper() + event.value[1:] for event in HookEventName}
        if (
            not isinstance(hooks, dict) or not set(hooks) <= events | {"state"}
            or not hooks.get("SessionStart") or not hooks.get("SubagentStart")
            or not isinstance(hooks.get("state"), dict)
        ):
            raise AgentConfigError("reviewed_hook_payload requires native startup hooks and explicit hook state")
        count = 0
        for event, groups in hooks.items():
            if event == "state":
                continue
            if not isinstance(groups, list):
                raise AgentConfigError("reviewed_hook_payload hook events must contain matcher groups")
            for group in groups:
                if (
                    not isinstance(group, dict) or not set(group) <= {"matcher", "hooks"}
                    or ("matcher" in group and not isinstance(group["matcher"], str))
                    or not isinstance(group.get("hooks"), list) or not group["hooks"]
                ):
                    raise AgentConfigError("reviewed_hook_payload contains an invalid hook matcher group")
                for handler in group["hooks"]:
                    if (
                        not isinstance(handler, dict)
                        or not set(handler) <= {"type", "command", "timeout", "statusMessage", "additionalContextLimit"}
                        or handler.get("type") != "command"
                        or not isinstance(handler.get("command"), str) or not handler["command"].strip()
                        or ("statusMessage" in handler and not isinstance(handler["statusMessage"], str))
                        or any(
                            key in handler and (type(handler[key]) is not int or handler[key] < 0)
                            for key in ("timeout", "additionalContextLimit")
                        )
                    ):
                        raise AgentConfigError("reviewed_hook_payload supports only reviewed native command hooks")
                    count += 1
        enabled = 0
        for key, state in hooks["state"].items():
            if not isinstance(key, str) or not isinstance(state, dict):
                raise AgentConfigError("reviewed_hook_payload contains invalid hook state")
            if set(state) == {"enabled"} and state["enabled"] is False:
                continue
            digest = state.get("trusted_hash")
            if (
                set(state) != {"enabled", "trusted_hash"} or state.get("enabled") is not True
                or not key.startswith("/<session-flags>/config.toml:")
                or not isinstance(digest, str) or not digest.startswith("sha256:")
                or len(digest) != 71 or any(char not in "0123456789abcdef" for char in digest[7:])
            ):
                raise AgentConfigError("reviewed_hook_payload may trust only reviewed session-flag hooks")
            enabled += 1
        if enabled != count:
            raise AgentConfigError("reviewed_hook_payload must explicitly trust every selected hook")
        return payload

    @staticmethod
    def _native_inline(value: Any) -> str:
        """Encode the validated payload for metadata-only native config inspection."""
        if isinstance(value, dict):
            return "{" + ",".join(
                json.dumps(key, ensure_ascii=False) + "=" + CodexDailyDriverAgent._native_inline(item)
                for key, item in value.items()
            ) + "}"
        if isinstance(value, list):
            return "[" + ",".join(CodexDailyDriverAgent._native_inline(item) for item in value) + "]"
        return json.dumps(value, ensure_ascii=False)

    def _fixture_project_trust(self) -> dict[str, dict[str, str]]:
        """Keep native write-capable fixture auto-trust out of shared configuration."""
        if not self.config.offline_fixture:
            return {}
        allowed = set(self.config.allowed_tools or []) - set(self.config.disallowed_tools or [])
        if not allowed & {"Bash", "Write", "Edit"}:
            return {}
        if self.working_directory is None:
            raise AgentConfigError("Fixture project trust requires a started agent")
        try:
            task = self._canonical_fixture_directory(str(self.working_directory))
        except (OSError, ValueError) as failure:
            raise AgentConfigError("Fixture project trust requires an owned canonical task directory") from failure
        # thread/start otherwise persists workspace-write project trust in
        # CODEX_HOME/config.toml. This exact-path override is per thread only.
        return {str(task): {"trust_level": "trusted"}}

    def _validate_native_fixture_isolation(self) -> None:
        """Reject inherited additions to reviewed hooks or the fixed fixture profile."""
        from openai_codex.client import CodexClient, CodexConfig
        from openai_codex.generated.v2_all import ConfigReadResponse, HooksListResponse

        payload = self._reviewed_hook_payload
        if self.working_directory is None:
            raise AgentConfigError("Native fixture inspection requires a started agent")
        overrides = dict(payload or {})
        permissions = None
        projects = self._fixture_project_trust()
        if projects:
            overrides["projects"] = projects
        if self.config.fixture_worktree_envelope:
            native = self._build_thread_options()["config"]
            permissions = native["permissions"]["owned-fixture"]
            overrides.update(default_permissions="owned-fixture", permissions=native["permissions"])
        # Metadata and execution use only validated hook values and this
        # internally generated profile. There is no caller-supplied config API.
        client = CodexClient(CodexConfig(
            env=self._build_codex_env(), cwd=str(self.working_directory),
            config_overrides=tuple(
                key + "=" + self._native_inline(value) for key, value in overrides.items()
            ),
        ))
        try:
            client.start()
            client.initialize()
            if payload is not None:
                expected = {
                    key: state["trusted_hash"] for key, state in payload["hooks"]["state"].items()
                    if state["enabled"]
                }
                response = client.request(
                    "hooks/list", {"cwds": [str(self.working_directory)]}, response_model=HooksListResponse
                )
                found = set()
                for row in response.data:
                    if row.errors:
                        raise AgentConfigError("reviewed_hook_payload failed native hook validation")
                    for wrapped in row.hooks:
                        hook = wrapped.root
                        if hook.is_managed:
                            raise AgentConfigError("reviewed_hook_payload cannot isolate unexpected managed hooks")
                        if not hook.enabled:
                            continue
                        if (
                            hook.key not in expected or hook.source.value != "sessionFlags"
                            or hook.trust_status.value != "trusted" or hook.current_hash != expected[hook.key]
                        ):
                            raise AgentConfigError("reviewed_hook_payload leaves unreviewed or untrusted hooks enabled")
                        found.add(hook.key)
                if found != set(expected):
                    raise AgentConfigError("reviewed_hook_payload did not load every reviewed hook")
            config = client.request(
                "config/read", {"cwd": str(self.working_directory), "includeLayers": False},
                response_model=ConfigReadResponse,
            ).config.model_dump(mode="json", by_alias=True)

            def populated(value: Any) -> Any:
                # Native config/read serializes unset profile fields as null.
                if isinstance(value, dict):
                    return {key: populated(item) for key, item in value.items() if item is not None}
                return value

            if permissions is not None and (
                config.get("default_permissions") != "owned-fixture"
                or populated((config.get("permissions") or {}).get("owned-fixture")) != permissions
            ):
                raise AgentConfigError("Native fixture profile contains inherited or altered permissions")
            if any(
                (config.get("projects") or {}).get(path, {}).get("trust_level") != state["trust_level"]
                for path, state in projects.items()
            ):
                raise AgentConfigError("Native fixture task trust was not applied without persistence")
            # Inspect names and enable flags only. Never retain or log host
            # server settings, environment values, or authentication.
            if payload is not None:
                if any(server.get("enabled", True) for server in (config.get("mcp_servers") or {}).values()):
                    raise AgentConfigError("reviewed_hook_payload leaves inherited MCP servers enabled")
                if any((config.get("features") or {}).get(name) is not False for name in payload["features"]):
                    raise AgentConfigError("reviewed_hook_payload did not disable unrelated native features")
        except AgentConfigError:
            raise
        except Exception as failure:
            raise AgentConfigError("Unable to inspect native fixture hook/config metadata") from failure
        finally:
            client.close()

    def _build_thread_options(self) -> dict[str, Any]:
        """Activate trusted hooks and native confinement only for opted-in fixtures."""
        from openai_codex import Sandbox
        from openai_codex.generated.v2_all import ThreadStartSource

        options = super()._build_thread_options()
        if self.config.lifecycle_hooks:
            options["session_start_source"] = ThreadStartSource.startup
        if self.config.offline_fixture:
            if self.config.allowed_tools is None:
                raise AgentConfigError("offline_fixture requires an explicit allowed_tools list")
            allowed = set(self.config.allowed_tools) - set(self.config.disallowed_tools or [])
            shell = bool(allowed & {"Read", "Grep", "Glob", "Skill", "Bash", "Write", "Edit"})
            write = bool(allowed & {"Bash", "Write", "Edit"})
            options["sandbox"] = Sandbox.workspace_write if write else Sandbox.read_only
            native = dict(options.get("config") or {})
            native.pop("enabled_tools", None)
            native.pop("disabled_tools", None)
            native["web_search"] = "disabled"
            native["sandbox_workspace_write"] = {
                "writable_roots": [],
                "network_access": False,
                "exclude_tmpdir_env_var": True,
                "exclude_slash_tmp": True,
            }
            native["features"] = {
                **native.get("features", {}),
                "shell_tool": shell,
                "multi_agent": bool(allowed & {"Agent", "Task"}),
                **dict.fromkeys(
                    ("goals", "view_image", "apps", "computer_use", "browser_use",
                     "image_generation", "skill_search", "sleep_tool"), False
                ),
            }
            projects = self._fixture_project_trust()
            if projects:
                native["projects"] = projects
            options["config"] = native
        if self.config.fixture_worktree_envelope:
            if self._fixture_envelope_roots is None or not self._fixture_git_directories:
                raise AgentConfigError("Fixture envelope needs validated task Git metadata before native execution")
            options.pop("sandbox", None)
            native = options["config"]
            native.pop("sandbox_workspace_write", None)
            native["default_permissions"] = "owned-fixture"
            native["permissions"] = {
                "owned-fixture": {
                    "extends": ":workspace",
                    "filesystem": {
                        str(self._fixture_envelope_roots[1]): "write",
                        **{str(directory): "write" for directory in self._fixture_git_directories},
                        ":tmpdir": "read",
                        ":slash_tmp": "read",
                    },
                    "network": {"enabled": False},
                }
            }
        if self._reviewed_hook_payload is not None:
            payload = self._reviewed_hook_payload
            native = options["config"]
            native["hooks"] = payload["hooks"]
            native["mcp_servers"] = payload["mcp_servers"]
            native["features"].update(payload["features"])
        return options

    def _log_config_enforcement(self) -> None:
        """Avoid the inherited full-access claim when native fixture confinement applies."""
        if self.config.offline_fixture:
            policy = "owned worktree envelope" if self.config.fixture_worktree_envelope else "read-only/workspace-write"
            self._log.info(
                "Offline fixture: native %s sandbox; network and non-fixture tools disabled. "
                "Read/Skill share the native shell capability.", policy,
            )
        else:
            super()._log_config_enforcement()

    async def _run_turn_with_streaming(
        self, state: Any, should_stop: Callable[[], bool] | None = None
    ) -> tuple[Any, Any, str]:
        """Route a failed native turn through the inherited partial-record error path."""
        result = await super()._run_turn_with_streaming(state, should_stop)
        turn = result[0]
        status = getattr(turn, "status", None)
        if getattr(status, "value", status) == "failed":
            error = getattr(turn, "error", None)
            raise RuntimeError(getattr(error, "message", None) or "Codex returned a failed turn")
        return result

    async def communicate(self, user_input: str, **kwargs: Any) -> TurnRecord:
        """Run one turn, and hand back its transcript with the judge's anchor in it.

        Both exits are covered. A clean turn returns its `TurnRecord` here; a
        crashed or timed-out one raises after leaving a partial record in
        `pending_turn`, which the orchestrator reads and reports. A judged row
        that crashed should score 0.0 on the reply rather than on the anchor
        being absent, so the partial is tagged `ERROR` rather than left bare.

        `**kwargs` rather than the base signature's keyword arguments: this
        override adds nothing to the call and forwards it whole, so a new
        keyword on `Agent.communicate` reaches the built-in without a change
        here.
        """
        if self.config.fixture_worktree_envelope:
            await self._run_async(
                self._validate_fixture_worktree_envelope, Path(self.working_directory or ""), require_git=True
            )
        if self._reviewed_hook_payload is not None or self._fixture_project_trust():
            await self._run_async(self._validate_native_fixture_isolation)
        try:
            record = await super().communicate(user_input, **kwargs)
        except BaseException:
            if self.pending_turn is not None:
                self.pending_turn = self._retagged(self.pending_turn, is_error=True)
            raise
        return self._retagged(record, is_error=False)

    def get_environment_info(self) -> dict[str, Any]:
        """The built-in's routing record, plus what this arm loaded.

        `codex_skills_linked` is the audit trail a run needs to tell a red arm
        from an arm whose plugin never arrived — `0013`'s reason for the Omp
        arm's equivalent fields. It is populated in `start()`, which is what
        makes it recordable here.

        **The retag counters are deliberately NOT here.** `coder_eval` merges
        this dict into the result once, during setup, immediately after `start()`
        and before any turn runs (`orchestrator.py`, `_record_route_environment_info`
        at both of its call sites). A counter incremented in `communicate()` is
        therefore always read as zero, so recording one would be a field that
        says nothing while looking like a measurement. The drift it was meant to
        alarm on is logged instead, in `_retagged`, where it happens.
        """
        return {
            **super().get_environment_info(),
            "codex_skills_linked": list(self._linked_skills),
            "codex_lifecycle_hooks_requested": self.config.lifecycle_hooks,
            "codex_offline_fixture": self.config.offline_fixture,
        }

    # --- internals ---------------------------------------------------------

    def _retagged(self, record: TurnRecord, *, is_error: bool) -> TurnRecord:
        """A copy of `record` whose `agent_output` carries the result anchor.

        A turn that arrives ALREADY tagged warns, once per session. Under the
        pinned `CODER_EVAL_VERSION` it never happens; if it starts happening the
        built-in has begun rendering the transcript itself and this package has
        become a no-op worth deleting. The warning goes to the run log rather
        than to `environment_info`, because that dict is captured before any
        turn has run — see `get_environment_info`.
        """
        if is_already_tagged(record.agent_output):
            self._already_tagged_turns += 1
            if self._already_tagged_turns == 1:
                self._log.warning(
                    "codex-daily-driver: a turn arrived already carrying the [RESULT - …] anchor. "
                    "The built-in agent has started rendering the transcript itself, so this package's "
                    "retag is now a no-op worth deleting — check it against the pinned CODER_EVAL_VERSION."
                )
            return record
        self._retagged_turns += 1
        return record.model_copy(
            update={"agent_output": render_agent_output(record.agent_output, is_error=is_error)}
        )

    def _read_linked_skills(self) -> list[str]:
        """The skill names under the working directory's `.agents/skills/`."""
        if self.working_directory is None:
            return []
        skills_dir = self.working_directory / SKILLS_DIR
        try:
            return sorted(entry.name for entry in skills_dir.iterdir() if (entry / "SKILL.md").exists())
        except OSError:
            # No directory is the bare variant, and is reported by the caller.
            return []
