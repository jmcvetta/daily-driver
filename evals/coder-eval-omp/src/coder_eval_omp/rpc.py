"""The Omp RPC stream, reduced — with no `coder_eval` and no `omp` in sight.

Everything in this module is pure: frames in, small dataclasses out. That is
deliberate. The agent in `agent.py` cannot be exercised without a `coder_eval`
install and an `omp` binary, so anything load-bearing that lives there is
untested code. What is load-bearing is here instead, and
`scripts/check-omp-agent.py` drives it against recorded frames in `make check`.

Three things it owns, and each one is a silent zero if it is wrong:

**Skill engagement.** `coder_eval`'s `skill_triggered` criterion detects a skill
by the substring `skills/<name>/` in any tool parameter, or by a canonical
`Skill` tool call. Omp engages a skill by reading the URL `skill://<name>`,
which contains neither. Left alone, every positive row in the Omp arm scores 0
— indistinguishable from a plugin that never loaded. `canonical_tool_call`
maps that read to a `Skill` call, exactly as `coder_eval`'s own OpenCode agent
maps OpenCode's skill tool.

**Tool names.** `command_executed` criteria are written against Claude's
vocabulary. `TOOL_NAME_MAP` renames Omp's to it. An unmapped name passes
through unchanged rather than being dropped, so a new Omp tool shows up in the
report under its own name instead of vanishing.

**The reply the judge reads.** Every `llm_judge` rubric in `evals/tasks/`
anchors on the `[RESULT - …]` tag that `coder_eval`'s `format_messages` emits,
and scores 0.0 where the tag is missing — by design, so a drifted harness
cannot report a plausible number. `coder_eval` builds that transcript only for
its Claude Code agent; its OpenCode and Codex agents hand the judge bare text.
An Omp arm that did the same would score every judged row 0.0 in both arms.
`render_agent_output` emits the tagged shape instead, so one rubric reads the
same on both harnesses.

The protocol itself is Omp's `docs/rpc.md`. Where that document does not say
(the arguments on `tool_execution_start`, the token accounting on `agent_end`)
this module reads every spelling the payload might use and *records which one
it found*, in `argument_keys_seen` and `usage_keys_seen`. The first live run
therefore answers the question rather than guessing at it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# The URL scheme Omp exposes a skill under. A `read` of it is the engagement
# that `skill_triggered` must be able to see.
SKILL_URL_PREFIX = "skill://"

# Omp's tool names -> the canonical (Claude) vocabulary every criterion here is
# written against. Provisional: read from Omp's `get_state` tool registry and
# its docs rather than from a full run, which is why an unmapped name passes
# through unchanged instead of being renamed to a guess.
TOOL_NAME_MAP: dict[str, str] = {
    "read": "Read",
    "write": "Write",
    "edit": "Edit",
    "bash": "Bash",
    "task": "Agent",
    "glob": "Glob",
    "grep": "Grep",
    "list": "LS",
    "fetch": "WebFetch",
    "webfetch": "WebFetch",
    "todo": "TodoWrite",
    "todowrite": "TodoWrite",
}

# Per-canonical-tool argument key renames, Omp's spelling -> Claude's. Without
# these a `command_executed` criterion on a non-Bash tool matches against a
# differently-keyed JSON blob and scores differently per harness: the criterion
# falls back to `json.dumps(parameters)` for every tool but `Bash`. Keys not
# listed pass through.
ARG_RENAME: dict[str, dict[str, str]] = {
    # `url` is deliberately NOT renamed to `file_path`. Omp's `read` takes a
    # file path or a URL, and a URL is Claude's `WebFetch`, not its `Read` — a
    # rename here would make a fetched page read as a file in every report.
    "Read": {"path": "file_path", "filePath": "file_path"},
    "Write": {"path": "file_path", "filePath": "file_path", "content": "content"},
    "Edit": {
        "path": "file_path",
        "filePath": "file_path",
        "oldString": "old_string",
        "newString": "new_string",
        "replaceAll": "replace_all",
    },
    # `bash` already names its argument `command`, which is the key
    # `command_executed`'s shell-aware extraction reads.
}

# Where a tool call's input arguments might sit on a `tool_execution_*` frame.
# Omp's `docs/rpc.md` shows `toolName` on that frame and does not show the
# arguments; the authoritative types are in the TypeScript source. Every
# plausible spelling is read, and the one that answered is recorded, so a live
# run settles this instead of a guess doing it.
ARGUMENT_KEYS = ("arguments", "input", "args", "params", "parameters", "toolInput")

# Where a tool call's own name might sit, same reasoning.
TOOL_NAME_KEYS = ("toolName", "tool", "name")

# Where a tool call's correlation id might sit.
CALL_ID_KEYS = ("toolCallId", "callId", "toolCallID", "id")

# Token counts, by the spellings a payload might use, mapped to the buckets
# `coder_eval`'s `TokenUsage` keeps. `docs/rpc.md` places per-turn accounting in
# "telemetry fields on `agent_end`" without naming them, so this reads both the
# camelCase and snake_case forms of each.
USAGE_KEYS: dict[str, tuple[str, ...]] = {
    "uncached_input_tokens": ("inputTokens", "input_tokens", "promptTokens", "prompt_tokens"),
    "output_tokens": ("outputTokens", "output_tokens", "completionTokens", "completion_tokens"),
    "cache_read_input_tokens": ("cacheReadTokens", "cache_read_tokens", "cachedTokens", "cached_tokens"),
    "cache_creation_input_tokens": ("cacheWriteTokens", "cache_write_tokens"),
}

# Sub-objects a usage payload might be nested under on `agent_end`.
USAGE_CONTAINERS = ("usage", "telemetry", "tokens", "stats", "tokenUsage")

# The frame types this module knows what to do with. A turn that recognized
# NONE of them captured no telemetry, and the agent crashes it rather than
# reporting a clean empty success — `coder_eval`'s OpenCode agent learned that
# the expensive way, scoring SUCCESS 1.0 on zero turns and zero tokens when it
# parsed the wrong vocabulary.
RECOGNIZED_FRAMES = frozenset(
    {
        "agent_start",
        "agent_end",
        "turn_start",
        "turn_end",
        "message_start",
        "message_update",
        "message_end",
        "tool_execution_start",
        "tool_execution_update",
        "tool_execution_end",
    }
)


@dataclass
class Text:
    """Assistant text, as it arrived — a streamed delta or a whole message."""

    text: str


@dataclass
class TurnStarted:
    """One inner turn of the agent's loop opened."""

    turn_id: str


@dataclass
class TurnFinished:
    """The inner turn named by `turn_id` closed."""

    turn_id: str


@dataclass
class ToolStarted:
    """A tool call began, named and keyed in the canonical vocabulary.

    `raw_tool_name` keeps Omp's own name so a report can say what was renamed.
    """

    call_id: str
    tool_name: str
    parameters: dict[str, Any]
    raw_tool_name: str


@dataclass
class ToolFinished:
    """A tool call ended. `status` is one of `ok`, `error` or `unresolved`."""

    call_id: str
    status: str
    summary: str | None = None
    error: str | None = None


@dataclass
class AgentFinished:
    """The agent settled. `terminal` is false while more work is scheduled.

    Omp sets `isTerminal: false` when maintenance or async delivery will resume
    the session, so a turn is complete only where this is true.
    """

    terminal: bool
    usage: dict[str, int]


@dataclass
class ExtensionFailed:
    """An extension handler raised. Carries Omp's own `extension_error` frame.

    The Omp arm loads this repository's constitution and session tools as an
    extension, so this frame is the difference between a red arm and an arm
    that never had the plugin.
    """

    extension_path: str
    event: str
    error: str


#: Everything `TurnReducer.feed` can return, in one name.
Action = Text | TurnStarted | TurnFinished | ToolStarted | ToolFinished | AgentFinished | ExtensionFailed


def skill_name_from_url(url: str) -> str | None:
    """The skill named by a `skill://<name>` URL, or None for any other string.

    `skill://pr-title` and `skill://pr-title/references/omp.md` both name
    `pr-title`: Omp reads a skill's own files through the same scheme, and both
    reads are the skill being engaged.
    """
    if not isinstance(url, str) or not url.startswith(SKILL_URL_PREFIX):
        return None
    rest = url[len(SKILL_URL_PREFIX) :].strip()
    name = rest.split("/", 1)[0].strip()
    return name or None


def canonical_tool_call(raw_tool_name: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Rename one Omp tool call into the vocabulary the criteria are written in.

    Returns the canonical tool name and its canonically-keyed parameters. A
    `read` of a `skill://<name>` URL becomes `Skill` with `{"skill": name}`,
    which is what `skill_triggered` looks for; every other call keeps its own
    shape with its name and argument keys renamed where a rename is known.
    """
    raw = (raw_tool_name or "unknown").strip()
    canonical = TOOL_NAME_MAP.get(raw.lower(), raw)

    if canonical == "Read":
        for key in ("url", "path", "filePath", "file_path", "target"):
            skill = skill_name_from_url(arguments.get(key, ""))
            if skill is not None:
                return "Skill", {"skill": skill}

    renames = ARG_RENAME.get(canonical, {})
    parameters = {renames.get(key, key): value for key, value in arguments.items()}
    return canonical, parameters


def extract_arguments(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """The tool input arguments on a frame, and the key they were found under.

    Returns `({}, None)` when the frame carries none — which is not an error on
    a `tool_execution_start`, because Omp may complete the arguments in a later
    `tool_execution_update` frame.
    """
    for key in ARGUMENT_KEYS:
        value = payload.get(key)
        if isinstance(value, dict) and value:
            return dict(value), key
    return {}, None


def extract_usage(payload: dict[str, Any]) -> tuple[dict[str, int], list[str]]:
    """Token counts from an `agent_end` payload, and the keys they came from.

    Reads the payload itself and every container in `USAGE_CONTAINERS`, so a
    count nested under `telemetry` is found as readily as one at the top level.
    An empty result means the frame carried no counts — the caller decides
    whether that fails the turn.
    """
    found: dict[str, int] = {}
    seen: list[str] = []
    sources = [payload]
    for container in USAGE_CONTAINERS:
        value = payload.get(container)
        if isinstance(value, dict):
            sources.append(value)

    for source in sources:
        for bucket, spellings in USAGE_KEYS.items():
            if bucket in found:
                continue
            for spelling in spellings:
                value = source.get(spelling)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                found[bucket] = int(value)
                seen.append(spelling)
                break
    return found, seen


def render_agent_output(assistant_texts: list[str], *, is_error: bool = False) -> str:
    """The turn transcript in the shape every `llm_judge` rubric here anchors on.

    `coder_eval`'s `format_messages` renders a Claude turn as `[ASSISTANT] …`
    blocks followed by one `[RESULT - SUCCESS] …` carrying the reply. The
    rubrics under `evals/tasks/` locate the reply at the last `[RESULT - …]`
    tag and score 0.0 where there is none, deliberately and with no fallback.
    So the Omp arm emits the same shape: the blocks, then the final block
    repeated under the result tag.

    An empty turn renders `[No output]`, which is what `format_messages`
    returns for one, so a judge sees the same thing on both harnesses.
    """
    blocks = [text for text in assistant_texts if text and text.strip()]
    if not blocks:
        return "[No output]"
    status = "ERROR" if is_error else "SUCCESS"
    parts = [f"[ASSISTANT] {text}" for text in blocks]
    parts.append(f"[RESULT - {status}] {blocks[-1]}")
    return "\n".join(parts)


class TurnReducer:
    """One `prompt` command's worth of Omp frames, reduced to actions.

    Feed it every stdout frame of a turn. It returns the actions each frame
    implies and accumulates what the turn's record needs: the assistant text,
    the open tool calls, the vocabulary it recognized, and the argument and
    usage key spellings it actually saw.

    It never raises on a malformed frame. A frame it cannot read is counted in
    `unrecognized_types`, and the agent decides what an unrecognized stream
    means — which is a crash, not a zero.
    """

    def __init__(self) -> None:
        self.assistant_texts: list[str] = []
        self.open_tools: dict[str, ToolStarted] = {}
        self.tool_calls: list[ToolStarted] = []
        self.recognized = 0
        self.unrecognized_types: set[str] = set()
        self.argument_keys_seen: set[str] = set()
        self.usage_keys_seen: set[str] = set()
        self.extension_errors: list[ExtensionFailed] = []
        self.error_message: str | None = None
        self.usage: dict[str, int] = {}
        self.terminal_end_seen = False
        self.turn_count = 0
        self._message_texts: dict[str, list[str]] = {}
        self._open_turn_ids: list[str] = []
        self._sequence = 0
        self.started_at = time.monotonic()

    # --- feeding -----------------------------------------------------------

    def feed(self, frame: dict[str, Any]) -> list[Action]:
        """Reduce one frame, returning the actions it implies (often none)."""
        if not isinstance(frame, dict):
            self.unrecognized_types.add("<not an object>")
            return []

        kind = str(frame.get("type") or "")
        if kind in RECOGNIZED_FRAMES:
            self.recognized += 1

        handler = {
            "turn_start": self._on_turn_start,
            "turn_end": self._on_turn_end,
            "message_update": self._on_message,
            "message_end": self._on_message,
            "tool_execution_start": self._on_tool_start,
            "tool_execution_update": self._on_tool_update,
            "tool_execution_end": self._on_tool_end,
            "agent_end": self._on_agent_end,
            "extension_error": self._on_extension_error,
        }.get(kind)

        if handler is None:
            # `ready`, `response`, `agent_start`, `message_start` and the
            # maintenance frames are all legitimate and imply no action. Only a
            # type outside the whole known vocabulary is drift worth reporting.
            if kind and kind not in RECOGNIZED_FRAMES and kind not in _SILENT_FRAMES:
                self.unrecognized_types.add(kind)
            return []
        return handler(frame)

    # --- handlers ----------------------------------------------------------

    def _on_turn_start(self, frame: dict[str, Any]) -> list[Action]:
        self.turn_count += 1
        turn_id = str(frame.get("turnId") or frame.get("id") or f"turn_{self.turn_count}")
        self._open_turn_ids.append(turn_id)
        return [TurnStarted(turn_id=turn_id)]

    def _on_turn_end(self, frame: dict[str, Any]) -> list[Action]:
        turn_id = str(frame.get("turnId") or frame.get("id") or "")
        if not turn_id:
            turn_id = self._open_turn_ids[-1] if self._open_turn_ids else f"turn_{self.turn_count}"
        if turn_id in self._open_turn_ids:
            self._open_turn_ids.remove(turn_id)
        return [TurnFinished(turn_id=turn_id)]

    def _on_message(self, frame: dict[str, Any]) -> list[Action]:
        """Assistant text, from a streamed delta or from a completed message.

        Omp streams deltas in `assistantMessageEvent` and may repeat the whole
        message on `message_end`. Both are keyed by message id, and a completed
        message REPLACES the deltas collected for that id — otherwise the reply
        is counted twice and every length rubric reads double.
        """
        message_id = str(frame.get("messageId") or frame.get("messageID") or frame.get("id") or "message")
        complete = _text_of(frame.get("message"))
        if complete:
            already = "".join(self._message_texts.get(message_id, []))
            self._message_texts[message_id] = [complete]
            self._resync_texts()
            # The deltas for this message are already in the stream. Re-emitting
            # the whole message would show the reply twice to every renderer.
            if already:
                return []
            return [Text(text=complete)]

        event = frame.get("assistantMessageEvent")
        delta = _text_of(event) if isinstance(event, dict) else None
        if not delta:
            delta = _text_of(frame)
        if not delta:
            return []
        self._message_texts.setdefault(message_id, []).append(delta)
        self._resync_texts()
        return [Text(text=delta)]

    def _on_tool_start(self, frame: dict[str, Any]) -> list[Action]:
        call_id = self._call_id(frame)
        raw_name = _first_string(frame, TOOL_NAME_KEYS) or "unknown"
        arguments, key = extract_arguments(frame)
        if key:
            self.argument_keys_seen.add(key)
        tool_name, parameters = canonical_tool_call(raw_name, arguments)
        started = ToolStarted(
            call_id=call_id,
            tool_name=tool_name,
            parameters=parameters,
            raw_tool_name=raw_name,
        )
        self.open_tools[call_id] = started
        self.tool_calls.append(started)
        return [started]

    def _on_tool_update(self, frame: dict[str, Any]) -> list[Action]:
        """Later evidence wins; absent evidence never clears what is held.

        A `tool_execution_start` routinely carries no arguments — the runtime
        has not finished assembling the call. Freezing that empty view would
        leave `parameters` `{}` for the whole run and zero every
        `command_executed` row while the report looked healthy.
        """
        call_id = self._call_id(frame)
        started = self.open_tools.get(call_id)
        if started is None:
            return []
        arguments, key = extract_arguments(frame)
        if not arguments:
            return []
        self.argument_keys_seen.add(key or "")
        self.argument_keys_seen.discard("")
        raw_name = _first_string(frame, TOOL_NAME_KEYS) or started.raw_tool_name
        tool_name, parameters = canonical_tool_call(raw_name, arguments)
        started.raw_tool_name = raw_name
        started.tool_name = tool_name
        started.parameters = parameters
        return []

    def _on_tool_end(self, frame: dict[str, Any]) -> list[Action]:
        call_id = self._call_id(frame)
        self._on_tool_update(frame)
        self.open_tools.pop(call_id, None)
        error = frame.get("error")
        result = frame.get("result")
        summary = result if isinstance(result, str) else None
        if summary is None and isinstance(result, dict):
            summary = _text_of(result)
        is_error = bool(error) or bool(frame.get("isError"))
        return [
            ToolFinished(
                call_id=call_id,
                status="error" if is_error else "ok",
                summary=summary,
                error=str(error) if error else None,
            )
        ]

    def _on_agent_end(self, frame: dict[str, Any]) -> list[Action]:
        usage, seen = extract_usage(frame)
        self.usage_keys_seen.update(seen)
        if usage:
            self.usage = usage
        terminal = frame.get("isTerminal") is not False
        self.terminal_end_seen = self.terminal_end_seen or terminal
        return [AgentFinished(terminal=terminal, usage=usage)]

    def _on_extension_error(self, frame: dict[str, Any]) -> list[Action]:
        failure = ExtensionFailed(
            extension_path=str(frame.get("extensionPath") or ""),
            event=str(frame.get("event") or ""),
            error=str(frame.get("error") or ""),
        )
        self.extension_errors.append(failure)
        return [failure]

    # --- closing -----------------------------------------------------------

    def close_open_tools(self) -> list[ToolFinished]:
        """Close every tool still awaiting a result, as `unresolved`.

        A turn that died mid-flight leaves tools open, and the event protocol
        requires every start to be closed.
        """
        closed = [
            ToolFinished(call_id=call_id, status="unresolved", error="no result observed")
            for call_id in list(self.open_tools)
        ]
        self.open_tools.clear()
        return closed

    def agent_output(self, *, is_error: bool = False) -> str:
        """The turn's transcript, in the judge-readable shape."""
        return render_agent_output(self.assistant_texts, is_error=is_error)

    # --- internals ---------------------------------------------------------

    def _resync_texts(self) -> None:
        self.assistant_texts = ["".join(parts) for parts in self._message_texts.values()]

    def _call_id(self, frame: dict[str, Any]) -> str:
        call_id = _first_string(frame, CALL_ID_KEYS)
        if call_id:
            return call_id
        self._sequence += 1
        return f"omp_call_{self._sequence}"


# Frames that are part of the protocol and imply no action here. Listed so that
# a type outside BOTH this set and `RECOGNIZED_FRAMES` is real drift rather
# than routine traffic, and reads as such in a crash message.
_SILENT_FRAMES = frozenset(
    {
        "ready",
        "response",
        "agent_start",
        "message_start",
        "available_commands_update",
        "auto_compaction_start",
        "auto_compaction_end",
        "auto_retry_start",
        "auto_retry_end",
        "retry_fallback_applied",
        "retry_fallback_succeeded",
        "model_changed",
        "thinking_level_changed",
        "ttsr_triggered",
        "todo_reminder",
        "todo_auto_clear",
        "irc_message",
        "notice",
        "goal_updated",
        "prompt_result",
        "command_output",
        "session_info_update",
        "config_update",
        "subagent_lifecycle",
        "subagent_progress",
        "subagent_event",
        "rpc_chunk",
    }
)


def _text_of(value: Any) -> str | None:
    """The text carried by a message-shaped payload, whatever it is keyed as.

    Handles the three shapes a message can take: a plain string, an object with
    a `text` or `delta` key, and an object with a `content` list of blocks.
    Thinking blocks are skipped — they are not the reply.
    """
    if isinstance(value, str):
        return value or None
    if not isinstance(value, dict):
        return None
    if str(value.get("type") or "").lower().startswith("thinking"):
        return None
    for key in ("text", "delta"):
        text = value.get(key)
        if isinstance(text, str) and text:
            return text
        if isinstance(text, dict):
            nested = _text_of(text)
            if nested:
                return nested
    content = value.get("content")
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        parts = [_text_of(block) for block in content]
        joined = "".join(part for part in parts if part)
        return joined or None
    return None


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """The first of `keys` holding a non-empty string, at the top level or one
    object deep under `tool` / `toolCall`."""
    sources: list[dict[str, Any]] = [payload]
    for container in ("tool", "toolCall"):
        value = payload.get(container)
        if isinstance(value, dict):
            sources.append(value)
    for source in sources:
        for key in keys:
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None
