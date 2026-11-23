"""Codex CLI JSON Lines events, reduced to plain values.

This module imports nothing. The agent cannot be exercised without an installed,
authenticated ``codex`` executable, so everything load-bearing about reading its
stream lives here where a test can drive it with recorded lines.

The vocabulary is the one ``codex exec --json`` documents and emits::

    {"type":"thread.started","thread_id":"…"}
    {"type":"turn.started"}
    {"type":"item.started","item":{"id":"…","type":"command_execution",…}}
    {"type":"item.completed","item":{"id":"…","type":"agent_message","text":"…"}}
    {"type":"turn.completed","usage":{"input_tokens":…,"cached_input_tokens":…,
                                     "output_tokens":…,"reasoning_output_tokens":…}}
    {"type":"turn.failed","error":{"message":"…"}}
    {"type":"error","message":"…"}

``error`` is not always fatal. A live run against a flaky transport emits
reconnect notices as ``error`` events and then completes, so this reducer
records them and only the agent decides whether a turn without
``turn.completed`` failed. ``turn.failed`` is always terminal.

Item types seen from the documented stream: ``agent_message``, ``reasoning``,
``command_execution``, ``file_change``, ``mcp_tool_call``, ``web_search``,
``plan`` and ``error``. Unknown types are preserved as raw items so a new CLI
version surfaces as telemetry rather than being silently dropped.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


#: Event kinds this reducer recognizes. The agent uses the set to detect a
#: stream whose vocabulary has moved.
EVENT_KINDS = frozenset(
    {
        "thread_started",
        "turn_started",
        "item_started",
        "item_completed",
        "turn_completed",
        "turn_failed",
        "error",
    }
)


@dataclass(frozen=True)
class Item:
    """One ``item.*`` payload, with the fields the eval criteria need."""

    id: str
    type: str
    status: str | None = None
    command: str | None = None
    exit_code: int | None = None
    text: str | None = None
    query: str | None = None
    server: str | None = None
    tool: str | None = None
    arguments: dict[str, Any] | None = None
    changes: tuple[dict[str, Any], ...] = ()
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    """The token buckets ``turn.completed`` reports.

    ``input_tokens`` is the whole prompt and includes the cached prefix, which
    is the same split coder_eval's ``TokenUsage`` documents for OpenAI.
    """

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0


@dataclass(frozen=True)
class TokenCounts:
    """coder_eval's three prompt buckets plus output, without importing it.

    ``uncached_input_tokens`` is the fresh slice; the cached prefix is
    ``cache_read_input_tokens``; OpenAI reports no separate cache write.
    Reasoning tokens are billed as output and are already folded in.
    """

    uncached_input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass(frozen=True)
class Event:
    """One reduced event. ``value`` is an Item, Usage, str or None."""

    kind: str
    value: Any = None


def token_counts(usage: Usage) -> TokenCounts:
    """Map the CLI's four buckets onto coder_eval's three plus output.

    ``input_tokens`` includes the cached prefix, so the fresh slice is the
    difference. Reasoning tokens are billed at the output rate and are folded
    into ``output_tokens``; the CLI reports them apart from ``output_tokens``.
    """
    cached = max(0, usage.cached_input_tokens)
    return TokenCounts(
        uncached_input_tokens=max(0, usage.input_tokens - cached),
        output_tokens=max(0, usage.output_tokens) + max(0, usage.reasoning_output_tokens),
        cache_creation_input_tokens=0,
        cache_read_input_tokens=cached,
    )


def token_delta(current: Usage, previous: Usage) -> TokenCounts:
    """The non-negative difference between two cumulative usage snapshots."""
    current_counts = token_counts(current)
    previous_counts = token_counts(previous)
    return TokenCounts(
        uncached_input_tokens=max(0, current_counts.uncached_input_tokens - previous_counts.uncached_input_tokens),
        output_tokens=max(0, current_counts.output_tokens - previous_counts.output_tokens),
        cache_creation_input_tokens=0,
        cache_read_input_tokens=max(0, current_counts.cache_read_input_tokens - previous_counts.cache_read_input_tokens),
    )


def tool_status(item: Item, *, completed: bool) -> str:
    """Classify one tool item's result: success, error or unknown.

    Exit code arbitrates when the CLI reports one, because a `command_execution`
    can carry `status: completed` for a shell command that exited non-zero. The
    status string is the fallback for tools that have no exit code (file
    changes, MCP calls, searches).
    """
    if not completed:
        return "unknown"
    if item.exit_code is not None:
        return "success" if item.exit_code == 0 else "error"
    if item.status in {"completed", "success"}:
        return "success"
    if item.status in {"failed", "error"}:
        return "error"
    return "unknown"


def _int(value: Any) -> int:
    """Coerce a reported token count. Anything unusable is 0, never a guess."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float) and value.is_integer():
        return max(0, int(value))
    return 0


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _item(payload: Any) -> Item | None:
    if not isinstance(payload, dict):
        return None
    item_type = _str(payload.get("type")) or "unknown"
    changes = payload.get("changes")
    changes = changes if isinstance(changes, list) else []
    arguments = payload.get("arguments")
    arguments = arguments if isinstance(arguments, dict) else None
    exit_code = payload.get("exit_code")
    return Item(
        id=_str(payload.get("id")) or "",
        type=item_type,
        status=_str(payload.get("status")),
        command=_str(payload.get("command")),
        exit_code=exit_code if isinstance(exit_code, int) else None,
        text=_str(payload.get("text")),
        query=_str(payload.get("query")),
        server=_str(payload.get("server")),
        tool=_str(payload.get("tool")),
        arguments=arguments,
        changes=tuple(c for c in changes if isinstance(c, dict)),
        raw=payload,
    )


@dataclass
class TurnAccumulator:
    """Everything one ``codex exec`` stream said, in order."""

    thread_id: str | None = None
    model_reported: str | None = None
    turns_started: int = 0
    turns_completed: int = 0
    usage: Usage = field(default_factory=Usage)
    events: list[Event] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failure: str | None = None
    recognized: int = 0
    unrecognized_types: set[str] = field(default_factory=set)

    def feed_line(self, line: str) -> list[Event]:
        """Reduce one stdout line. Malformed or non-JSON lines are ignored."""
        raw = line.strip()
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        if not isinstance(payload, dict):
            return []
        return self.feed(payload)

    def feed(self, payload: dict[str, Any]) -> list[Event]:
        """Reduce one decoded event object and return the events it produced."""
        kind = _str(payload.get("type")) or ""
        produced: list[Event] = []

        if kind == "thread.started":
            self.thread_id = _str(payload.get("thread_id")) or self.thread_id
            produced.append(Event("thread_started", self.thread_id))
        elif kind == "turn.started":
            self.turns_started += 1
            produced.append(Event("turn_started"))
        elif kind in {"item.started", "item.completed"}:
            item = _item(payload.get("item"))
            if item is not None:
                produced.append(Event(kind.replace(".", "_"), item))
        elif kind == "turn.completed":
            usage = payload.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            self.turns_completed += 1
            self.usage = Usage(
                input_tokens=self.usage.input_tokens + _int(usage.get("input_tokens")),
                cached_input_tokens=self.usage.cached_input_tokens + _int(usage.get("cached_input_tokens")),
                output_tokens=self.usage.output_tokens + _int(usage.get("output_tokens")),
                reasoning_output_tokens=self.usage.reasoning_output_tokens
                + _int(usage.get("reasoning_output_tokens")),
            )
            self.model_reported = _str(payload.get("model")) or self.model_reported
            produced.append(Event("turn_completed", self.usage))
        elif kind == "turn.failed":
            error = payload.get("error")
            message = (error or {}).get("message") if isinstance(error, dict) else error
            self.failure = str(message or "turn failed")
            produced.append(Event("turn_failed", self.failure))
        elif kind == "error":
            message = str(payload.get("message") or "unknown error")
            self.errors.append(message)
            produced.append(Event("error", message))
        else:
            # The envelope carried no recognized type. Keep the sample bounded
            # for the crash message rather than growing it per line.
            if len(self.unrecognized_types) < 8:
                self.unrecognized_types.add(kind or "<missing type>")
            return []

        self.recognized += 1
        self.events.extend(produced)
        return produced
