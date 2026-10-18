#!/usr/bin/env python3
"""The acceptance test for case 03's dispatch grading.

Two halves, both offline and stdlib-only, like `check-omp-agent.py`:

  * the evidence side: `coder_eval_omp.rpc.TurnReducer` and `dispatch` keep
    every attempted `task` call whole -- late arguments, rejected and
    unresolved calls, retries -- and refuse to truncate;
  * the grading side: `check_dispatch.py`, the fixture grader the case's
    three `run_command` criteria call, counts one assignment per `tasks[]`
    entry and never scores unclear evidence as a pass.

The three committed excerpts under `evals/fixtures/fix-daily-driver-bugs/
dispatch-evidence/` reproduce the defects the installed regex checker had: valid
tasks beyond its 2000-character window, a capitalised `Undertake`, and a
shared-context prohibition counted as a dispatch. They are rebuilt from the
offsets and texts the issue (#635) preserved, because the run directory they
came from is local and ignored. The historical records are untouched.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "coder-eval-omp" / "src"))

from coder_eval_omp import dispatch  # noqa: E402  (the path insert must come first)
from coder_eval_omp.rpc import TurnReducer  # noqa: E402

FIXTURES = ROOT / "evals" / "fixtures" / "fix-daily-driver-bugs"
GRADER_PATH = FIXTURES / "shared" / "check_dispatch.py"
EXCERPTS = FIXTURES / "dispatch-evidence"
CASE = ROOT / "evals" / "tasks" / "fix-daily-driver-bugs" / "03-unavailable-route-blocks-only-its-task.yaml"

spec = importlib.util.spec_from_file_location("check_dispatch", GRADER_PATH)
grader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grader)


class CheckFailed(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailed(message)


def result_text(count: int, agent: str = "implementation") -> str:
    jobs = "\n".join(f"- worker-{i} (job_{i:03d})" for i in range(1, count + 1))
    return f"Spawned {count} background agents using {agent}.\n{jobs}"


def call(tasks, *, agent="implementation", status="ok", text=None, call_id="c1", attempt=1, context=""):
    if text is None and status == "ok":
        text = result_text(len(tasks), agent or "implementation")
    return {
        "call_id": call_id,
        "attempt": attempt,
        "iteration": 1,
        "sequence": 1,
        "arguments": {"agent": agent, "context": context, "tasks": tasks},
        "status": status,
        "error": None if status == "ok" else "failed",
        "result": text,
        "result_text": text,
    }


def entry(task, **extra):
    return {"id": "t", "description": "d", "task": task, **extra}


def evidence(*calls, complete=True):
    return {"version": 1, "complete": complete, "calls": list(calls)}


def grade(document, *args) -> tuple[int, str]:
    """Run the real CLI against `document`, as the case's criteria do."""
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / dispatch.EVIDENCE_FILENAME
        if document is not None:
            path.write_text(document if isinstance(document, str) else json.dumps(document), encoding="utf-8")
        done = subprocess.run(
            [sys.executable, str(GRADER_PATH), "--evidence", str(path), *args],
            capture_output=True,
            text=True,
        )
    return done.returncode, done.stdout + done.stderr


REQUIRE_9 = ("--require", "990009", "--agent", "implementation")
REQUIRE_11 = ("--require", "990011", "--agent", "implementation")
FORBID_10 = ("--forbid", "990010")


def passes(document, *args) -> bool:
    return grade(document, *args)[0] == 0


def check_filenames_agree() -> None:
    check(grader.EVIDENCE_FILENAME == dispatch.EVIDENCE_FILENAME, "grader and writer disagree on the artifact name")
    check(grader.EVIDENCE_VERSION == dispatch.EVIDENCE_VERSION, "grader and writer disagree on the version")


def check_excerpts_reproduce_and_correct_the_defects() -> None:
    plugin_04 = json.loads((EXCERPTS / "with-plugin-04.json").read_text())
    text = json.dumps(plugin_04["calls"])
    check(all(text.find(f"undertake #{n}") > 2000 for n in (990009, 990011)), "excerpt 04 must keep tasks past 2000 chars")
    check(passes(plugin_04, *REQUIRE_9) and passes(plugin_04, *REQUIRE_11) and passes(plugin_04, *FORBID_10),
          "long context must not hide valid tasks")

    plugin_00 = json.loads((EXCERPTS / "with-plugin-00.json").read_text())
    check("Undertake #990009" in json.dumps(plugin_00), "excerpt 00 must keep the capitalised invocation")
    check(passes(plugin_00, *REQUIRE_9) and passes(plugin_00, *REQUIRE_11), "capitalisation must not reject a task")

    bare = json.loads((EXCERPTS / "bare-00.json").read_text())
    check("#990010 is NOT dispatched" in json.dumps(bare), "excerpt bare-00 must keep the shared-context prohibition")
    check(passes(bare, *FORBID_10), "a prohibition in shared context must not count as an assignment")
    check(passes(bare, *REQUIRE_9), "a failed preflight is not a second launch")


def check_parsing_variants() -> None:
    for task in ("undertake #990009", "Undertake #990009", "/undertake #990009", "undertake issue #990009",
                 "Run `undertake #990009`", "Run **undertake** #990009 now", "run /undertake #990009 on the fixture"):
        check(passes(evidence(call([entry(task), entry("undertake #990011")])), *REQUIRE_9), f"{task!r} must assign #990009")
    check(grader.positive_targets("undertake #990009 undertake #990009") == {"990009"}, "a repeat is one assignment")


def check_counts() -> None:
    both = evidence(call([entry("undertake #990009"), entry("undertake #990011")]))
    check(passes(both, *REQUIRE_9) and passes(both, *REQUIRE_11), "one batch of two")
    separate = evidence(call([entry("undertake #990009")], call_id="a"), call([entry("undertake #990011")], call_id="b"))
    check(passes(separate, *REQUIRE_9) and passes(separate, *REQUIRE_11), "two one-entry calls")
    repeated = evidence(call([entry("undertake #990009 and, again, undertake #990009")]))
    check(passes(repeated, *REQUIRE_9), "a repeat inside one entry is one assignment")
    twice = evidence(call([entry("undertake #990009"), entry("undertake #990009")]))
    check(not passes(twice, *REQUIRE_9), "duplicate entries in a batch are duplicates")
    two_calls = evidence(call([entry("undertake #990009")], call_id="a"), call([entry("undertake #990009")], call_id="b"))
    check(not passes(two_calls, *REQUIRE_9), "duplicate successful calls are duplicates")
    retried = evidence(call([entry("undertake #990009")], status="error", call_id="a"),
                       call([entry("undertake #990009")], call_id="b", attempt=2))
    check(passes(retried, *REQUIRE_9), "a failed preflight then one success is one launch")
    check(not passes(evidence(), *REQUIRE_9), "nothing dispatched cannot satisfy a requirement")
    check(passes(evidence(), *FORBID_10), "complete evidence of no dispatch proves no forbidden assignment")


def check_prohibitions_and_noise() -> None:
    noisy = evidence(call([entry("undertake #990009. Do not edit or comment on #990010; #990011 is a different issue."),
                           entry("undertake #990011 (see #990010 for background)")],
                          context="#990010 is NOT dispatched; do not pick it up"))
    check(passes(noisy, *FORBID_10), "warnings and mentions must not assign #990010")
    check(passes(noisy, *REQUIRE_9) and passes(noisy, *REQUIRE_11), "noise must not disturb real assignments")
    for task in ("do not undertake #990010", "Don't /undertake #990010", "never run undertake #990010"):
        check(passes(evidence(call([entry(task)])), *FORBID_10), f"{task!r} is negated")
    check(passes(evidence(call([entry("undertake #990009, not undertake #990010")])), *FORBID_10), "a negated second target")
    check(not passes(evidence(call([entry("undertake #990009, not undertake #990010")])), *REQUIRE_11), "absent target")


def check_forbidden_assignment_always_fails() -> None:
    for kind in ("ok", "error", "unresolved"):
        document = evidence(call([entry("undertake #990010")], status=kind))
        check(not passes(document, *FORBID_10), f"a {kind} call still assigned #990010")
    wrong = evidence(call([entry("undertake #990010")], agent="reasoning"))
    check(not passes(wrong, *FORBID_10), "the agent name does not excuse the assignment")
    override = evidence(call([entry("undertake #990010", model="x")], agent="other"))
    check(not passes(override, *FORBID_10), "a model override does not excuse the assignment")
    retry = evidence(call([entry("undertake #990010")], status="error", call_id="a"),
                     call([entry("undertake #990009")], call_id="b", attempt=2))
    check(not passes(retry, *FORBID_10), "a retry does not erase the earlier forbidden attempt")


def check_nothing_unclear_passes() -> None:
    wrong_agent = evidence(call([entry("undertake #990009")], agent="reasoning"))
    check(not passes(wrong_agent, *REQUIRE_9), "the required agent is part of the requirement")
    check(not passes(evidence(call([entry("undertake #990009 and undertake #990011")])), *REQUIRE_9),
          "several targets in one entry are unclear")
    check(not passes(evidence(call([entry("undertake #990009 and undertake #990011")])), *FORBID_10),
          "unclear evidence cannot prove an absence")
    for malformed in (evidence(call(["undertake #990009"])), evidence(call([{"id": "t"}])),
                      evidence({**call([entry("undertake #990009")]), "arguments": {}}),
                      evidence({**call([entry("undertake #990009")]), "arguments": {"agent": "implementation"}})):
        check(not passes(malformed, *REQUIRE_9) and not passes(malformed, *FORBID_10), "malformed evidence must fail both")
    check(not passes(None, *FORBID_10), "a missing artifact cannot pass")
    check(not passes("not json", *FORBID_10), "an unreadable artifact cannot pass")
    check(not passes({**evidence(), "version": 2}, *FORBID_10), "an unknown version cannot pass")
    incomplete = evidence(complete=False)
    incomplete["error"] = "too large"
    code, output = grade(incomplete, *FORBID_10)
    check(code != 0 and "too large" in output, "an instrumentation error is reported and never a pass")
    check(not passes(evidence(call([entry("undertake #990009")], status="unresolved")), *REQUIRE_9), "unresolved is not a launch")


def check_launch_results() -> None:
    def required(**changes):
        base = call([entry("undertake #990009"), entry("undertake #990011")])
        base.update(changes)
        return evidence(base)

    check(passes(required(), *REQUIRE_9), "the observed format proves a launch")
    for text in ("Spawned 2 background agents using implementation.\n- only-one",
                 "Spawned 1 background agents using implementation.\n- one",
                 "Spawned 2 background agents using implementation.",
                 "Spawned 2 background agents using implementation.\n- same\n- same",
                 "Spawned 2 background agents using reasoning.\n- a\n- b",
                 "Started two agents",
                 "Spawned 2 background agents using implementation.\nsurprise\n- a\n- b",
                 ""):
        document = required(result=text, result_text=text)
        check(not passes(document, *REQUIRE_9) and not passes(document, *REQUIRE_11), f"unproven launch {text!r}")
        check(passes(document, *FORBID_10), "launch state does not touch the absence check")
    check(not passes(required(result_text=None), *REQUIRE_9), "no result text, no launch")
    solo = evidence(call([entry("undertake #990009")], text="Spawned 1 background agent using implementation.\n- w"))
    check(passes(solo, *REQUIRE_9), "the singular header is the same format")


def frame(kind, call_id, **fields):
    return {"type": kind, "toolCallId": call_id, "toolName": "task", **fields}


def check_reducer_keeps_every_attempt() -> None:
    reducer = TurnReducer()
    tasks = [entry("undertake #990009"), entry("undertake #990011")]
    reducer.feed(frame("tool_execution_start", "k1"))
    reducer.feed(frame("tool_execution_update", "k1", args={"agent": "implementation", "tasks": [entry("draft")]}))
    reducer.feed(frame("tool_execution_update", "k1", args={"agent": "implementation", "context": "c", "tasks": tasks}))
    reducer.feed(frame("tool_execution_end", "k1", result={"content": [{"type": "text", "text": result_text(2)}], "details": {"n": 2}}))
    reducer.feed(frame("tool_execution_start", "k2", args={"agent": "reasoning", "tasks": [entry("undertake #990010")]}))
    reducer.feed(frame("tool_execution_end", "k2", isError=True, error="rejected"))
    reducer.feed(frame("tool_execution_start", "k3", args={"agent": "implementation", "tasks": [entry("undertake #990009")]}))
    reducer.feed({"type": "tool_execution_start", "toolCallId": "r1", "toolName": "read", "args": {"path": "x"}})
    reducer.feed({"type": "tool_execution_end", "toolCallId": "r1", "toolName": "read", "result": "unrelated"})
    reducer.close_open_tools()

    records = dispatch.task_call_records(reducer.tool_calls, attempt=2, iteration=1)
    check([r["call_id"] for r in records] == ["k1", "k2", "k3"], "one record per task call, no other tools")
    check(records[0]["arguments"]["tasks"] == tasks, "the final argument update wins; a start and update are one call")
    check(records[0]["result"]["details"] == {"n": 2}, "the raw result keeps its structured details")
    check(records[0]["result_text"] == result_text(2), "the result text is kept whole")
    check([r["status"] for r in records] == ["ok", "error", "unresolved"], "every outcome is recorded")
    check(all(r["attempt"] == 2 and r["iteration"] == 1 for r in records), "attempt and iteration identity")
    check("unrelated" not in json.dumps(records), "unrelated tool results are not kept")

    reused = TurnReducer()
    reused.feed(frame("tool_execution_start", "same", args={"tasks": [entry("undertake #990009")]}))
    reused.feed(frame("tool_execution_end", "same", result="done"))
    reused.feed(frame("tool_execution_start", "same", args={"tasks": [entry("undertake #990011")]}))
    got = dispatch.task_call_records(reused.tool_calls, attempt=1, iteration=1)
    check([r["status"] for r in got] == ["ok", "unresolved"], "a reused call id cannot lend one call's result to another")

    document = json.loads(dispatch.evidence_document(records))
    check(document["version"] == 1 and document["complete"] is True, "the document is versioned and complete")
    check(len(document["calls"]) == 3, "the document holds every record")


def check_oversize_is_an_explicit_error() -> None:
    huge = [{"arguments": {"tasks": [entry("x" * 1024)]}, "pad": "y" * (dispatch.MAX_EVIDENCE_BYTES // 4)} for _ in range(5)]
    try:
        dispatch.evidence_document(huge)
    except dispatch.EvidenceTooLarge as error:
        text = dispatch.error_document(str(error))
    else:
        raise CheckFailed("oversize evidence must raise, not be trimmed")
    code, output = grade(text, *FORBID_10)
    check(code != 0 and "limit" in output, "the grader reports the limit instead of scoring partial evidence")


def check_case_wiring() -> None:
    text = CASE.read_text(encoding="utf-8")
    check("record_task_dispatches: true" in text, "case 03 must opt in to the dispatch artifact")
    check(text.count("check_dispatch.py") == 3 and "tool_name: Agent" not in text, "three run_command checks replace the Agent regexes")
    for flags, weight in (("--require 990009 --agent implementation", 1), ("--require 990011 --agent implementation", 1),
                          ("--forbid 990010", 2)):
        pattern = re.compile(rf"command: python3 \.fixture/check_dispatch\.py {re.escape(flags)}\n(?:    .*\n)*?    weight: {weight}\n")
        check(pattern.search(text.replace("\n    timeout: 30", "\n    timeout: 30")) is not None, f"missing check {flags} weight {weight}")
    check("settle_on_async_handoff: true" in text, "the settle setting stays")


def main() -> None:
    for name, checker in sorted(globals().items()):
        if name.startswith("check_") and callable(checker):
            checker()
    print("check-dispatch-grader: one assignment per tasks[] entry, every attempted call kept, "
          "and no unclear evidence scores as a pass")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-dispatch-grader: {failure}", file=sys.stderr)
        sys.exit(1)
