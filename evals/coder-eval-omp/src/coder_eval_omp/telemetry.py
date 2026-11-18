"""Reviewer-child telemetry from Omp subagent frames — pure, like `rpc.py`.

The reviewer-quality suite dispatches Omp's `reviewer` as a child agent. The
parent's aggregate `usage` is not the reviewer's, and an attempt's wall time is
not the reviewer's latency, so the adapter subscribes to subagent events
(`set_subagent_subscription: events`) and keeps the child's own evidence:

- the requested selector and role from `subagent_progress`, plus the resolved
  model identity (`...@upstream`) and the resolved thinking level that Omp
  reports for that child;
- every completed assistant message with its own timestamp, model, provider,
  token buckets and duration;
- the child's elapsed wall time between its lifecycle frames and the sum of its
  per-message generation durations.

The artifact is versioned and bounded. A missing usage field is recorded as
unreported, never as zero, and the priced total is `unreported` unless every
message used for it carried a complete usage object.

Nothing here imports `coder_eval` or `omp`; `agent.py` feeds it frames.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from .pricing import UNREPORTED, cost_usd, load_prices, peak_multiplier, price_key as price_selector

#: File in the task sandbox. The collector reads this name.
EVIDENCE_FILENAME = "omp-reviewer-telemetry.json"

#: Bumped when the shape changes; a reader must reject any other value.
EVIDENCE_VERSION = 1

#: Most completed assistant messages kept per subagent; the rest only count.
MAX_MESSAGES = 64

#: Most subagent records kept per attempt; the rest only count as overflow.
MAX_SUBAGENTS = 16

#: Token buckets read from an Omp `AssistantMessage.usage`.
_USAGE_BUCKETS: tuple[tuple[str, str], ...] = (
    ("input", "input"),
    ("output", "output"),
    ("cache_read", "cacheRead"),
    ("cache_write", "cacheWrite"),
)

#: Fields copied from an assistant message, for the per-message record.
_MESSAGE_FIELDS = (
    ("response_id", "responseId"),
    ("timestamp_ms", "timestamp"),
    ("model", "model"),
    ("provider", "provider"),
    ("upstream_provider", "upstreamProvider"),
    ("upstream_model", "upstreamModel"),
    ("duration_ms", "duration"),
    ("ttft_ms", "ttft"),
    ("stop_reason", "stopReason"),
    ("error_message", "errorMessage"),
)


def _number(value: Any) -> bool:
    """A finite number, and never a boolean."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _optional_number(value: Any) -> int | float | None:
    """A number kept as-is, or None where the protocol omitted it."""
    return value if _number(value) else None


def _usage_of(message: dict[str, Any]) -> dict[str, Any] | None:
    """The four required token buckets and reasoning, or None when incomplete.

    Omp's `Usage` always carries input, output, cacheRead and cacheWrite for an
    assistant message. A message missing one is protocol drift; recording the
    present ones as a total would silently underprice the reviewer, so the
    whole object is reported unavailable instead.
    """
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return None
    found: dict[str, Any] = {}
    for bucket, spelling in _USAGE_BUCKETS:
        value = usage.get(spelling)
        if not _number(value) or value < 0:
            return None
        found[bucket] = value
    found["reasoning"] = _optional_number(usage.get("reasoningTokens"))
    return found


def _identity_from_resolved(value: Any) -> tuple[str | None, str | None]:
    """`(provider, model)` from Omp's `selector@upstream[:level]` identity.

    `vercel-ai-gateway/mistral/mistral-large-4@mistral:low` names the gateway
    selector and the upstream that served it. The upstream is what the arm's
    `vercel_gateway_only` restriction is meant to force, so it is kept apart
    from the requested route rather than folded into it.
    """
    if not isinstance(value, str) or not value:
        return None, None
    head, _, tail = value.partition("@")
    if not tail:
        return None, head or None
    upstream, _, _level = tail.partition(":")
    return (upstream or None), head or None


class ReviewerTelemetry:
    """Collect one attempt's subagent evidence, in the order Omp emits it."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._subagents: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []

    def _record(self, subagent_id: str) -> dict[str, Any]:
        record = self._subagents.get(subagent_id)
        if record is None:
            if len(self._order) >= MAX_SUBAGENTS:
                # Drop the oldest record and keep counting the loss, so a busy
                # parent cannot turn an unbounded artifact into a silent one.
                oldest = self._order.pop(0)
                self._subagents.pop(oldest, None)
            record = {
                "id": subagent_id,
                "agent": None,
                "description": None,
                "parent_tool_call_id": None,
                "status": None,
                "session_file": None,
                "requested_models": [],
                "model_role": None,
                "resolved_model_identity": None,
                "resolved_thinking_level": None,
                "resolved_model": None,
                "backend_provider": None,
                "backend_model": None,
                "started_monotonic": self._clock(),
                "ended_monotonic": None,
                "thinking_levels": [],
                "messages": [],
                "message_overflow": 0,
                "_message_ids": set(),
                "overflow": 0,
            }
            self._subagents[subagent_id] = record
            self._order.append(subagent_id)
        return record

    def ingest(self, frame: dict[str, Any]) -> bool:
        """Reduce one top-level Omp frame; True when it carried subagent data."""
        kind = frame.get("type")
        payload = frame.get("payload")
        if kind not in {"subagent_lifecycle", "subagent_progress", "subagent_event"}:
            return False
        if not isinstance(payload, dict):
            return False
        subagent_id = payload.get("id")
        if not isinstance(subagent_id, str) or not subagent_id:
            progress = payload.get("progress")
            subagent_id = progress.get("id") if isinstance(progress, dict) else None
        if not isinstance(subagent_id, str) or not subagent_id:
            return False
        record = self._record(subagent_id)
        if kind == "subagent_lifecycle":
            self._apply_lifecycle(record, payload)
        elif kind == "subagent_progress":
            self._apply_progress(record, payload)
        else:
            self._apply_event(record, payload)
        return True

    def _apply_lifecycle(self, record: dict[str, Any], payload: dict[str, Any]) -> None:
        record["agent"] = payload.get("agent") or record["agent"]
        record["description"] = payload.get("description") or record["description"]
        record["parent_tool_call_id"] = payload.get("parentToolCallId") or record["parent_tool_call_id"]
        record["session_file"] = payload.get("sessionFile") or record["session_file"]
        status = payload.get("status")
        if isinstance(status, str):
            record["status"] = status
        if status != "started" and record["ended_monotonic"] is None:
            record["ended_monotonic"] = self._clock()

    def _apply_progress(self, record: dict[str, Any], payload: dict[str, Any]) -> None:
        progress = payload.get("progress")
        if not isinstance(progress, dict):
            return
        record["agent"] = payload.get("agent") or record["agent"]
        record["parent_tool_call_id"] = payload.get("parentToolCallId") or record["parent_tool_call_id"]
        record["session_file"] = payload.get("sessionFile") or record["session_file"]
        status = progress.get("status")
        if isinstance(status, str):
            record["status"] = status
        models = progress.get("modelOverride")
        if isinstance(models, list):
            record["requested_models"] = [value for value in models if isinstance(value, str)]
        for field, key in (
            ("model_role", "modelRole"),
            ("resolved_model_identity", "resolvedModelIdentity"),
            ("resolved_thinking_level", "resolvedThinkingLevel"),
            ("resolved_model", "resolvedModel"),
        ):
            value = progress.get(key)
            if isinstance(value, str) and value:
                record[field] = value
        if record["resolved_model_identity"]:
            backend_provider, backend_model = _identity_from_resolved(record["resolved_model_identity"])
            record["backend_provider"] = backend_provider
            record["backend_model"] = backend_model

    def _apply_event(self, record: dict[str, Any], payload: dict[str, Any]) -> None:
        event = payload.get("event")
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if kind == "thinking_level_changed":
            record["thinking_levels"].append(
                {
                    "thinking_level": event.get("thinkingLevel"),
                    "configured": event.get("configured"),
                    "resolved": event.get("resolved"),
                }
            )
            return
        messages: list[Any] = []
        if kind == "message_end":
            messages = [event.get("message")]
        elif kind == "agent_end":
            messages = list(event.get("messages") or [])
        for message in messages:
            if isinstance(message, dict) and message.get("role") == "assistant":
                self._add_message(record, message)

    def _add_message(self, record: dict[str, Any], message: dict[str, Any]) -> None:
        message_id = message.get("responseId")
        if not isinstance(message_id, str) or not message_id:
            timestamp = message.get("timestamp")
            message_id = f"ts:{timestamp}" if _number(timestamp) else f"seq:{len(record['messages']) + record['message_overflow']}"
        if message_id in record["_message_ids"]:
            return
        record["_message_ids"].add(message_id)
        if len(record["messages"]) >= MAX_MESSAGES:
            record["message_overflow"] += 1
            return
        entry: dict[str, Any] = {field: message.get(source) for field, source in _MESSAGE_FIELDS}
        entry["usage"] = _usage_of(message)
        record["messages"].append(entry)

    def document(
        self,
        attempt: int,
        iteration: int,
        parent_model: str | None,
    ) -> dict[str, Any]:
        """This attempt's artifact fragment, with reviewer cost computed per message."""
        subagents = []
        table = load_prices()
        for subagent_id in self._order:
            record = self._subagents[subagent_id]
            messages = list(record["messages"])
            requested = record["requested_models"][0] if record["requested_models"] else None
            card = table.get(price_selector(requested)) if requested else None
            enriched = []
            for message in messages:
                entry = dict(message)
                entry["peak_multiplier"] = (
                    peak_multiplier(card.peak, message.get("timestamp_ms")) if card is not None else None
                )
                enriched.append(entry)
            priced = [
                {
                    "tokens": {
                        "uncached_input_tokens": message["usage"]["input"],
                        "output_tokens": message["usage"]["output"],
                        "cache_read_input_tokens": message["usage"]["cache_read"],
                        "cache_creation_input_tokens": message["usage"]["cache_write"],
                    },
                    "timestamp": message["timestamp_ms"],
                }
                for message in messages
                if message.get("usage") is not None
            ]
            cost = UNREPORTED
            if requested and messages and len(priced) == len(messages):
                cost = cost_usd(requested, priced)
            elapsed = (record["ended_monotonic"] or self._clock()) - record["started_monotonic"]
            generation = sum(
                message["duration_ms"]
                for message in messages
                if _number(message.get("duration_ms"))
            )
            subagents.append(
                {
                    "id": record["id"],
                    "agent": record["agent"],
                    "description": record["description"],
                    "parent_tool_call_id": record["parent_tool_call_id"],
                    "status": record["status"],
                    "session_file": record["session_file"],
                    "requested_models": record["requested_models"],
                    "requested_model": requested,
                    "model_role": record["model_role"],
                    "resolved_model_identity": record["resolved_model_identity"],
                    "resolved_thinking_level": record["resolved_thinking_level"],
                    "resolved_model": record["resolved_model"],
                    "backend_provider": record["backend_provider"],
                    "backend_model": record["backend_model"],
                    "thinking_levels": list(record["thinking_levels"]),
                    "elapsed_ms": round(max(elapsed, 0.0) * 1000, 3),
                    "generation_ms": round(float(generation), 3) if generation else None,
                    "messages": enriched,
                    "message_count": len(messages),
                    "message_overflow": record["message_overflow"],
                    "cost_usd": cost,
                }
            )
        return {
            "attempt": attempt,
            "iteration": iteration,
            "parent_model": parent_model,
            "subagents": subagents,
        }

    def has_subagents(self) -> bool:
        """Whether any subagent frame arrived for this attempt."""
        return bool(self._order)


def artifact_document(attempts: list[dict[str, Any]], *, complete: bool) -> str:
    """Serialize the whole artifact, with a UTC creation time."""
    return (
        json.dumps(
            {
                "version": EVIDENCE_VERSION,
                "complete": complete,
                "created_at": datetime.now(tz=timezone.utc).isoformat(),
                "attempts": attempts,
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
