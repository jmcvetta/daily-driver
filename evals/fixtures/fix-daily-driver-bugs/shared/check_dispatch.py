#!/usr/bin/env python3
"""Grade the task assignments an Omp orchestrator made, from structured evidence.

Reads `omp-task-dispatches.json` (written by `coder_eval_omp` when a row sets
`record_task_dispatches`) and answers one binary question per invocation:

    check_dispatch.py --require 990009 --agent implementation
        exactly one successful assignment of #990009, to that agent
    check_dispatch.py --forbid 990010
        no positive assignment of #990010 at all

Exit 0 is a proved pass. Anything else exits 1 with a diagnostic: a failure,
or evidence too unclear to prove either answer.

THE PARSING RULES

An assignment is one `tasks[]` entry. Only that entry's `task` string names
what it was asked to undertake; names, descriptions, shared context and any
other mention of an issue are not authoritative. A positive invocation is
`undertake #N`, `/undertake #N` or `undertake issue #N`, case-insensitive,
with Markdown emphasis and code ticks ignored and an optional leading `Run`.
The same invocation repeated in one entry is one assignment. A negated
invocation (`do not undertake #N`) is not an assignment. An entry naming two
different targets, an entry that is not an object with a string `task`, and a
call with no recorded arguments are unclear, so nothing passes.

THE OUTCOME

A positive launch needs a successful tool result in the observed format

    Spawned 2 background agents using implementation.
    - <job one>
    - <job two>

with the reported count equal to the entries requested and a complete list of
distinct jobs. Any other success text, a mismatched count, or an agent that
differs from the one requested leaves the launch state unknown, which never
passes a `--require`. A failed or unresolved call launched nothing, but the
assignment it carried still fails a `--forbid`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

#: Mirrors `coder_eval_omp.dispatch.EVIDENCE_FILENAME`.
EVIDENCE_FILENAME = "omp-task-dispatches.json"
EVIDENCE_VERSION = 1

_INVOCATION = re.compile(r"(?<![\w/])/?undertake\s+(?:issue\s+)?#(\d+)\b", re.IGNORECASE)
_NEGATION = re.compile(
    r"(?:\bdo\s+not|\bdon'?t|\bnever|\bmust\s+not|\bmustn'?t|\bshould\s+not|\bshouldn'?t|\bnot|\bno|\bwithout|\bavoid)"
    r"\s+(?:\w+\s+){0,2}$",
    re.IGNORECASE,
)
_SPAWNED = re.compile(r"^Spawned (\d+) background agents? using ([^\s.]+)\.\s*$")
_BULLET = re.compile(r"^\s*(?:[-*•])\s+(\S.*?)\s*$")


class Unclear(Exception):
    """The evidence cannot prove an answer either way."""


def positive_targets(task: str) -> set[str]:
    """Issue numbers this instruction positively asks to undertake."""
    text = task.replace("`", "").replace("*", "")
    found: set[str] = set()
    for match in _INVOCATION.finditer(text):
        if _NEGATION.search(text[: match.start()]):
            continue
        found.add(match.group(1))
    return found


def parse_launch(call: dict[str, Any], entry_count: int, agent: str | None) -> str:
    """`launched`, `failed`, or `unknown` for the whole call.

    A partial or unrecognised outcome is `unknown`, never a per-entry guess.
    """
    status = call.get("status")
    if status in ("error", "unresolved"):
        return "failed"
    if status != "ok":
        return "unknown"
    text = call.get("result_text")
    if not isinstance(text, str):
        return "unknown"
    lines = [line for line in text.splitlines() if line.strip()]
    header = _SPAWNED.match(lines[0]) if lines else None
    if header is None:
        return "unknown"
    reported = int(header.group(1))
    if reported != entry_count:
        return "unknown"
    if agent is not None and header.group(2) != agent:
        return "unknown"
    jobs = []
    for line in lines[1:]:
        bullet = _BULLET.match(line)
        if bullet is None:
            return "unknown"
        jobs.append(bullet.group(1))
    if len(jobs) != reported or len(set(jobs)) != len(jobs):
        return "unknown"
    return "launched"


def assignments(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    """Every positive assignment: target, agent, call identity and launch state.

    Raises `Unclear` for evidence that is missing, malformed or ambiguous.
    """
    if evidence.get("version") != EVIDENCE_VERSION:
        raise Unclear(f"evidence version {evidence.get('version')!r} is not {EVIDENCE_VERSION}")
    if evidence.get("complete") is not True:
        raise Unclear(f"evidence is not complete: {evidence.get('error') or 'no reason recorded'}")
    calls = evidence.get("calls")
    if not isinstance(calls, list):
        raise Unclear("evidence has no calls list")

    found: list[dict[str, Any]] = []
    for call in calls:
        if not isinstance(call, dict):
            raise Unclear("a recorded call is not an object")
        label = f"call {call.get('call_id')!r} (attempt {call.get('attempt')})"
        arguments = call.get("arguments")
        if not isinstance(arguments, dict) or not arguments:
            raise Unclear(f"{label} recorded no arguments")
        tasks = arguments.get("tasks")
        if not isinstance(tasks, list):
            raise Unclear(f"{label} has no tasks list")
        call_agent = arguments.get("agent")
        agents = [
            entry.get("agent", call_agent)
            for entry in tasks
            if isinstance(entry, dict)
        ]
        for index, entry in enumerate(tasks):
            if not isinstance(entry, dict) or not isinstance(entry.get("task"), str):
                raise Unclear(f"{label} entry {index} is malformed")
            targets = positive_targets(entry["task"])
            if len(targets) > 1:
                raise Unclear(f"{label} entry {index} names several targets: {sorted(targets)}")
        agent = agents[0] if agents and all(item == agents[0] for item in agents) else None
        launch = parse_launch(call, len(tasks), agent if isinstance(agent, str) else None)
        for index, entry in enumerate(tasks):
            targets = positive_targets(entry["task"])
            for target in targets:
                found.append(
                    {
                        "target": target,
                        "agent": entry.get("agent", call_agent),
                        "launch": launch,
                        "where": f"{label} entry {index}",
                    }
                )
    return found


def check_required(found: list[dict[str, Any]], number: str, agent: str) -> list[str]:
    """Problems with the claim `number` was undertaken exactly once by `agent`."""
    mine = [item for item in found if item["target"] == number]
    problems = [
        f"#{number}: launch state unknown at {item['where']}" for item in mine if item["launch"] == "unknown"
    ]
    if problems:
        return problems
    launched = [item for item in mine if item["launch"] == "launched"]
    if not launched:
        return [f"#{number}: no successful assignment ({len(mine)} attempted)"]
    if len(launched) > 1:
        return [f"#{number}: {len(launched)} successful assignments, expected exactly one"]
    if launched[0]["agent"] != agent:
        return [f"#{number}: assigned to {launched[0]['agent']!r}, expected {agent!r}"]
    return []


def check_forbidden(found: list[dict[str, Any]], number: str) -> list[str]:
    """Problems if any positive assignment of `number` exists, launched or not."""
    return [
        f"#{number}: forbidden assignment at {item['where']} (agent {item['agent']!r}, {item['launch']})"
        for item in found
        if item["target"] == number
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evidence", default=EVIDENCE_FILENAME)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--require", metavar="NUMBER")
    mode.add_argument("--forbid", metavar="NUMBER")
    parser.add_argument("--agent", help="the agent a --require assignment must use")
    args = parser.parse_args(argv)
    if args.require and not args.agent:
        parser.error("--require needs --agent")

    path = Path(args.evidence)
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(evidence, dict):
            raise Unclear("evidence is not a JSON object")
        found = assignments(evidence)
    except FileNotFoundError:
        print(f"FAIL: {path} is missing; no dispatch evidence was recorded", file=sys.stderr)
        return 1
    except (OSError, json.JSONDecodeError, Unclear) as error:
        print(f"FAIL: dispatch evidence is unusable: {error}", file=sys.stderr)
        return 1

    problems = (
        check_required(found, args.require, args.agent)
        if args.require
        else check_forbidden(found, args.forbid)
    )
    if problems:
        print("FAIL: " + "; ".join(problems), file=sys.stderr)
        return 1
    print(f"PASS: #{args.require or args.forbid} {'dispatched once' if args.require else 'not assigned'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
