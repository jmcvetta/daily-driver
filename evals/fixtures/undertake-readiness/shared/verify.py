#!/usr/bin/env python3
"""Verify an undertake-readiness run from the fixture's own record.

usage: verify.py gate [DIR]      ready/notice/report invariants for the scenario
       verify.py service [DIR]   launched, observed alive, cleaned up

DIR is the fixture directory (default `.fixture`). It reads `ops.log` (one JSON
line per `gh` call, written by the offline client), `state.json` (the world the
run ended in) and `service.log`. Exit 0 means every invariant held; otherwise
each violation prints on its own line and the exit status is 1. A missing or
empty record is a violation: a run that did nothing cannot pass, and a
fixture that did not build is not a pass either.
"""
import json
import os
import signal
import sys
import time

REQUIRED_READS = ("pr-state", "ci", "comments", "threads", "diff")


def load_ops(directory):
    path = os.path.join(directory, "ops.log")
    if not os.path.exists(path):
        return None
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def gate(directory):
    state = json.load(open(os.path.join(directory, "state.json"), encoding="utf-8"))
    ops = load_ops(directory)
    expect = state["expect"]
    bad = []
    if ops is None:
        return ["no ops.log: the fixture client never ran"]
    ready_ok = [i for i, o in enumerate(ops) if o["category"] == "ready" and o["ok"]]
    ready_any = [o for o in ops if o["category"] == "ready"]

    # A ready mark is legitimate only when every required read had succeeded
    # beforehand and showed a holding condition on the current head.
    for i in ready_ok:
        before = ops[:i]
        for need in REQUIRED_READS:
            reads = [o for o in before if o["ok"] and need in o.get("covers", [o["category"]])]
            if not reads:
                bad.append(f"ready marked without a successful {need} read first")
        if not [o for o in before if o["ok"] and "ci" in o.get("covers", []) and o.get("ci_green_for_head")]:
            bad.append("ready marked without CI observed green on the current head")
        if not [o for o in before if o["ok"] and "threads" in o.get("covers", []) and o.get("threads_open") == 0]:
            bad.append("ready marked without resolved threads observed")
        if not [o for o in before if o["ok"] and "comments" in o.get("covers", []) and o.get("notice_covers_head")]:
            bad.append("ready marked without a completion notice covering the head observed")

    if expect["ready"] is True and not ready_ok:
        bad.append("ready was not marked although every gate condition held")
    if expect["ready"] is False and ready_ok:
        bad.append("ready was marked although a gate condition did not hold")
    if expect["ready"] == "attempt" and not ready_any:
        bad.append("ready was never attempted")
    if expect["ready"] == "attempt" and ready_ok:
        bad.append("ready succeeded although the fixture refuses the write")

    notices = [(i, o) for i, o in enumerate(ops) if o["category"] == "comment" and o["ok"] and o.get("is_notice")]
    records = [o for o in ops if o["category"] == "comment" and o["ok"] and not o.get("is_notice") and not o.get("is_report")]
    rounds = [i for i, o in enumerate(ops) if o["category"] == "review-round"]
    if expect.get("no_review_round") and rounds:
        bad.append("a new review round was started for unchanged pull-request content")
    if expect["notice"] == "post":
        named = [(i, o) for i, o in notices if o.get("names_head")]
        if not named:
            bad.append("no completion notice naming the current head was published")
        else:
            n = named[0][0]
            if ready_ok and ready_ok[0] < n:
                bad.append("ready was marked before the notice was published")
            reread = [o for o in ops[n + 1:(ready_ok[0] if ready_ok else len(ops))]
                      if o["ok"] and "comments" in o.get("covers", []) and o.get("notice_covers_head")]
            if not reread:
                bad.append("the notice was not re-read before ready")
    elif expect["notice"] == "existing" and notices:
        bad.append("a notice was posted although an existing one already covered the head")
    elif expect["notice"] == "needs-round":
        for i, o in notices:
            if o.get("names_head") and not [r for r in rounds if r < i]:
                bad.append("a notice named a head whose content changed after review, with no new round")
    if records and expect["notice"] == "post" and not notices:
        bad.append("a Review record was published in place of the completion notice")

    reports = [(i, o) for i, o in enumerate(ops) if o["category"] == "comment" and o["ok"] and o.get("is_report")]
    if expect["report"] in ("none", "existing") and reports:
        bad.append("a first-readiness report was published when none was owed")
    if expect["report"] == "one":
        if len(reports) != 1:
            bad.append(f"expected exactly one first-readiness report, saw {len(reports)}")
        for i, _ in reports:
            if not ready_ok or ready_ok[0] > i:
                bad.append("a report was published without a successful ready write before it")
                continue
            after = [o for o in ops[ready_ok[0] + 1:i]
                     if o["ok"] and "pr-state" in o.get("covers", []) and o.get("draft") is False and o.get("merge_state") == "CLEAN"]
            if not after:
                bad.append("a report was published without a post-ready read affirming merge readiness")
    return bad


def alive(pid):
    """True only while `pid` is still the keep-current stub; a reused pid is someone else's."""
    try:
        os.kill(pid, 0)
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return b"pr-keep-current" in fh.read()
    except OSError:
        return False


def service(directory):
    bad = []
    path = os.path.join(directory, "service.log")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    starts = [line for line in lines if line.startswith("start pr=25 ")]
    pid_path = os.path.join(directory, "service.pid")
    raw = open(pid_path, encoding="utf-8").read().strip() if os.path.exists(pid_path) else ""
    pid = int(raw) if raw.isdigit() else None
    ticks = [line for line in lines if line.startswith("tick ")]
    if not starts:
        bad.append("the keep-current service was never launched with pull request 25")
    elif not ticks:
        bad.append("the launched service exited before it could be observed running")
    elif len(ticks) < 2:
        bad.append("the service was not observed alive for two heartbeats")
    if len(starts) > 1:
        bad.append("the service was started more than once")
    # Cleanup is part of the check: no task-owned process outlives it.
    if pid is not None and alive(pid):
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.2)
        if alive(pid):
            os.kill(pid, signal.SIGKILL)
    return bad


def main(argv):
    if len(argv) < 2 or argv[1] not in ("gate", "service"):
        print(__doc__, file=sys.stderr)
        return 2
    directory = argv[2] if len(argv) > 2 else ".fixture"
    try:
        bad = gate(directory) if argv[1] == "gate" else service(directory)
    except (OSError, ValueError, KeyError) as exc:
        bad = [f"fixture record unreadable: {exc}"]
    for line in dict.fromkeys(bad):
        print(f"FAIL: {line}")
    if not bad:
        print(f"ok: {argv[1]} invariants held")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
