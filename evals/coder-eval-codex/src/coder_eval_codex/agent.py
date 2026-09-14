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
arm's routing readable: `scripts/check-eval-arms.py` maps a pinned `agent.type`
to the arm tag it must carry, and `codex-daily-driver` names exactly one arm.

**The first correction** is `transcript.render_agent_output`, applied to the
`TurnRecord` this agent hands back. `transcript.py` says what it is for; the
short version is that every judge rubric under `evals/tasks/` locates the reply
at the last `[RESULT - …]` tag and scores 0.0 where there is none, and
`coder_eval` builds that shape for its Claude Code agent alone.

**The second** is `plugins.resolve_local_plugins`, applied to the plugin roots
before `start()` delegates. `plugins.py` says what it is for; the short version
is that `_setup_skills` symlinks each skill by the path it was handed, so the
relative root an experiment naturally writes links fifteen skills that point
at themselves.

**Neither of them is the normalisation issue #185 expected.** It asked for a
`skill://<name>` mapping, the spelling Omp uses. The spike in #181 measured
that Codex does not use that spelling, and `coder_eval`'s `skill_triggered`
already detects the spelling Codex does use — a shell read of
`.agents/skills/<name>/SKILL.md`, whose command string carries the
`skills/<name>/` substring the criterion matches on. Adding a mapping would have
been a rename of something already named.

Nothing here can be exercised without a `coder_eval` install and the Codex SDK,
which is why so little is here. `scripts/check-codex-agent.py` drives the pure
half in `make check`.
"""

from __future__ import annotations

import logging
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

    Every field is `CodexAgentConfig`'s. Only the discriminator differs, because
    `coder_eval` routes a raw config dict to its class by the registered kind.
    """

    type: Literal["codex-daily-driver"]  # type: ignore[assignment]


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
        self._linked_skills: list[str] = []
        self._retagged_turns = 0
        self._already_tagged_turns = 0

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
        that agent is built — produces fifteen links that point at themselves.

        **Then the count is checked, and an empty one is fatal.** The Omp arm
        raises in the same place and for the same reason: an arm that declared
        plugins and loaded none runs untreated and reports zeros, which reads
        exactly like a skill that never fires. `_setup_skills` only warns, and
        only when it had sources to link from — fifteen broken links are
        fifteen `iterdir()` entries, so its own warning stays silent on exactly
        the failure above.

        The reading is done from the directory rather than from the session: the
        Codex app-server exposes no query for the skills it discovered, so unlike
        the Omp arm's `omp_skills_loaded` this says what was offered rather than
        what was taken up. Requiring a readable `SKILL.md` is what makes it an
        answer at all rather than a count of directory entries.
        """
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
