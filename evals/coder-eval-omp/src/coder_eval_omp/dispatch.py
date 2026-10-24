"""The task-dispatch evidence a row's grader reads — pure, like `rpc.py`.

Case 03 asks which issues the orchestrator assigned to workers. The canonical
`Agent` telemetry cannot answer that reliably: `command_executed` matches a
regex over the first 2000 characters of the serialized call, so a long shared
context hides the real assignments. This module records the Omp `task` tool
calls themselves — arguments, outcome and raw result — in a separate versioned
artifact, and the fixture grader parses `tasks[]` from it.

Nothing here rewrites the normal telemetry or synthesizes `Agent` calls. The
artifact is opt-in (`OmpAgentConfig.record_task_dispatches`) and never
truncates a field: past `MAX_EVIDENCE_BYTES` it is replaced by an explicit
instrumentation error, which the grader reports and cannot score as a pass.
"""

from __future__ import annotations

import json
from typing import Any

from .rpc import ToolStarted

﻿#: File in the task sandbox. `evals/fixtures/fix-daily-driver-bugs/shared/
#: check_dispatch.py` reads the same name.
EVIDENCE_FILENAME = "omp-task-dispatches.json"

#: Bumped when the shape changes; the grader rejects any other value.
EVIDENCE_VERSION = 1

#: An explicit ceiling, not a truncation point.
MAX_EVIDENCE_BYTES = 8 * 1024 * 1024

#: Omp's own name for the dispatch tool, before `TOOL_NAME_MAP` renames it.
TASK_TOOL = "task"


class EvidenceTooLarge(Exception):
    """The serialized evidence passed `MAX_EVIDENCE_BYTES`."""


def task_call_records(
    tool_calls: list[ToolStarted], *, attempt: int, iteration: int
) -> list[dict[str, Any]]:
    """One record per attempted `task` call, in call order.

    `tool_calls` is `TurnReducer.tool_calls`: an argument-less start followed
    by an argument update is already one entry holding the final arguments. A
    call with no end is `unresolved`, so a crash or timeout keeps what was
    attempted.
    """
    records: list[dict[str, Any]] = []
    for sequence, started in enumerate(tool_calls, start=1):
        if started.raw_tool_name.strip().lower() != TASK_TOOL:
            continue
        finished = started.finished
        records.append(
            {
                "call_id": started.call_id,
                "attempt": attempt,
                "iteration": iteration,
                "sequence": sequence,
                "arguments": dict(started.parameters),
                "status": finished.status if finished else "unresolved",
                "error": finished.error if finished else "no result observed",
                "result": finished.result if finished else None,
                "result_text": finished.summary if finished else None,
            }
        )
    return records


def evidence_document(calls: list[dict[str, Any]]) -> str:
    """The artifact text for `calls`; raises `EvidenceTooLarge`, never trims."""
    text = json.dumps(
        {"version": EVIDENCE_VERSION, "complete": True, "calls": calls},
        separators=(",", ":"),
        sort_keys=True,
    )
    size = len(text.encode("utf-8"))
    if size > MAX_EVIDENCE_BYTES:
        raise EvidenceTooLarge(
            f"task-dispatch evidence is {size} bytes, over the {MAX_EVIDENCE_BYTES}-byte limit"
        )
    return text + "\n"


def error_document(message: str) -> str:
    """The artifact for an instrumentation failure: present, and never a pass."""
    return (
        json.dumps(
            {"version": EVIDENCE_VERSION, "complete": False, "error": message, "calls": []},
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
