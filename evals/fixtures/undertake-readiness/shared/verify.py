#!/usr/bin/env python3
"""Verify an undertake-readiness or branch-currency run from offline evidence.

usage: verify.py gate [DIR]      ready/notice/report invariants for the scenario
       verify.py service [DIR]   launched, observed alive, cleaned up
       verify.py currency [DIR]  base merge and current-head CI read

DIR is the fixture directory (default `.fixture`). It reads `ops.log` (one JSON
line per `gh` call), `state.json` (the world the verifier should observe) and
`service.log`. Exit 0 means every invariant held; otherwise each violation
prints on its own line.
"""
import json
import os
import signal
import subprocess
import sys
import time


def load_ops(directory):
    path = os.path.join(directory, "ops.log")
    if not os.path.exists(path):
        return None
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


REQUIRED_READS = ("diff", "pr-state", "ci", "threads", "comments")


def gate_evidence_missing(before):
    """Gate conditions the ops in `before` do not show as observed."""
    missing = []
    for need in REQUIRED_READS:
        if not [o for o in before if o["ok"] and need in o.get("covers", [o["category"]])]:
            missing.append(f"a successful {need} read")
    if not [o for o in before if o["ok"] and "ci" in o.get("covers", []) and o.get("ci_green_for_head")]:
        missing.append("CI observed green on the current head")
    if not [o for o in before if o["ok"] and "threads" in o.get("covers", []) and o.get("threads_open") == 0]:
        missing.append("resolved threads observed")
    if not [o for o in before if o["ok"] and "comments" in o.get("covers", []) and o.get("notice_covers_head")]:
        missing.append("a completion notice covering the head")
    return missing


def gate(directory):
    state = json.load(open(os.path.join(directory, "state.json"), encoding="utf-8"))
    ops = load_ops(directory)
    expect = state["expect"]
    bad = []
    if ops is None:
        return ["no ops.log: the fixture client never ran"]
    ready_any = [(i, o) for i, o in enumerate(ops) if o["category"] == "ready"]
    ready_ok = [i for i, o in ready_any if o["ok"]]

    # A ready attempt requires the gate evidence and a successful report
    # comment, or a report that was already present before this run.
    for i, ready in ready_any:
        before = ops[:i]
        for missing in gate_evidence_missing(before):
            bad.append(f"ready attempted without {missing} first")
        prior_report = any(o["category"] == "comment" and o["ok"] and o.get("is_report") for o in before)
        if expect["report"] == "existing":
            prior_report = any(c["body"].startswith("First-readiness report") for c in state["comments"])
        if not prior_report:
            bad.append("ready attempted without a published first-readiness report")

    if expect["ready"] is True and not ready_ok:
        bad.append("ready was not marked although every gate condition held")
    if expect["ready"] is False and ready_any:
        bad.append("ready was attempted although a gate condition did not hold")
    if expect["ready"] == "attempt" and not ready_any:
        bad.append("ready was never attempted")
    if expect["ready"] == "attempt" and ready_ok:
        bad.append("ready succeeded although the fixture refuses the write")
    if expect["ready"] == "none" and ready_any:
        bad.append("ready was attempted although report publication failed")

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
            if ready_any and ready_any[0][0] < n:
                bad.append("ready was attempted before the notice was published")
            reread = [o for o in ops[n + 1:(ready_any[0][0] if ready_any else len(ops))]
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

    reports = [(i, o) for i, o in enumerate(ops)
               if o["category"] == "comment" and o.get("is_report")]
    successful_reports = [(i, o) for i, o in reports if o["ok"]]
    if expect["report"] == "none" and reports:
        bad.append("a first-readiness report was attempted when none was owed")
    if expect["report"] == "existing":
        if successful_reports:
            bad.append("a first-readiness report was duplicated")
        if not any(c["body"].startswith("First-readiness report") for c in state["comments"]):
            bad.append("the fixture had no existing first-readiness report")
    if expect["report"] == "one":
        if len(successful_reports) != 1:
            bad.append(f"expected exactly one successful first-readiness report, saw {len(successful_reports)}")
        for i, report in successful_reports:
            before = ops[:i]
            for missing in gate_evidence_missing(before):
                bad.append(f"report posted without {missing} first")
            if not ready_any or i >= ready_any[0][0]:
                bad.append("the report was not successfully posted before the ready attempt")
            if report.get("draft") is not True:
                bad.append("the readiness report was not posted while the PR was a draft")
            if report.get("head") != expect["head"]:
                bad.append("the readiness report did not name the current head")
    if expect["report"] == "failed":
        if successful_reports or not reports:
            bad.append("expected only failed first-readiness report writes")
        if ready_any:
            bad.append("ready was attempted after the report write failed")
    elif expect["report"] != "failed" and any(not o["ok"] for _, o in reports):
        bad.append("a first-readiness report write failed")
    return bad



def currency(directory):
    state = json.load(open(os.path.join(directory, "state.json"), encoding="utf-8"))
    ops = load_ops(directory)
    if ops is None:
        return ["no ops.log: the fixture client never ran"]
    updates = [(i, op) for i, op in enumerate(ops) if op["category"] == "update-branch"]
    bad = []
    if len(updates) != 1 or not updates[0][1]["ok"]:
        bad.append(f"expected one successful base update attempt, saw {len(updates)}")
        return bad
    update_index, update = updates[0]
    previous_head = update.get("previous_head")
    if update["argv"] != ["pr", "update-branch", "25"]:
        bad.append("the update did not target pull request 25 through gh pr update-branch")
    if not previous_head or update["head"] == previous_head:
        bad.append("the update did not move the pull-request head")
    if not update.get("base_in_head"):
        bad.append("the resulting pull-request head does not contain its base")
    root = os.path.dirname(os.path.abspath(directory))
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    base = subprocess.run(["git", "rev-parse", "origin/master"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    if update.get("base_sha") != base:
        bad.append("the update did not use the pull request's master base")
    if state["pr"]["head"] != current:
        bad.append("the reported pull-request head differs from the fixture Git head")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", "origin/master", "HEAD"], cwd=root)
    if ancestor.returncode:
        bad.append("the fixture Git head does not contain origin/master")
    before_ci = [op for op in ops[:update_index]
                 if op["ok"] and "ci" in op.get("covers", [op["category"]])
                 and op["head"] == previous_head]
    before_workflows = [op for op in ops[:update_index]
                        if op["ok"] and op["category"] == "workflows"
                        and op["head"] == previous_head]
    if not any(op["argv"][-1].endswith("/check-runs") for op in before_ci):
        bad.append("current-head check runs were not read before the update")
    if not any(op["argv"][-1].endswith("/status") for op in before_ci):
        bad.append("current-head commit statuses were not read before the update")
    if not before_workflows:
        bad.append("matching workflow runs were not read before the update")
    after_ci = [op for op in ops[update_index + 1:]
                if op["ok"] and "ci" in op.get("covers", [op["category"]])
                and op["head"] == current]
    after_workflows = [op for op in ops[update_index + 1:]
                       if op["ok"] and op["category"] == "workflows"
                       and op["head"] == current]
    if not any(op["argv"][-1].endswith("/check-runs") for op in after_ci):
        bad.append("check runs were not assessed on the updated head")
    if not any(op["argv"][-1].endswith("/status") for op in after_ci):
        bad.append("commit statuses were not assessed on the updated head")
    if not after_workflows:
        bad.append("matching workflow runs were not assessed on the updated head")
    if not any(op.get("ci_in_flight") and not op["ci_green_for_head"] for op in after_ci):
        bad.append("CI was not assessed as in flight on the updated head")
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
    if len(starts) > 2:
        bad.append("the service was relaunched beyond its single mode-transition restart")
    # Cleanup is part of the check: no task-owned process outlives it.
    if pid is not None and alive(pid):
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.2)
        if alive(pid):
            os.kill(pid, signal.SIGKILL)
    return bad


def main(argv):
    if len(argv) < 2 or argv[1] not in ("gate", "service", "currency"):
        print(__doc__, file=sys.stderr)
        return 2
    directory = argv[2] if len(argv) > 2 else ".fixture"
    try:
        bad = {"gate": gate, "service": service, "currency": currency}[argv[1]](directory)
    except (OSError, ValueError, KeyError) as exc:
        bad = [f"fixture record unreadable: {exc}"]
    for line in dict.fromkeys(bad):
        print(f"FAIL: {line}")
    if not bad:
        print(f"ok: {argv[1]} invariants held")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
