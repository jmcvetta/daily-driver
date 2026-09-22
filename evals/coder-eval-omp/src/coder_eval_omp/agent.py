"""The `omp` agent kind: one long-lived `omp --mode rpc` process per task.

`coder_eval`'s OpenCode agent is the template — a CLI driven as a subprocess
over a newline-delimited JSON stream — and the one structural difference is
session continuity. OpenCode invokes its CLI once per turn and replays a
session id; Omp's RPC mode holds the session open, so this agent starts one
process in `start()` and writes a `prompt` command per turn into it. There is
no session id to replay, and a turn ends on the `agent_end` frame rather than
on process exit.

**Loading the plugin is not a skills mapping.** `0011` puts this repository's
constitution in `rules/*.md` behind Omp's rule provider and the session-title
and timer tools in `extensions/daily-driver.js`. Omp reads both from an
*installed* plugin's manifest, so `--plugin-dir` — which finds skills and
nothing else — would leave the constitution out of the treated arm and score
`tasks/constitution/*` zero for the wrong reason. This agent installs each
`plugins:` root with `omp plugin link` instead, which is the route
`scripts/check-omp-plugin.py` measures as loading the skills, the extension and
the manifest together.

**It installs into a throwaway Omp home**, built beside the task and discarded
with it. The laptop's own installed plugins therefore cannot reach the bare
arm, which is the isolation `coder_eval`'s Claude agent gets from
`setting_sources: []`. Provider configuration is the one thing that must come
from the real home, because a run needs a model: every file in the real
`~/.omp/agent/` is symlinked into the throwaway one, except the config this
agent writes itself.

What the frames mean is `rpc.py`'s, and it is pure so that it can be tested.
What is here is process lifecycle, the event protocol, and the recording of
what Omp actually loaded — which is the difference between a red arm and an
arm whose plugin never arrived.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import shutil
import signal
import tempfile
import time
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal, NoReturn

from coder_eval.agent import Agent
from coder_eval.errors import AgentCrashError, TurnTimeoutError
from coder_eval.models import (
    AgentState,
    ApiRoute,
    BaseAgentConfig,
    CommandTelemetry,
    ResultSummary,
    SystemPromptSemantics,
    TokenUsage,
    TurnRecord,
)
from coder_eval.streaming.callbacks import StreamCallback, safe_emit
from coder_eval.streaming.collector import EventCollector
from coder_eval.streaming.events import (
    AgentEndEvent,
    AgentEndStatus,
    AgentStartEvent,
    StreamEvent,
    TextChunkEvent,
    ToolEndEvent,
    ToolEndStatus,
    ToolStartEvent,
    TurnEndEvent,
    TurnEndStatus,
    TurnStartEvent,
)

from .rpc import (
    AgentFinished,
    ExtensionFailed,
    Text,
    ToolFinished,
    ToolStarted,
    TurnFinished,
    TurnReducer,
    TurnStarted,
)


logger = logging.getLogger(__name__)

#: The kind string this agent registers under, and the value a task's
#: `agent: {type: omp}` carries.
AGENT_KIND = "omp"

# Grace between SIGTERM and SIGKILL when tearing the RPC process down.
_TERM_GRACE_SECONDS = 5.0

# SIGKILL is absent on Windows; SIGTERM is the honest fallback there.
_SIGKILL: signal.Signals = getattr(signal, "SIGKILL", signal.SIGTERM)

# How long to wait for the `ready` frame and for each startup command. Generous:
# it covers a cold start that walks the filesystem for skills, and a timeout
# that is too short is a red run nobody can reproduce.
_STARTUP_TIMEOUT_SECONDS = 180.0

# A single frame can carry a whole tool result, which blows past asyncio's
# default 64 KiB line cap and raises mid-stream, killing the read loop.
_STDOUT_LINE_LIMIT = 16 * 1024 * 1024

_RESULT_STATUS: dict[ToolEndStatus, str] = {
    ToolEndStatus.OK: "success",
    ToolEndStatus.ERROR: "error",
    ToolEndStatus.PERMISSION_DENIED: "error",
    ToolEndStatus.UNRESOLVED: "unknown",
}

# Written into the throwaway Omp home. Skill commands are off by default, and
# with them off `get_available_commands` reports the builtins alone — so the
# run could not record which skills it loaded, which is what tells a red arm
# from an arm whose plugin never arrived.
_OMP_CONFIG = "skills:\n  enableSkillCommands: true\n"


class OmpAgentConfig(BaseAgentConfig):
    """Configuration for the `omp` agent kind.

    `model` is Omp's `provider/modelId` form (for example
    `anthropic/claude-sonnet-5`) and is applied with a `set_model` command once
    the session is up. Omitted, the session keeps whatever model the resolved
    Omp home defaults to.
    """

    type: Literal["omp"]  # type: ignore[assignment]

    binary: str = "omp"
    """The Omp executable, resolved on PATH unless an absolute path is given."""

    inherit_omp_home: bool = True
    """Symlink the real `~/.omp/agent/` into the throwaway home.

    On by default, because a run needs a model and the provider configuration
    lives there. Off, the session starts from Omp's own defaults — useful only
    where the environment configures providers some other way, since Omp
    refuses to start a session with no model available at all.
    """

    require_token_telemetry: bool = False
    """Fail a turn that captured no token counts.

    Off, unlike `coder_eval`'s OpenCode agent, and the reason is honesty:
    Omp's `docs/rpc.md` places per-turn accounting in "telemetry fields on
    `agent_end`" without naming them, so this agent reads every plausible
    spelling and records which one answered. Until a live run says which it is,
    a missing count is a gap in this adapter rather than proof of a broken
    turn. Turn it on once `usage_keys_seen` in a run's `environment_info` names
    the real fields.
    """

    extra_args: list[str] = []
    """Arguments appended to the `omp --mode rpc` command line, verbatim."""


class OmpAgent(Agent[OmpAgentConfig]):
    """Runs `omp --mode rpc` as one subprocess per task, one prompt per turn."""

    # The turn loop polls `should_stop` at every frame boundary and honors it by
    # aborting the in-flight prompt.
    supports_cooperative_stop: ClassVar[bool] = True

    # Omp takes no system-prompt argument in RPC mode, so `system_prompt` is not
    # honored and the honest regime is the base's "unknown". Declared rather
    # than left unset, so the run marker is a decision.
    system_prompt_semantics: ClassVar[SystemPromptSemantics] = "unknown"

    def __init__(
        self,
        config: OmpAgentConfig,
        route: ApiRoute | None = None,
        *,
        task_id: str = "unknown",
    ) -> None:
        """Every parameter the factory can pass is declared, never absorbed.

        `create_agent` calls `agent_class(config, route=route, **kwargs)` through
        a cast, so nothing checks the call site; a `**_` sink would mean nothing
        checked it at runtime either. `route` is accepted for factory parity and
        is unused — Omp owns its own provider configuration.
        """
        self.config = config
        self.route = route
        self.task_id = task_id
        self.working_directory: str | None = None
        self._env_path_prepend: list[str] = []
        self._process: asyncio.subprocess.Process | None = None
        self._home: tempfile.TemporaryDirectory[str] | None = None
        self._request_id = 0
        self._session_id: str | None = None
        self._loaded_commands: list[str] = []
        self._loaded_skills: list[str] = []
        self._linked_plugins: list[str] = []
        self._extension_errors: list[str] = []
        self._argument_keys_seen: set[str] = set()
        self._usage_keys_seen: set[str] = set()
        self._state = AgentState.WORKING

    # --- lifecycle ---------------------------------------------------------

    async def start(
        self,
        working_directory: str,
        *,
        env_path_prepend: list[str] | None = None,
        plugin_tools_dir: str | None = None,
    ) -> None:
        """Build the Omp home, install the plugins, and open the RPC session.

        `plugin_tools_dir` is UiPath's CLI pin and has no Omp equivalent; it is
        accepted and ignored.
        """
        binary = shutil.which(self.config.binary) or (
            self.config.binary if Path(self.config.binary).is_absolute() else None
        )
        if binary is None:
            raise RuntimeError(
                f"The {self.config.binary!r} binary was not found on PATH. "
                "Install Omp with `curl -fsSL https://omp.sh/install | sh`."
            )

        unenforced = [
            field
            for field in ("allowed_tools", "disallowed_tools", "system_prompt", "system_prompt_file")
            if getattr(self.config, field, None)
        ]
        if unenforced:
            # Said out loud once per task rather than left to be discovered from
            # a report. `disallowed_tools` is what the trigger rows use to keep
            # a denied `Read` of `skills/<name>/SKILL.md` from scoring as an
            # engagement, and this arm cannot enforce it: Omp's RPC mode takes
            # no per-session tool allowlist. A no-fire row is therefore weaker
            # here than on Claude Code, and `evals/README.md` says so.
            logger.warning(
                "omp: %s set but NOT enforced — Omp's RPC mode has no equivalent knob, so the run is "
                "unconstrained by them; do not read them as a boundary.",
                ", ".join(unenforced),
            )

        self.working_directory = working_directory
        self._env_path_prepend = list(env_path_prepend or [])
        self._home = tempfile.TemporaryDirectory(prefix="coder-eval-omp-")
        home = Path(self._home.name)
        self._prepare_home(home)
        try:
            await self._link_plugins(binary, home)
            await self._spawn(binary, home)
            await self._record_what_loaded()
            await self._apply_model()
        except Exception:
            # A half-built session must not survive the failure. `coder_eval`
            # retries a start that raises, so an RPC process left running here
            # is one orphan per attempt — each holding a session, a model
            # connection and a throwaway home.
            await self.kill()
            if self._home is not None:
                with contextlib.suppress(OSError):
                    self._home.cleanup()
                self._home = None
            self._state = AgentState.ERROR
            raise
        self._state = AgentState.WORKING

    async def stop(self) -> None:
        """Close stdin — Omp's documented shutdown — then kill whatever is left."""
        proc = self._process
        if proc is not None and proc.returncode is None and proc.stdin is not None:
            with contextlib.suppress(BrokenPipeError, ConnectionResetError, OSError, ValueError):
                proc.stdin.close()
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=_TERM_GRACE_SECONDS)
        await self.kill()
        if self._home is not None:
            with contextlib.suppress(OSError):
                self._home.cleanup()
            self._home = None
        self._mark_stopped()

    async def kill(self) -> None:
        proc = self._process
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                proc.terminate()
            with contextlib.suppress(TimeoutError, asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=_TERM_GRACE_SECONDS)
            if proc.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    proc.kill()

    def kill_sync(self) -> None:
        """SIGKILL the RPC process from the watchdog thread, which cannot await."""
        proc = self._process
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(proc.pid, _SIGKILL)

    def get_environment_info(self) -> dict[str, Any]:
        """What the arm loaded, recorded per task so a report can be audited.

        Issue #173's third acceptance criterion: a red arm must be
        distinguishable from an arm whose plugin never loaded. These fields are
        how. `omp_skills_loaded` is read back from the running session's own
        command registry, not from the directory that was handed to it.
        """
        info: dict[str, Any] = {
            **super().get_environment_info(),
            "omp_model": self.config.model,
            "omp_linked_plugins": list(self._linked_plugins),
            "omp_skills_loaded": list(self._loaded_skills),
            "omp_extension_errors": list(self._extension_errors),
        }
        if self._session_id:
            info["omp_session_id"] = self._session_id
        if self._argument_keys_seen:
            # The spike could not say whether a tool frame carries its input
            # arguments, or under which key. A live run answers it here.
            info["omp_argument_keys_seen"] = sorted(self._argument_keys_seen)
        if self._usage_keys_seen:
            info["omp_usage_keys_seen"] = sorted(self._usage_keys_seen)
        return info

    # --- the turn ----------------------------------------------------------

    async def communicate(
        self,
        user_input: str,
        *,
        stream_callback: StreamCallback | None = None,
        timeout: float | None = None,
        max_turns: int | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> TurnRecord:
        proc = self._process
        if proc is None or self.working_directory is None:
            raise RuntimeError("OmpAgent.start() must be called before communicate()")

        self._begin_turn()
        collector = EventCollector()
        reducer = TurnReducer()
        started_at = time.monotonic()
        open_tools: dict[str, CommandTelemetry] = {}
        sequence = 0
        current_turn_id = ""
        finalized = [False]
        max_turns_exhausted = False
        stopped_early = False

        def emit(event: StreamEvent) -> None:
            collector.on_event(event)
            if stream_callback is not None:
                safe_emit(stream_callback, event)

        def finalize(
            status: AgentEndStatus,
            *,
            crashed: bool = False,
            crash_reason: str | None = None,
        ) -> None:
            """Close the orphans and emit the one terminal event.

            Idempotent: the protocol allows exactly one `AgentEndEvent` per
            `communicate()`, and a late failure must not emit a second.
            """
            if finalized[0]:
                return
            finalized[0] = True
            for closed in reducer.close_open_tools():
                _emit_tool_end(emit, self.task_id, current_turn_id, open_tools, closed)
            if current_turn_id:
                emit(
                    TurnEndEvent(
                        task_id=self.task_id,
                        turn_id=current_turn_id,
                        status=TurnEndStatus(status.value),
                        tokens=None,
                    )
                )
            emit(
                AgentEndEvent(
                    task_id=self.task_id,
                    status=status,
                    usage=TokenUsage(**reducer.usage),
                    iteration=self._iteration,
                    user_input=user_input,
                    agent_output=reducer.agent_output(is_error=crashed),
                    model_used=self.config.model,
                    assistant_turn_count=reducer.turn_count,
                    num_turns=reducer.turn_count,
                    max_turns_exhausted=max_turns_exhausted,
                    result_summary=ResultSummary(
                        is_error=crashed,
                        subtype=status.value,
                        result=crash_reason or reducer.error_message,
                    ),
                    crashed=crashed,
                    crash_reason=crash_reason,
                    duration_seconds=time.monotonic() - started_at,
                )
            )

        emit(
            AgentStartEvent(
                task_id=self.task_id,
                prompt=user_input,
                iteration=self._iteration,
                model=self.config.model,
            )
        )

        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            request_id = self._next_request_id()
            await self._send({"id": request_id, "type": "prompt", "message": user_input})

            def dispatch(action: Any) -> bool:
                """Emit one reducer action as a stream event.

                Shared by the live loop and the abort settle, so a frame that
                lands after a stop is recorded exactly as one that lands before
                it. Returns True only for a terminal `AgentFinished`.
                """
                nonlocal sequence, current_turn_id
                if isinstance(action, Text):
                    emit(
                        TextChunkEvent(
                            task_id=self.task_id,
                            turn_id=current_turn_id,
                            text=action.text,
                        )
                    )
                elif isinstance(action, TurnStarted):
                    current_turn_id = action.turn_id
                    emit(
                        TurnStartEvent(
                            task_id=self.task_id,
                            turn_id=current_turn_id,
                            model=self.config.model,
                        )
                    )
                elif isinstance(action, TurnFinished):
                    emit(
                        TurnEndEvent(
                            task_id=self.task_id,
                            turn_id=action.turn_id,
                            status=TurnEndStatus.COMPLETED,
                            tokens=None,
                        )
                    )
                    current_turn_id = ""
                elif isinstance(action, ToolStarted):
                    sequence += 1
                    telemetry = CommandTelemetry(
                        tool_name=action.tool_name,
                        tool_id=action.call_id,
                        assistant_turn_index=reducer.turn_count,
                        timestamp=datetime.now(),
                        execution_started_at=datetime.now(),
                        parameters=dict(action.parameters),
                        sequence_number=sequence,
                    )
                    open_tools[action.call_id] = telemetry
                    emit(
                        ToolStartEvent(
                            task_id=self.task_id,
                            turn_id=current_turn_id,
                            tool=telemetry,
                        )
                    )
                elif isinstance(action, ToolFinished):
                    _emit_tool_end(emit, self.task_id, current_turn_id, open_tools, action)
                elif isinstance(action, ExtensionFailed):
                    # The constitution and the session tools ride on the
                    # extension, so this is a defect in the arm rather than
                    # in the skill under test. Recorded, not swallowed.
                    self._extension_errors.append(
                        f"{action.extension_path} on {action.event}: {action.error}"
                    )
                    logger.error("omp: extension error: %s", self._extension_errors[-1])
                elif isinstance(action, AgentFinished) and action.terminal:
                    # `isTerminal: false` means maintenance has scheduled
                    # more work and the session will resume, so only a
                    # terminal end settles the turn.
                    return True
                return False

            assert proc.stdout is not None
            settled = False
            while not settled:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    await self._timeout_turn(finalize, collector, timeout or 0.0)

                try:
                    line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
                except (TimeoutError, asyncio.TimeoutError):
                    await self._timeout_turn(finalize, collector, timeout or 0.0)
                if not line:
                    # EOF with no terminal `agent_end`: the process died under
                    # the turn. Crash rather than report an empty success.
                    self._crash(
                        finalize,
                        collector,
                        f"omp closed its stream after {reducer.recognized} recognized frame(s) "
                        "without a terminal agent_end",
                    )

                frame = _parse(line)
                if frame is None:
                    continue

                for action in reducer.feed(frame):
                    if dispatch(action):
                        settled = True

                if settled:
                    break
                if max_turns is not None and reducer.turn_count > max_turns:
                    max_turns_exhausted = True
                    await self._abort_and_settle(reducer, dispatch)
                    break
                if should_stop is not None and should_stop():
                    stopped_early = True
                    await self._abort_and_settle(reducer, dispatch)
                    break

            self._argument_keys_seen.update(reducer.argument_keys_seen)
            self._usage_keys_seen.update(reducer.usage_keys_seen)

            if reducer.recognized == 0:
                # The vocabulary moved. A turn that recognized nothing captured
                # no telemetry, and reporting it as a clean empty success is
                # indistinguishable from a real pass in every aggregate.
                self._crash(
                    finalize,
                    collector,
                    "omp emitted no recognized event frames; the RPC vocabulary has moved "
                    f"(saw: {sorted(reducer.unrecognized_types)})",
                )
            if self.config.require_token_telemetry and not reducer.usage:
                self._crash(
                    finalize,
                    collector,
                    "omp reported no token counts on agent_end; the telemetry field names have moved",
                )

            status = AgentEndStatus.MAX_TURNS_EXHAUSTED if max_turns_exhausted else AgentEndStatus.COMPLETED
            if stopped_early:
                # Its own status, not COMPLETED: a run cut by `stop_early` read
                # a truncated trajectory, and reporting it as a full one would
                # make the same event read differently per harness.
                status = AgentEndStatus.STOPPED_EARLY
            finalize(status)
            # Built before the turn is marked clean: a failure in the reduction
            # is a failed turn, and `_end_turn_ok` would clear the rollback flag
            # `discard_pending_turn` needs.
            record = collector.build_turn_record()
            self._end_turn_ok()
            return record

        except (AgentCrashError, TurnTimeoutError):
            raise
        except asyncio.CancelledError:
            self._finalize_external_cancel(finalize)
            self._capture_partial_turn(collector)
            raise
        except Exception as error:
            self._crash(finalize, collector, f"Omp turn failed: {error!s}", cause=error)
            raise  # unreachable: _crash is NoReturn. Kept so the flow is explicit.

    # --- startup -----------------------------------------------------------

    def _prepare_home(self, home: Path) -> None:
        """A throwaway Omp home that borrows the real one's providers.

        Every file in the real `~/.omp/agent/` is symlinked in, so the run finds
        the models and credentials a person configured. `config.yml` is written
        here instead of symlinked: the arm runs on Omp's defaults plus skill
        commands, rather than on whatever a laptop happens to have set, which is
        the same isolation `coder_eval`'s Claude agent gets from
        `setting_sources: []`.

        Nothing is written into the real home. `omp plugin link` writes into
        this one.
        """
        agent_dir = home / ".omp" / "agent"
        agent_dir.mkdir(parents=True, exist_ok=True)

        if self.config.inherit_omp_home:
            real = Path(os.path.expanduser("~")) / ".omp" / "agent"
            if real.is_dir():
                for entry in sorted(real.iterdir()):
                    if entry.name == "config.yml" or not entry.is_file():
                        continue
                    with contextlib.suppress(OSError):
                        (agent_dir / entry.name).symlink_to(entry)
            else:
                logger.warning(
                    "omp: %s does not exist, so the session inherits no provider configuration; "
                    "Omp refuses to start a session with no model available.",
                    real,
                )

        (agent_dir / "config.yml").write_text(_OMP_CONFIG, encoding="utf-8")

    async def _link_plugins(self, binary: str, home: Path) -> None:
        """Install every `plugins:` root into the throwaway home.

        `omp plugin link` is the offline half of the install route, and the
        install route is the only one that loads a plugin's extension and rules
        as well as its skills — measured in `scripts/check-omp-plugin.py`.

        A declared plugin that does not install is fatal. The alternative is an
        arm that runs without the skills under test and reports zeros, which
        reads exactly like a skill that never fires.
        """
        env = self._child_env(home)
        for plugin in self.config.plugins or []:
            if not isinstance(plugin, Mapping) or plugin.get("type") != "local":
                raise RuntimeError(f"omp: only `type: local` plugin entries are supported; got {plugin!r}")
            path = plugin.get("path")
            if not path:
                continue
            root = Path(os.path.expandvars(str(path))).resolve()
            if not root.is_dir():
                raise RuntimeError(f"omp: plugin path {path!r} resolved to {root}, which is not a directory")
            # Awaited rather than run with `subprocess.run`: `start()` runs on
            # the orchestrator's event loop, which every other task in a
            # parallel run shares, and a blocking call here would stall all of
            # them for as long as an install takes.
            linked = await asyncio.create_subprocess_exec(
                binary,
                "plugin",
                "link",
                str(root),
                cwd=str(root),
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    linked.communicate(), timeout=_STARTUP_TIMEOUT_SECONDS
                )
            except (TimeoutError, asyncio.TimeoutError):
                with contextlib.suppress(ProcessLookupError):
                    linked.kill()
                raise RuntimeError(
                    f"omp plugin link {root} did not finish within {_STARTUP_TIMEOUT_SECONDS:.0f}s"
                ) from None
            if linked.returncode != 0:
                raise RuntimeError(
                    f"omp plugin link {root} failed ({linked.returncode}): "
                    f"{stdout.decode('utf-8', 'replace').strip()} "
                    f"{stderr.decode('utf-8', 'replace').strip()}"
                )
            self._linked_plugins.append(str(root))
        if self.config.plugins and not self._linked_plugins:
            raise RuntimeError("omp: plugins were declared but none installed; the arm would run untreated")

    async def _spawn(self, binary: str, home: Path) -> None:
        """Start `omp --mode rpc` and wait for its `ready` frame."""
        argv = [binary, "--mode", "rpc", *self.config.extra_args]
        self._process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.working_directory,
            env=self._child_env(home),
            limit=_STDOUT_LINE_LIMIT,
        )
        await self._await_frame(lambda frame: frame.get("type") == "ready", "the ready frame")

    async def _record_what_loaded(self) -> None:
        """Ask the running session what it got, and keep the answer.

        `get_available_commands` is answered from the session's own registry and
        calls no model, so this costs nothing. The `skill:<name>` commands it
        reports are the skills Omp actually discovered — the evidence that
        separates a red arm from an arm whose plugin never arrived.
        """
        commands = await self._request("get_available_commands")
        names = [str(entry.get("name") or "") for entry in commands.get("commands", [])]
        self._loaded_commands = sorted(name for name in names if name)
        self._loaded_skills = sorted(
            name.split(":", 1)[1] for name in self._loaded_commands if name.startswith("skill:")
        )
        if self.config.plugins and not self._loaded_skills:
            raise RuntimeError(
                "omp: the session offers no skill commands, so the plugin's skills did not load; "
                "the arm would measure an untreated session and report zeros"
            )

        state = await self._request("get_state")
        session_id = state.get("sessionId")
        if isinstance(session_id, str):
            self._session_id = session_id

    async def _apply_model(self) -> None:
        """Pin the session's model, where the task named one.

        Omp's `set_model` takes the provider and the model id separately, so
        `provider/modelId` is split on the first slash. A bare name is sent as
        the model id alone and Omp resolves the provider.
        """
        if not self.config.model:
            return
        provider, _, model_id = self.config.model.partition("/")
        command: dict[str, Any] = {"type": "set_model", "modelId": model_id or provider}
        if model_id:
            command["provider"] = provider
        await self._request_command(command)

    # --- rpc plumbing ------------------------------------------------------

    def _child_env(self, home: Path) -> dict[str, str]:
        """The child's environment: the caller's, pointed at the throwaway home.

        The PATH prepend is `Agent.start`'s mock-shadowing contract — the
        sandbox's mock CLI directories must resolve before the real binaries, or
        a task grading a mocked CLI silently exercises the real one.
        """
        env = dict(os.environ)
        if self._env_path_prepend:
            env["PATH"] = os.pathsep.join([*self._env_path_prepend, env.get("PATH", "")])
        env["HOME"] = str(home)
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            env[name] = str(home / name.lower())
        return env

    def _next_request_id(self) -> str:
        self._request_id += 1
        return f"coder-eval-omp-{self._request_id}"

    async def _send(self, command: dict[str, Any]) -> None:
        proc = self._process
        if proc is None or proc.stdin is None:
            raise RuntimeError("omp: the RPC process is not running")
        proc.stdin.write((json.dumps(command) + "\n").encode("utf-8"))
        await proc.stdin.drain()

    async def _request(self, command_type: str, **fields: Any) -> dict[str, Any]:
        """Send one command and return its `data`, raising on a failed response."""
        return await self._request_command({"type": command_type, **fields})

    async def _request_command(self, command: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_request_id()
        await self._send({**command, "id": request_id})
        frame = await self._await_frame(
            lambda candidate: candidate.get("type") == "response" and candidate.get("id") == request_id,
            f"the {command['type']} response",
        )
        if not frame.get("success"):
            raise RuntimeError(f"omp: {command['type']} failed: {frame.get('error')}")
        data = frame.get("data")
        return data if isinstance(data, dict) else {}

    async def _await_frame(self, matches: Callable[[dict[str, Any]], bool], what: str) -> dict[str, Any]:
        """Read frames until one matches, with a startup deadline on the whole wait."""
        proc = self._process
        if proc is None or proc.stdout is None:
            raise RuntimeError("omp: the RPC process is not running")
        deadline = time.monotonic() + _STARTUP_TIMEOUT_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"omp: timed out after {_STARTUP_TIMEOUT_SECONDS:.0f}s waiting for {what}")
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
            except (TimeoutError, asyncio.TimeoutError):
                raise RuntimeError(f"omp: timed out after {_STARTUP_TIMEOUT_SECONDS:.0f}s waiting for {what}") from None
            if not line:
                stderr = await _drain(proc.stderr)
                raise RuntimeError(f"omp: exited before {what}. stderr: {stderr.strip()}")
            frame = _parse(line)
            if frame is None:
                continue
            if frame.get("type") == "extension_error":
                self._extension_errors.append(
                    f"{frame.get('extensionPath')} on {frame.get('event')}: {frame.get('error')}"
                )
            if matches(frame):
                return frame

    async def _timeout_turn(self, finalize: Any, collector: EventCollector, timeout: float) -> NoReturn:
        """Abort the prompt, park the crashed partial record, raise the timeout.

        The capture is the load-bearing half. `discard_pending_turn` is the
        only route a failed turn's telemetry takes to the report, and it reads
        `pending_turn` — so a timeout that finalizes without capturing drops
        every tool call the turn made, and a row whose skill fired scores 0.0
        for want of the record rather than for want of the engagement.
        """
        with contextlib.suppress(Exception):
            await self._send({"id": self._next_request_id(), "type": "abort"})
        try:
            self._finalize_and_raise_timeout(finalize, timeout)
        finally:
            self._capture_partial_turn(collector)

    async def _abort_and_settle(self, reducer: TurnReducer, dispatch: Callable[[Any], bool]) -> None:
        """Stop the in-flight prompt, then read the stream back to a settled state.

        The session outlives the turn, so an `agent_end` still in flight would
        be read at the top of the NEXT turn and settle it before the model had
        said anything. The frames are fed to the reducer AND emitted, because
        the turn's record is built from emitted events, not from reducer state:
        a tool call that started before the stop and finished during the settle
        must still land in the frozen trajectory. Dropping it here is how an
        early-stopped replicate loses the very command its early-stop latched
        on — the live verdict saw the in-flight call, the final check saw an
        empty record, and every positive row scored 0 with the plugin provably
        loaded. Measured live, 2026-09-16, and the reason this emits.
        """
        with contextlib.suppress(Exception):
            await self._send({"id": self._next_request_id(), "type": "abort"})

        proc = self._process
        if proc is None or proc.stdout is None:
            return
        deadline = time.monotonic() + _TERM_GRACE_SECONDS
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("omp: the session did not settle within %.0fs of an abort", _TERM_GRACE_SECONDS)
                return
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=remaining)
            except (TimeoutError, asyncio.TimeoutError):
                logger.warning("omp: the session did not settle within %.0fs of an abort", _TERM_GRACE_SECONDS)
                return
            if not line:
                return
            frame = _parse(line)
            if frame is None:
                continue
            for action in reducer.feed(frame):
                if dispatch(action):
                    return

    def _crash(
        self,
        finalize: Any,
        collector: EventCollector,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        """Finalize the turn as crashed, park its telemetry, and raise."""
        self._capture_partial_turn(collector)
        self._finalize_and_raise_crash(finalize, message, cause=cause)


def _emit_tool_end(
    emit: Callable[[StreamEvent], None],
    task_id: str,
    turn_id: str,
    open_tools: dict[str, CommandTelemetry],
    finished: ToolFinished,
) -> None:
    """Close one tool call, inventing telemetry for a result with no call.

    A result with no matching start should not happen, and dropping it if it
    does would lose a tool call from every criterion that reads telemetry.
    """
    status = {
        "ok": ToolEndStatus.OK,
        "error": ToolEndStatus.ERROR,
        "unresolved": ToolEndStatus.UNRESOLVED,
    }.get(finished.status, ToolEndStatus.OK)
    telemetry = open_tools.pop(finished.call_id, None)
    if telemetry is None:
        telemetry = CommandTelemetry(
            tool_name="unknown",
            tool_id=finished.call_id,
            timestamp=datetime.now(),
        )
    completed = datetime.now()
    telemetry.execution_completed_at = completed
    if telemetry.execution_started_at is not None:
        telemetry.duration_ms = (completed - telemetry.execution_started_at).total_seconds() * 1000
    telemetry.result_status = _RESULT_STATUS[status]  # type: ignore[assignment]
    telemetry.result_summary = finished.summary
    telemetry.error_message = finished.error
    emit(ToolEndEvent(task_id=task_id, turn_id=turn_id, tool=telemetry, status=status))


def _parse(line: bytes) -> dict[str, Any] | None:
    """One stdout line as a frame, or None for blank and unparseable lines.

    Omp answers malformed input with a recoverable parse failure and keeps
    running, so a line this side cannot read is skipped for the same reason:
    one bad line must not end a turn that is otherwise healthy.
    """
    text = line.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    try:
        frame = json.loads(text)
    except json.JSONDecodeError:
        logger.debug("omp: unparseable stdout line: %.200s", text)
        return None
    return frame if isinstance(frame, dict) else None


async def _drain(stream: asyncio.StreamReader | None) -> str:
    """Whatever the process left on stderr, for a failure message."""
    if stream is None:
        return ""
    with contextlib.suppress(Exception):
        return (await stream.read()).decode("utf-8", errors="replace")
    return ""
