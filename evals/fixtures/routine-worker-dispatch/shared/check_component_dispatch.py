#!/usr/bin/env python3
"""Validate one routine component handoff from Omp task-dispatch evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

EVIDENCE_PATH = Path("omp-task-dispatches.json")
PENDING_PATH = EVIDENCE_PATH.with_name(f"{EVIDENCE_PATH.name}.pending")
SPAWNED_MANY = re.compile(r"^Spawned (\d+) background agents? using ([^\s.]+)\.\s*$")
SPAWNED_ONE = re.compile(r"^Spawned agent `([^`]+)` \(job `([^`]+)`\)\.\s*$")
JOB = re.compile(r"^\s*(?:[-*•])\s+(\S.*?)\s*$")

SCENARIOS: dict[str, dict[str, Any]] = {
    "implementation": {
        "files": ("labels.py", "test_labels.py", "README.md"),
        "command": "python3 -m unittest test_labels.py",
        "requirements": (
            ("contract", ("normalize_label", "lowercase", "ascii", "spaces or tabs", "underscore")),
            ("scope", ("owned product files", "do not change other files", "no other files", "may be edited", "sole writer of")),
            ("authorization", ("authorized", "no network", "no tracker")),
            ("single-writer ownership", ("sole writer", "one writer", "single writer")),
            ("owner integration", ("owner", "integrat")),
            ("acceptance", ("acceptance",)),
            ("requested result", ("observed", "unresolved")),
            ("no nested delegation", ("do not spawn", "no further worker", "no other worker", "dispatch any agent", "no other agent")),
        ),
    },
    "review-fix": {
        "files": ("format.py", "test_format.py", "README.md"),
        "command": "python3 -m unittest test_format.py",
        "requirements": (
            ("triaged findings", ("triaged", "accepted")),
            ("correction contract", ("format_name", "trim", "upper")),
            ("scope", ("owned product files", "do not change other files", "no other files", "may be edited", "sole writer of")),
            ("authorization", ("authorized", "no publication", "no push")),
            ("single-writer ownership", ("sole writer", "one writer", "single writer")),
            ("owner dispositions", ("owner", "thread", "disposition")),
            ("independent verification", ("verify the fix delta",)),
            ("requested result", ("observed", "unresolved")),
            ("no nested delegation", ("do not spawn", "no further worker", "no other worker", "dispatch any agent", "no other agent")),
        ),
    },
}


def fail(message: str) -> int:
    """Print a clear failed check and return a nonzero status."""
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def read_calls() -> tuple[list[dict[str, Any]] | None, str | None]:
    """Read complete structured Omp task-dispatch evidence."""
    if PENDING_PATH.exists():
        return None, "dispatch evidence is pending or its write failed"
    try:
        document = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return None, f"cannot read dispatch evidence: {error}"
    if not isinstance(document, dict) or document.get("version") != 1:
        return None, "unsupported dispatch-evidence version"
    if document.get("complete") is not True:
        return None, "dispatch evidence is incomplete"
    calls = document.get("calls")
    if not isinstance(calls, list) or not all(isinstance(call, dict) for call in calls):
        return None, "dispatch evidence has no valid calls list"
    return calls, None


def successful_task(calls: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    """Require one successful Omp task call containing one routine assignment."""
    successful = []
    for call in calls:
        status = call.get("status")
        if status == "unresolved":
            return None, "a task call has unresolved completion"
        if status == "ok":
            successful.append(call)
        elif status != "error":
            return None, f"unknown task-call status {status!r}"
    if len(successful) != 1:
        return None, f"expected one successful task call, found {len(successful)}"

    call = successful[0]
    arguments = call.get("arguments")
    if not isinstance(arguments, dict):
        return None, "successful task call has no arguments"
    tasks = arguments.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 1 or not isinstance(tasks[0], dict):
        return None, "successful task call must contain one component task"
    task = tasks[0]
    if task.get("agent", arguments.get("agent")) != "routine":
        return None, "component task is not assigned to routine"
    result = call.get("result_text")
    if not isinstance(result, str):
        return None, "task call did not record its result text"
    lines = [line for line in result.splitlines() if line.strip()]
    header = lines[0] if lines else ""
    single = SPAWNED_ONE.match(header)
    many = SPAWNED_MANY.match(header)
    if single is not None:
        if single.group(1) != single.group(2):
            return None, "spawned worker name and job differ"
    elif many is not None:
        if int(many.group(1)) != 1:
            return None, "task call did not report exactly one spawned worker"
        if many.group(2) != "routine":
            return None, f"spawned worker is {many.group(2)}, not routine"
        jobs = [line for line in lines[1:2] if JOB.match(line)]
        if not jobs:
            return None, "spawned worker is not listed by job"
    else:
        return None, "task call did not report a recognised spawned worker"
    if not isinstance(task.get("task"), str):
        return None, "routine task has no textual brief"
    return call, None


def check_brief(call: dict[str, Any], scenario: dict[str, Any]) -> list[str]:
    """Check the dispatched brief carries its scenario contract and boundaries."""
    arguments = call["arguments"]
    task = arguments["tasks"][0]
    context = arguments.get("context")
    text = "\n".join(
        value for value in (context, task.get("task")) if isinstance(value, str)
    ).casefold()
    missing = [path for path in scenario["files"] if path.casefold() not in text]
    if scenario["command"].casefold() not in text:
        missing.append(f"named check `{scenario['command']}`")
    for label, alternatives in scenario["requirements"]:
        if not any(phrase.casefold() in text for phrase in alternatives):
            missing.append(label)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    args = parser.parse_args()

    calls, error = read_calls()
    if error or calls is None:
        return fail(error or "dispatch evidence unavailable")
    call, error = successful_task(calls)
    if error or call is None:
        return fail(error or "successful component task unavailable")
    missing = check_brief(call, SCENARIOS[args.scenario])
    if missing:
        return fail("worker brief omits " + ", ".join(missing))
    print(f"PASS: one routine {args.scenario} task carries the required brief")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
