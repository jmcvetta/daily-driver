"""The ``codex-daily-driver`` agent kind: a driver for the installed Codex CLI.

The comparison this arm exists for is the **CLI**, not the Codex SDK. The SDK
and the app-server clients are a different execution path with their own
authentication and transport, so an SDK run cannot answer whether the shipped
tool behaves the same as Omp. This module therefore spawns::

    codex exec --json … -

one process per ``communicate()``, reads the documented JSON Lines stream, and
reduces it with :mod:`coder_eval_codex.events`. Session continuity across turns
is the CLI's own ``exec resume <thread_id>``.

Evidence is recorded, not assumed. ``start()`` asks the installed binary for its
version, its login status, and its model catalog, then fails closed when the
answer contradicts the arm:

* no ``codex`` on ``PATH`` is a configuration error naming the install route;
* API-key environment variables are refused, because the authorized route is
  the Codex subscription and an API key would silently bill a different meter;
* a login that is absent, unrecognized, or a plain API key is refused rather
  than discovered after the first paid turn;
* a requested model the catalog does not list is refused, instead of being
  replaced by a guessed identity or a provider default.

Subscription runs record tokens but never a fabricated cash cost: the CLI
reports no charge for subscription allowance, and coder_eval's rate card is a
list price, not a bill.

Skills are placed where the CLI scans for them — ``.agents/skills`` in the
working directory, with symlinks the CLI follows — by
:mod:`coder_eval_codex.skills`; see that module for the relative-root defect
this replaces.

Not supported, and logged rather than pretended: ``system_prompt`` and
``system_prompt_file`` have no ``codex exec`` flag, and
``allowed_tools``/``disallowed_tools`` are not an enforceable CLI surface. The
trust boundary is the eval sandbox plus the CLI's own sandbox mode.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal, NoReturn

from coder_eval.agent import Agent
from coder_eval.errors import AgentConfigError, AgentCrashError, TurnTimeoutError
from coder_eval.isolation.docker_runner import STDOUT_LINE_LIMIT_BYTES
from coder_eval.models import (
    AgentState,
    ApiRoute,
    AssistantMessage,
    BaseAgentConfig,
    CommandTelemetry,
    ContentBlock,
    PermissionMode,
    ResultSummary,
    SystemPromptSemantics,
    TokenUsage,
    TranscriptMessage,
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

from .discovery import classify_auth, model_slugs
from .events import Event, Item, TokenCounts, TurnAccumulator, token_counts, token_delta
from .skills import SkillLinkError, link_skills
from .transcript import is_already_tagged, render_agent_output


logger = logging.getLogger(__name__)

#: The kind string this agent registers under, and the value an experiment's
#: ``agent: {type: …}`` carries.
AGENT_KIND = "codex-daily-driver"

# Grace between SIGTERM and SIGKILL when tearing down the CLI subprocess.
_TERM_GRACE_SECONDS = 5.0
# How long to drain stderr after the process is reaped.
_DRAIN_SECONDS = 2.0
_SIGKILL: signal.Signals = getattr(signal, "SIGKILL", signal.SIGTERM)

# Config fields the CLI has no equivalent knob for.
_UNSUPPORTED_CONFIG_FIELDS: tuple[str, ...] = (
    "system_prompt",
    "system_prompt_file",
    "allowed_tools",
    "disallowed_tools",
)

# Environment variables that would route the CLI to metered API billing. The
# authorized route is the subscription; refuse rather than silently spend.
_METERED_AUTH_ENV: tuple[str, ...] = ("CODEX_API_KEY", "OPENAI_API_KEY")

# Native Codex tool item types -> the canonical (Claude) vocabulary every
# criterion is written against.
_TOOL_ITEM_NAMES: dict[str, str] = {
    "command_execution": "Bash",
    "file_change": "Write",
    "mcp_tool_call": "Mcp",
    "web_search": "WebSearch",
    "image_generation": "ImageGeneration",
    "image_view": "ImageView",
    "collab_agent_tool_call": "Agent",
    "dynamic_tool_call": "Tool",
}


class CodexCLIAgentConfig(BaseAgentConfig):
    """Configuration for the ``codex-daily-driver`` kind."""

    type: Literal["codex-daily-driver"]  # type: ignore[assignment]

    #: Reasoning effort passed as ``model_reasoning_effort``. None leaves the
    #: model's own default, which is recorded as unreported rather than "high".
    effort: Literal["minimal", "low", "medium", "high", "xhigh", "max", "ultra"] | None = None
    #: The executable to drive. A name is resolved on PATH; a path is used as given.
    executable: str = "codex"
    #: Refuse API-key authentication. The arm is a subscription comparison.
    require_subscription_auth: bool = True
    #: Crash a clean turn that reported no token counts, instead of scoring it.
    require_token_telemetry: bool = True


def _usage(counts: TokenCounts) -> TokenUsage:
    """coder_eval's token record from the pure counts the reducer produced."""
    return TokenUsage(
        uncached_input_tokens=counts.uncached_input_tokens,
        output_tokens=counts.output_tokens,
        cache_creation_input_tokens=counts.cache_creation_input_tokens,
        cache_read_input_tokens=counts.cache_read_input_tokens,
    )


class _CodexTurnState:
    """Per-``communicate()`` reducer output, assembled into a ``TurnRecord``."""

    def __init__(self, *, task_id: str, iteration: int, user_input: str, model: str | None) -> None:
        self.task_id = task_id
        self.iteration = iteration
        self.user_input = user_input
        self.model = model
        self.started_at = time.monotonic()
        self.thread_id: str | None = None
        self.turn_id = ""
        self.turn_open = False
        self.turn_count = 0
        self.turns_completed = 0
        self.max_turns_exhausted = False
        self.messages: list[TranscriptMessage] = []
        self.text_parts: list[str] = []
        self.open_tools: dict[str, CommandTelemetry] = {}
        self.sequence = 0
        self.failure: str | None = None
        self.errors: list[str] = []
        self.recognized = 0
        self.unrecognized_types: set[str] = set()
        self.finalized = False
        self._turn_started_at: datetime | None = None
        self._turn_text: list[str] = []
        self._turn_thinking: list[str] = []
        self._turn_tool_ids: list[str] = []
        self._previous_usage = TurnAccumulator().usage
        self._emit: Callable[[StreamEvent], None] = lambda _e: None

    def bind(self, emit: Callable[[StreamEvent], None]) -> None:
        self._emit = emit

    def emit(self, event: StreamEvent) -> None:
        self._emit(event)

    @property
    def agent_output(self) -> str:
        return "".join(self.text_parts)

    def _open_turn(self) -> None:
        self.turn_count += 1
        self.turn_open = True
        self.turn_id = f"{self.thread_id or self.task_id}:turn{self.turn_count}"
        self._turn_started_at = datetime.now()
        self._turn_text = []
        self._turn_thinking = []
        self._turn_tool_ids = []
        self.emit(
            TurnStartEvent(
                task_id=self.task_id,
                thread_id=self.thread_id,
                turn_id=self.turn_id,
                model=self.model,
            )
        )

    def _close_turn(self, *, status: TurnEndStatus = TurnEndStatus.COMPLETED, tokens: TokenUsage | None = None) -> None:
        if not self.turn_open:
            return
        self.turn_open = False
        started = self._turn_started_at or datetime.now()
        completed = datetime.now()
        blocks: list[ContentBlock] = []
        if self._turn_text:
            blocks.append(ContentBlock(block_type="text", sequence=0, text="".join(self._turn_text)))
        if self._turn_thinking:
            blocks.append(
                ContentBlock(block_type="thinking", sequence=len(blocks), thinking="\n".join(self._turn_thinking))
            )
        for tool_id in self._turn_tool_ids:
            blocks.append(ContentBlock(block_type="tool_use", sequence=len(blocks), tool_use_id=tool_id))
        self.messages.append(
            AssistantMessage(
                started_at=started,
                completed_at=completed,
                generation_duration_ms=(completed - started).total_seconds() * 1000,
                content_blocks=blocks,
                tool_use_ids=list(self._turn_tool_ids),
                input_tokens=tokens.uncached_input_tokens if tokens else 0,
                output_tokens=tokens.output_tokens if tokens else 0,
                cache_read_tokens=tokens.cache_read_input_tokens if tokens else 0,
                model=self.model,
            )
        )
        self.emit(
            TurnEndEvent(
                task_id=self.task_id,
                thread_id=self.thread_id,
                turn_id=self.turn_id,
                status=status,
                tokens=tokens,
            )
        )

    def on_text(self, item: Item) -> None:
        if not item.text:
            return
        self.text_parts.append(item.text)
        self._turn_text.append(item.text)
        self.emit(TextChunkEvent(task_id=self.task_id, thread_id=self.thread_id, turn_id=self.turn_id, text=item.text))

    def on_thinking(self, item: Item) -> None:
        if item.text:
            self._turn_thinking.append(item.text)

    def on_tool(self, item: Item, *, completed: bool) -> None:
        tool_name = _TOOL_ITEM_NAMES.get(item.type, item.type)
        tool_id = item.id or f"{tool_name.lower()}_{self.sequence + 1}"
        self.sequence += 1

        params: dict[str, Any] = {}
        summary: str | None = None
        if tool_name == "Bash":
            if item.command:
                params["command"] = item.command
                summary = item.command
        elif tool_name == "Write":
            paths = [str(change.get("path")) for change in item.changes if change.get("path")]
            if paths:
                params["file_path"] = paths[0]
            summary = ", ".join(paths) or None
        elif tool_name == "Mcp":
            params = {
                key: value
                for key, value in (("server", item.server), ("tool", item.tool), ("arguments", item.arguments))
                if value is not None
            }
        elif tool_name == "WebSearch" and item.query:
            params["query"] = item.query

        status: Literal["success", "error", "unknown"] = "unknown"
        if completed:
            if item.status in {"completed", "success"} or item.exit_code == 0:
                status = "success"
            elif item.status in {"failed", "error"} or (item.exit_code is not None and item.exit_code != 0):
                status = "error"

        telemetry = CommandTelemetry(
            tool_name=tool_name,
            tool_id=tool_id,
            timestamp=datetime.now(),
            parameters=params,
            result_status=status if completed else None,
            result_summary=summary,
        )
        if tool_id not in self.open_tools:
            self.emit(ToolStartEvent(task_id=self.task_id, thread_id=self.thread_id, turn_id=self.turn_id, tool=telemetry))
            self._turn_tool_ids.append(tool_id)
        if completed:
            self.open_tools.pop(tool_id, None)
            self.emit(
                ToolEndEvent(
                    task_id=self.task_id,
                    thread_id=self.thread_id,
                    turn_id=self.turn_id,
                    tool=telemetry,
                    status=ToolEndStatus.OK if status == "success" else ToolEndStatus.ERROR,
                )
            )
        else:
            self.open_tools[tool_id] = telemetry

    def on_turn_completed(self, usage: Any) -> None:
        self.turns_completed += 1
        delta = _usage(token_delta(usage, self._previous_usage))
        self._previous_usage = usage
        self._close_turn(tokens=delta)

    def close_open_tools(self) -> None:
        for tool_id, telemetry in list(self.open_tools.items()):
            self.open_tools.pop(tool_id, None)
            self.emit(
                ToolEndEvent(
                    task_id=self.task_id,
                    thread_id=self.thread_id,
                    turn_id=self.turn_id,
                    tool=telemetry,
                    status=ToolEndStatus.UNRESOLVED,
                )
            )

    def finalize(
        self,
        status: AgentEndStatus,
        *,
        usage: TokenUsage,
        model_used: str | None,
        crashed: bool = False,
        crash_reason: str | None = None,
    ) -> None:
        """Close orphans, close an open turn, and emit exactly one terminal event."""
        if self.finalized:
            return
        self.finalized = True
        self.close_open_tools()
        if self.turn_open:
            self._close_turn(status=TurnEndStatus(status.value))  # type: ignore[arg-type]
        self.emit(
            AgentEndEvent(
                task_id=self.task_id,
                thread_id=self.thread_id,
                status=status,
                usage=usage,
                iteration=self.iteration,
                user_input=self.user_input,
                agent_output=self.agent_output,
                model_used=model_used,
                assistant_turn_count=len(self.messages),
                messages=list(self.messages),
                num_turns=self.turn_count,
                max_turns_exhausted=self.max_turns_exhausted,
                result_summary=ResultSummary(
                    is_error=crashed,
                    subtype=status.value,
                    stop_reason=None,
                    result=crash_reason or self.failure or ("; ".join(self.errors[-3:]) if self.errors else None),
                ),
                crashed=crashed,
                crash_reason=crash_reason,
                duration_seconds=time.monotonic() - self.started_at,
            )
        )


class CodexCLIAgent(Agent[CodexCLIAgentConfig]):
    """Drives the installed ``codex`` executable, one process per turn."""

    supports_cooperative_stop: ClassVar[bool] = True
    #: The CLI has no system-prompt flag; the regime is genuinely unknown.
    system_prompt_semantics: ClassVar[SystemPromptSemantics] = "unknown"

    def __init__(
        self,
        config: CodexCLIAgentConfig,
        route: ApiRoute | None = None,
        *,
        task_id: str = "unknown",
    ) -> None:
        self.config = config
        self.route = route
        self.task_id = task_id
        self.working_directory: str | None = None
        self._env_path_prepend: list[str] = []
        self._plugin_tools_dir: str | None = None
        self._thread_id: str | None = None
        self._skills: list[str] = []
        self._version: str | None = None
        self._auth_mode: str = "unknown"
        self._login_status: str = "unreported"
        self._catalog_checked = False
        self._process: asyncio.subprocess.Process | None = None
        self._spawned_pgids: list[int] = []
        self._state = AgentState.WORKING

    # --- probes -----------------------------------------------------------

    def _run_probe(self, argv: list[str], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=self._build_env(),
            check=False,
        )

    def _probe_identity(self) -> None:
        """Record the binary, its auth mode and its catalog; fail closed on a gap."""
        executable = self.config.executable
        env = self._build_env()
        if shutil.which(executable, path=env.get("PATH")) is None and not Path(executable).is_file():
            raise AgentConfigError(
                f"The Codex CLI {executable!r} was not found on PATH. Install the current CLI "
                "(npm install -g @openai/codex) and authenticate the Codex subscription with `codex login`."
            )
        version = self._run_probe([executable, "--version"])
        self._version = (version.stdout or version.stderr).strip() or "unreported"

        login = self._run_probe([executable, "login", "status"])
        self._login_status = (login.stdout or login.stderr).strip() or "unreported"
        self._auth_mode = classify_auth(self._login_status)

        if self.config.require_subscription_auth:
            metered = [name for name in _METERED_AUTH_ENV if os.environ.get(name)]
            if metered:
                raise AgentConfigError(
                    f"{', '.join(metered)} is set. This arm measures the Codex subscription and must not "
                    "fall back to metered API billing; unset the variable and authenticate with `codex login`."
                )
            if self._auth_mode != "subscription":
                raise AgentConfigError(
                    f"The Codex CLI is not authenticated with a subscription ({self._login_status!r}). "
                    "Run `codex login` on the machine that runs the arm; the CLI comparison does not "
                    "accept an API key or an unverified login."
                )

        models_probe = self._run_probe([executable, "debug", "models"])
        slugs: list[str] = []
        if models_probe.returncode == 0:
            slugs = model_slugs(models_probe.stdout or "")
            self._catalog_checked = bool(slugs)
        if self.config.model and slugs and self.config.model not in slugs:
            raise AgentConfigError(
                f"The Codex CLI catalog does not list {self.config.model!r}; available: {', '.join(slugs)}. "
                "Fix the experiment pin rather than letting the CLI choose another model."
            )

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        if self._env_path_prepend:
            env["PATH"] = os.pathsep.join([*self._env_path_prepend, env.get("PATH", "")])
        if self._plugin_tools_dir and "PLUGIN_TOOLS_DIR" not in env:
            env["PLUGIN_TOOLS_DIR"] = self._plugin_tools_dir
        return env

    # --- lifecycle --------------------------------------------------------

    async def start(
        self,
        working_directory: str,
        *,
        env_path_prepend: list[str] | None = None,
        plugin_tools_dir: str | None = None,
    ) -> None:
        self.working_directory = working_directory
        self._env_path_prepend = list(env_path_prepend or [])
        self._plugin_tools_dir = plugin_tools_dir
        self._thread_id = None
        self._state = AgentState.WORKING

        ignored = [field for field in _UNSUPPORTED_CONFIG_FIELDS if getattr(self.config, field, None)]
        if ignored:
            logger.warning(
                "codex: %s set but NOT enforced — the CLI has no equivalent knob, so the run is "
                "unconstrained by them; do not rely on them as a boundary.",
                ", ".join(ignored),
            )

        self._probe_identity()
        try:
            self._skills = link_skills(
                self.config.plugins or [],
                base=Path.cwd(),
                workspace=Path(working_directory),
            )
        except SkillLinkError as exc:
            raise AgentConfigError(str(exc)) from exc

    async def stop(self) -> None:
        await self.kill()
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
        self._sweep_process_groups()

    def kill_sync(self) -> None:
        proc = self._process
        if proc is not None and proc.returncode is None:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(proc.pid, _SIGKILL)
        self._sweep_process_groups()

    def _sweep_process_groups(self) -> None:
        if os.name != "posix":
            return
        for pgid in self._spawned_pgids:
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(pgid, _SIGKILL)
        self._spawned_pgids.clear()

    def get_environment_info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "codex_cli_version": self._version or "unreported",
            "codex_auth_mode": self._auth_mode,
            "codex_login_status": self._login_status,
            "codex_model_requested": self.config.model,
            "codex_effort_requested": self.config.effort,
            "codex_model_catalog_checked": self._catalog_checked,
            "codex_skills_linked": list(self._skills),
            # Subscription allowance is not cash; the recorder keeps the two apart.
            "codex_billing_source": "subscription" if self._auth_mode == "subscription" else "unreported",
        }
        return info

    # --- command construction --------------------------------------------

    def _sandbox_mode(self) -> str:
        return "read-only" if self.config.permission_mode is PermissionMode.PLAN else "workspace-write"

    def _shared_args(self) -> list[str]:
        argv = [
            self.config.executable,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-c",
            'approval_policy="never"',
            "-c",
            f'sandbox_mode="{self._sandbox_mode()}"',
        ]
        if self.config.model:
            argv += ["-m", self.config.model]
        if self.config.effort:
            argv += ["-c", f'model_reasoning_effort="{self.config.effort}"']
        return argv

    def _build_argv(self) -> list[str]:
        argv = self._shared_args()
        if self._thread_id:
            # Resume keeps the session's working directory and history; the
            # prompt arrives on stdin, so no argument can be mistaken for a flag.
            argv += ["resume", self._thread_id, "-"]
        else:
            argv += ["-C", self.working_directory or ".", "-"]
        return argv

    # --- the turn ---------------------------------------------------------

    async def communicate(
        self,
        user_input: str,
        *,
        stream_callback: StreamCallback | None = None,
        timeout: float | None = None,
        max_turns: int | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> TurnRecord:
        if self.working_directory is None:
            raise RuntimeError("CodexCLIAgent.start() must be called before communicate()")

        self._begin_turn()
        collector = EventCollector()

        def emit(event: StreamEvent) -> None:
            collector.on_event(event)
            if stream_callback is not None:
                safe_emit(stream_callback, event)

        state = _CodexTurnState(
            task_id=self.task_id,
            iteration=self._iteration,
            user_input=user_input,
            model=self.config.model,
        )
        state.thread_id = self._thread_id
        state.bind(emit)
        emit(
            AgentStartEvent(
                task_id=self.task_id,
                prompt=user_input,
                iteration=self._iteration,
                model=self.config.model,
            )
        )

        accumulator = TurnAccumulator()
        deadline = None if timeout is None else time.monotonic() + timeout
        stopped_early = False
        stderr_drain: asyncio.Future[bytes] | None = None
        proc: asyncio.subprocess.Process | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._build_argv(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_directory,
                env=self._build_env(),
                limit=STDOUT_LINE_LIMIT_BYTES,
                start_new_session=os.name == "posix",
            )
            self._process = proc
            if os.name == "posix":
                self._spawned_pgids.append(proc.pid)
            assert proc.stdin is not None
            assert proc.stdout is not None

            proc.stdin.write(user_input.encode())
            await proc.stdin.drain()
            proc.stdin.close()
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                await proc.stdin.wait_closed()

            if proc.stderr is not None:
                stderr_drain = asyncio.ensure_future(proc.stderr.read())

            exit_waiter = asyncio.ensure_future(proc.wait())
            read_task: asyncio.Future[bytes] | None = None
            try:
                while True:
                    remaining = None if deadline is None else deadline - time.monotonic()
                    if remaining is not None and remaining <= 0:
                        await self._timeout_turn(state, collector, accumulator, timeout or 0.0)

                    if read_task is None:
                        read_task = asyncio.ensure_future(proc.stdout.readline())
                    done, _pending = await asyncio.wait(
                        {read_task, exit_waiter},
                        timeout=remaining,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        await self._timeout_turn(state, collector, accumulator, timeout or 0.0)
                    if not read_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(read_task), _DRAIN_SECONDS)
                        except TimeoutError:
                            break
                    line = read_task.result()
                    read_task = None
                    if not line:
                        break

                    for reduced in accumulator.feed_line(line.decode("utf-8", "replace")):
                        self._handle(reduced, state, accumulator)
                    if state.failure is not None:
                        await self.kill()
                        break
                    if max_turns is not None and state.turn_count > max_turns:
                        state.max_turns_exhausted = True
                        await self.kill()
                        break
                    if should_stop is not None and should_stop():
                        stopped_early = True
                        await self.kill()
                        break
            finally:
                if read_task is not None:
                    read_task.cancel()
                exit_waiter.cancel()

            status = await self._settle_turn(
                proc,
                state,
                collector,
                accumulator,
                stderr_drain,
                stopped_early=stopped_early,
                deadline=deadline,
                timeout=timeout,
            )
            usage = _usage(token_counts(accumulator.usage))
            state.finalize(
                status,
                usage=usage,
                model_used=accumulator.model_reported,
            )
            record = collector.build_turn_record()
            # The judge anchors on the [RESULT - …] transcript; the CLI emits a
            # bare agent message. Without this every judged row scores 0.0.
            if record.agent_output and not is_already_tagged(record.agent_output):
                record = record.model_copy(update={"agent_output": render_agent_output(record.agent_output)})
            self._end_turn_ok()
            return record

        except (AgentCrashError, TurnTimeoutError):
            raise
        except asyncio.CancelledError:
            state.finalize(
                AgentEndStatus.CRASHED,
                usage=_usage(token_counts(accumulator.usage)),
                model_used=accumulator.model_reported,
                crashed=True,
                crash_reason="turn cancelled",
            )
            self._capture_partial_turn(collector)
            raise
        except Exception as exc:
            self._crash_turn(state, collector, accumulator, f"Codex CLI turn failed: {exc!s}", cause=exc)
            raise
        finally:
            if stderr_drain is not None:
                stderr_drain.cancel()
            if proc is not None and proc.returncode is None:
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    proc.kill()
                self._sweep_process_groups()
            self._process = None

    def _handle(self, event: Event, state: _CodexTurnState, accumulator: TurnAccumulator) -> None:
        if event.kind == "thread_started":
            state.thread_id = event.value
            self._thread_id = event.value
        elif event.kind == "turn_started":
            state._open_turn()
        elif event.kind == "item_started":
            item = event.value
            if isinstance(item, Item) and item.type in _TOOL_ITEM_NAMES:
                state.on_tool(item, completed=False)
        elif event.kind == "item_completed":
            item = event.value
            if not isinstance(item, Item):
                return
            if item.type == "agent_message":
                state.on_text(item)
            elif item.type == "reasoning":
                state.on_thinking(item)
            elif item.type in _TOOL_ITEM_NAMES:
                state.on_tool(item, completed=True)
            elif item.type == "error":
                state.errors.append(item.text or "item error")
            else:
                if len(state.unrecognized_types) < 8:
                    state.unrecognized_types.add(item.type)
        elif event.kind == "turn_completed":
            state.on_turn_completed(accumulator.usage)
        elif event.kind == "turn_failed":
            state.failure = str(event.value)

        state.recognized = accumulator.recognized
        state.errors = accumulator.errors
        state.unrecognized_types = set(accumulator.unrecognized_types)

    async def _settle_turn(
        self,
        proc: asyncio.subprocess.Process,
        state: _CodexTurnState,
        collector: EventCollector,
        accumulator: TurnAccumulator,
        stderr_drain: asyncio.Future[bytes] | None,
        *,
        stopped_early: bool,
        deadline: float | None,
        timeout: float | None,
    ) -> AgentEndStatus:
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        try:
            await asyncio.wait_for(proc.wait(), timeout=_TERM_GRACE_SECONDS if remaining is None else remaining)
        except TimeoutError:
            if remaining is not None:
                await self._timeout_turn(state, collector, accumulator, timeout or 0.0)
            await self.kill()
            self._crash_turn(
                state,
                collector,
                accumulator,
                f"Codex CLI closed its event stream but did not exit within {_TERM_GRACE_SECONDS:.0f}s",
            )

        stderr_bytes = b""
        if stderr_drain is not None:
            with contextlib.suppress(TimeoutError):
                stderr_bytes = await asyncio.wait_for(asyncio.shield(stderr_drain), timeout=_DRAIN_SECONDS)

        if state.failure is not None:
            self._crash_turn(state, collector, accumulator, f"Codex CLI turn failed: {state.failure}")
        if proc.returncode not in (0, None) and not stopped_early and not state.max_turns_exhausted:
            detail = stderr_bytes.decode("utf-8", "replace").strip() or f"exit code {proc.returncode}"
            self._crash_turn(state, collector, accumulator, f"Codex CLI exited non-zero: {detail}")

        if stopped_early:
            return AgentEndStatus.STOPPED_EARLY
        if state.max_turns_exhausted:
            return AgentEndStatus.MAX_TURNS_EXHAUSTED

        if accumulator.turns_completed == 0:
            detail = "; ".join(accumulator.errors[-3:]) or "no turn.completed event"
            self._crash_turn(state, collector, accumulator, f"Codex CLI produced no completed turn ({detail})")

        usage = _usage(token_counts(accumulator.usage))
        if (
            self.config.require_token_telemetry
            and usage.uncached_input_tokens == 0
            and usage.cache_read_input_tokens == 0
            and usage.output_tokens == 0
        ):
            self._crash_turn(
                state,
                collector,
                accumulator,
                "Codex CLI completed a turn with no token counts. The event or usage schema may have "
                "changed; see evals/coder-eval-codex/events.py before trusting this CLI version.",
            )
        return AgentEndStatus.COMPLETED

    def _crash_turn(
        self,
        state: _CodexTurnState,
        collector: EventCollector | None,
        accumulator: TurnAccumulator,
        message: str,
        *,
        cause: BaseException | None = None,
    ) -> NoReturn:
        state.failure = state.failure or message
        self._state = AgentState.ERROR
        with contextlib.suppress(Exception):
            state.finalize(
                AgentEndStatus.CRASHED,
                usage=_usage(token_counts(accumulator.usage)),
                model_used=accumulator.model_reported,
                crashed=True,
                crash_reason=message,
            )
        if collector is not None:
            self._capture_partial_turn(collector)
        if cause is not None:
            raise AgentCrashError(message) from cause
        raise AgentCrashError(message)

    async def _timeout_turn(
        self,
        state: _CodexTurnState,
        collector: EventCollector | None,
        accumulator: TurnAccumulator,
        timeout: float,
    ) -> NoReturn:
        await self.kill()
        self._state = AgentState.ERROR
        state.finalize(
            AgentEndStatus.TIMEOUT,
            usage=_usage(token_counts(accumulator.usage)),
            model_used=accumulator.model_reported,
            crashed=True,
            crash_reason=f"turn exceeded {timeout:.0f}s",
        )
        if collector is not None:
            self._capture_partial_turn(collector)
        raise TurnTimeoutError(timeout, iteration=self._iteration)
