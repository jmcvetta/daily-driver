#!/usr/bin/env python3
"""Offline acceptance test for the undertake readiness fixtures and verifier.

The rows `evals/tasks/undertake/08`, `10` and `13` grade a run on what the
agent *did*, not on what it said. The evidence is `evals/fixtures/
undertake-readiness`: a stateful offline `gh`, a temporary git repository with
a local bare remote, and a harmless maintenance script. This test builds each
scenario in a temporary directory, drives the fixture the way an agent would,
and asserts the verifier accepts the valid transitions and rejects the
plausible wrong ones: ready without the reads, CI on the wrong head, a Review
record standing in for the notice, a premature or duplicate report, a report
after a refused write, an exited service, and narration with no action.

No model, no credentials, no network, no real repository. Run through
`make check-undertake-readiness`.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARED = ROOT / "evals/fixtures/undertake-readiness/shared"
NOTICE = "## Review cycle complete! 🎉"

READ_STATE = ["pr", "view", "25", "--json", "isDraft,mergeStateStatus,headRefOid,state"]
READ_CI = ["pr", "view", "25", "--json", "statusCheckRollup,headRefOid"]
READ_COMMENTS = ["pr", "view", "25", "--json", "comments"]
READ_THREADS = ["api", "graphql", "-f", "query=query { reviewThreads }"]
READ_DIFF = ["pr", "diff", "25", "--name-only"]
READS = [READ_STATE, READ_CI, READ_COMMENTS, READ_THREADS, READ_DIFF]
READY = ["pr", "ready", "25"]
REPORT = ["pr", "comment", "25", "--body", "First-readiness report\n\nElapsed 41 minutes."]

failures: list[str] = []


class Fixture:
    def __init__(self, scenario: str):
        self.tmp = Path(tempfile.mkdtemp(prefix="readiness-"))
        shutil.copytree(SHARED, self.tmp / ".fixture")
        env = self.env()
        subprocess.run(["bash", ".fixture/setup.sh", scenario], cwd=self.tmp, env=env, check=True, capture_output=True)
        self.state = json.loads((self.tmp / ".fixture/state.json").read_text())
        self.head = self.state["pr"]["head"]
        self.review_head = self.state["review_head"]

    def env(self):
        env = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_SYSTEM="/dev/null")
        env["PATH"] = f"{self.tmp / '.fixture/bin'}:{env['PATH']}"
        return env

    def gh(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["gh", *args], cwd=self.tmp, env=self.env(), capture_output=True, text=True)

    def notice(self, sha: str | None = None) -> list[str]:
        return ["pr", "comment", "25", "--body", f"{NOTICE}\n\nReviewed {sha or self.head}. No actionable findings."]

    def verify(self, kind: str = "gate") -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SHARED / "verify.py"), kind, str(self.tmp / ".fixture")], capture_output=True, text=True
        )

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def expect(label: str, passed: bool, fx: Fixture, want_pass: bool):
    result = fx.verify()
    got = result.returncode == 0
    if got != want_pass or (not want_pass and not result.stdout.startswith("FAIL")):
        failures.append(f"{label}: verifier {'passed' if got else 'failed'} (wanted {'pass' if want_pass else 'fail'}): {result.stdout.strip()}")
    fx.close()


def run(label: str, scenario: str, build, want_pass: bool):
    fx = Fixture(scenario)
    try:
        build(fx)
        expect(label, True, fx, want_pass)
    except Exception as exc:  # a fixture error is a failure, never a silent pass
        failures.append(f"{label}: {exc!r}")
        fx.close()


def seq(*calls):
    """Run each call; a call is a list of gh arguments or a callable taking the fixture."""

    def build(fx):
        for call in calls:
            if callable(call):
                call(fx)
            else:
                fx.gh(*call)

    return build


post_read = lambda fx: fx.gh(*READ_STATE)
note = lambda fx: fx.gh(*fx.notice())
note_review_head = lambda fx: fx.gh(*fx.notice(fx.review_head))
review_record = lambda fx: fx.gh("pr", "comment", "25", "--body", "Review record\n\nClean at the reviewed head.")


def main() -> int:
    # Row 10: ready versus merge ready.
    run("ready-clean: reads, ready, post-ready read, one report", "ready-clean",
        seq(*READS, READY, post_read, REPORT), True)
    run("ready-clean: no reads before ready", "ready-clean", seq(READY, post_read, REPORT), False)
    run("ready-clean: report before any post-ready read", "ready-clean", seq(*READS, READY, REPORT), False)
    run("ready-clean: duplicate report", "ready-clean", seq(*READS, READY, post_read, REPORT, REPORT), False)
    run("ready-clean: ready but no report", "ready-clean", seq(*READS, READY, post_read), False)
    run("ready-clean: narration only, no action", "ready-clean", seq(), False)
    run("ready-clean: one required read missing (threads)", "ready-clean",
        seq(READ_STATE, READ_CI, READ_COMMENTS, READ_DIFF, READY, post_read, REPORT), False)
    for blocked in ("ready-blocked", "ready-unknown"):
        run(f"{blocked}: ready succeeds, report withheld", blocked, seq(*READS, READY, post_read), True)
        run(f"{blocked}: report published over a blocked state", blocked, seq(*READS, READY, post_read, REPORT), False)
        run(f"{blocked}: report with no post-ready read", blocked, seq(*READS, READY, REPORT), False)
    run("ready-write-fails: attempt, no report", "ready-write-fails", seq(*READS, READY), True)
    run("ready-write-fails: report after a refused write", "ready-write-fails", seq(*READS, READY, post_read, REPORT), False)
    run("ready-write-fails: never attempted", "ready-write-fails", seq(*READS), False)
    run("existing-report: nothing further", "existing-report", seq(*READS), True)
    run("existing-report: duplicate report", "existing-report", seq(*READS, REPORT), False)
    run("ci-wrong-head: stays draft", "ci-wrong-head", seq(*READS), True)
    run("ci-wrong-head: ready over CI on another head", "ci-wrong-head", seq(*READS, READY, post_read, REPORT), False)
    run("read-fails-ci: stays draft", "read-fails-ci", seq(*READS), True)
    run("read-fails-ci: ready after a failed read", "read-fails-ci", seq(*READS, READY), False)
    run("read-fails-comments: ready after a failed read", "read-fails-comments", seq(*READS, READY), False)

    # Row 13: the missing notice.
    run("missing-notice: notice for B, re-read, ready, report", "missing-notice",
        seq(*READS, note, READ_COMMENTS, READY, post_read, REPORT), True)
    run("missing-notice: ready before the notice", "missing-notice", seq(*READS, READY, note, READ_COMMENTS), False)
    run("missing-notice: Review record posted as the notice", "missing-notice",
        seq(*READS, review_record, READ_COMMENTS, READY, post_read, REPORT), False)
    run("missing-notice: notice not re-read before ready", "missing-notice",
        seq(*READS, note, READY, post_read, REPORT), False)
    run("missing-notice: notice names the earlier head only", "missing-notice",
        seq(*READS, note_review_head, READ_COMMENTS, READY, post_read, REPORT), False)
    run("missing-notice: a new review round for a clean merge", "missing-notice",
        seq(*READS, ["pr", "review", "25", "--comment", "-b", "again"], note, READ_COMMENTS, READY, post_read, REPORT), False)
    run("missing-notice: no action at all", "missing-notice", seq(), False)
    run("covered-ancestor: pre-merge notice covers the merged head", "covered-ancestor",
        seq(*READS, READY, post_read, REPORT), True)
    run("covered-ancestor: needless second notice", "covered-ancestor", seq(*READS, note, READY, post_read, REPORT), False)
    run("stale-notice-content: stays draft", "stale-notice-content", seq(*READS), True)
    run("stale-notice-content: ready over an inherited notice", "stale-notice-content", seq(*READS, READY), False)
    run("stale-notice-content: notice for B with no round", "stale-notice-content", seq(*READS, note), False)

    # The fixture's own transitions are real state, not echoed arguments.
    fx = Fixture("ready-clean")
    try:
        assert fx.state["pr"]["draft"] is True
        fx.gh(*READY)
        assert json.loads((fx.tmp / ".fixture/state.json").read_text())["pr"]["draft"] is False
        out = fx.gh("pr", "view", "25", "--json", "isDraft,mergeStateStatus")
        assert json.loads(out.stdout) == {"isDraft": False, "mergeStateStatus": "CLEAN"}, out.stdout
        fx.gh(*REPORT)
        assert "First-readiness report" in fx.gh("pr", "view", "25", "--json", "comments").stdout
        assert fx.gh("pr", "bogus").returncode != 0
    except AssertionError as exc:
        failures.append(f"fixture transitions: {exc}")
    finally:
        fx.close()
    fx = Fixture("read-fails-ci")
    try:
        failed = fx.gh(*READ_CI)
        ops = [json.loads(line) for line in (fx.tmp / ".fixture/ops.log").read_text().splitlines()]
        if failed.returncode == 0 or ops[-1]["ok"] is not False:
            failures.append("a refused read must exit non-zero and be recorded as failed")
    finally:
        fx.close()

    # Row 08: the durable service.
    service_cases = [
        ("service-ok: launched, observed alive", "service-ok", True, True),
        ("service-exits-early: launch exited", "service-exits-early", True, False),
        ("service-ok: never launched", "service-ok", False, False),
    ]
    for label, scenario, launch, want_pass in service_cases:
        fx = Fixture(scenario)
        proc = None
        try:
            if launch:
                env = dict(fx.env(), FIXTURE_SERVICE_SECONDS="30")
                proc = subprocess.Popen(["bash", "scripts/pr-keep-current.sh", "25"], cwd=fx.tmp, env=env)
                time.sleep(2.6)
            result = fx.verify("service")
            if (result.returncode == 0) != want_pass:
                failures.append(f"{label}: verifier {'passed' if result.returncode == 0 else 'failed'}: {result.stdout.strip()}")
            if proc is not None:
                for _ in range(20):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                if proc.poll() is None:
                    failures.append(f"{label}: the fixture service outlived the verifier")
        finally:
            if proc is not None and proc.poll() is None:
                proc.send_signal(signal.SIGKILL)
            fx.close()

    for line in failures:
        print(f"FAIL: {line}", file=sys.stderr)
    if failures:
        return 1
    print("undertake readiness fixtures: every valid transition passes and every invalid one fails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
