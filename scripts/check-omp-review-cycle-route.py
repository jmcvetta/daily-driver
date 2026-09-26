#!/usr/bin/env python3
"""Check Omp's supervised CI route and exercise GNU timeout offline."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "omp.md"
UNDERTAKE_REFERENCE = ROOT / "skills" / "undertake" / "references" / "omp.md"
EMBARK_REFERENCE = ROOT / "skills" / "embark" / "references" / "omp.md"
STAND_DOWN_REFERENCE = ROOT / "skills" / "stand-down" / "references" / "omp.md"
SKILL = ROOT / "skills" / "review-cycle" / "SKILL.md"
REFERENCES = (
    REVIEW_REFERENCE,
    UNDERTAKE_REFERENCE,
    EMBARK_REFERENCE,
    STAND_DOWN_REFERENCE,
)
OBSOLETE_HUB_COMMAND = re.compile(
    r"\bhub\s+(?:start|wait|stop|describe|logs|jobs|cancel)\b", re.IGNORECASE
)


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-review-cycle-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def bounded_service_call(text: str) -> dict[str, str]:
    """Read the JSON named-service example from the review route."""
    examples = re.findall(r"```text\s*\n(\{.*?\})\n```", text, re.DOTALL)
    for example in examples:
        try:
            call = json.loads(example)
        except json.JSONDecodeError:
            continue
        if "gh pr checks --watch" in call.get("command", ""):
            return call
    fail("review-cycle has no executable named-service call example")


def check_documented_routes() -> None:
    """Reject stale calls and verify documented process controls and fields."""
    contents = {path: path.read_text(encoding="utf-8") for path in REFERENCES}
    for path, text in contents.items():
        if OBSOLETE_HUB_COMMAND.search(text):
            fail(f"{path.relative_to(ROOT)} requires the obsolete hub tool")

    review_text = contents[REVIEW_REFERENCE]
    call = bounded_service_call(review_text)
    if set(call) != {"command", "name", "cwd"}:
        fail("named-service example contains missing or unsupported fields")
    command = call["command"].split()
    expected_prefix = [
        "timeout",
        "--signal=TERM",
        "--kill-after=5s",
        "900s",
        "gh",
        "pr",
        "checks",
        "--watch",
    ]
    if "Agent Hub TUI" not in review_text or "omp://agent-hub.md" not in review_text:
        fail("review route does not distinguish Agent Hub from process control")
    if "mode write fails, inspect the service once" not in review_text:
        fail("review route does not inspect a rejected lifecycle change")
    if "stop it with" not in review_text or "persist=true" not in review_text:
        fail("review route does not stop a service whose persistence is unconfirmed")
    if "Do not assume a separate owner-scoped" not in review_text:
        fail("review route invents a completion replay guarantee")
    if command[: len(expected_prefix)] != expected_prefix:
        fail("service command does not use the bounded CI watch invocation")
    if call["name"] != "ci-<pr>-<short-sha>":
        fail("named service identity does not bind to the PR head")
    if call["cwd"] != "<task-worktree>":
        fail("named service does not run from the task worktree")
    if "GNU coreutils `timeout`" not in review_text:
        fail("review route does not state the deadline utility prerequisite")
    if "mode write fails" not in review_text or "stop the service" not in review_text:
        fail("review route does not clean up a rejected persistence request")
    if "write proc://<name>/mode" not in review_text or "persist=true" not in review_text:
        fail("review route does not verify persistent service mode")
    if "write proc://<name>/kill" not in review_text:
        fail("review route does not stop a failed or expired watcher")
    if "write proc://<name>/kill" not in contents[STAND_DOWN_REFERENCE]:
        fail("stand-down cannot stop the named CI service")
    if "write proc://<job-id>/kill" not in contents[EMBARK_REFERENCE]:
        fail("embark cannot cancel a task job by its returned job ID")
    if "read proc://<job-id>" not in contents[EMBARK_REFERENCE]:
        fail("embark cannot inspect a task job by its returned job ID")
    if "wait` with no arguments" not in contents[EMBARK_REFERENCE]:
        fail("embark does not use the current no-argument wait tool")
    if "wait` tool has no arguments" not in review_text:
        fail("review route does not document the current wait tool")
    if "partial watch that cannot observe registration" not in SKILL.read_text(encoding="utf-8"):
        fail("shared review-cycle rule omits the partial-watch exception")
    if "No unmanaged shell wait" not in SKILL.read_text(encoding="utf-8"):
        fail("shared review-cycle rule does not distinguish supervised services")


def run_timeout(timeout: str, command: list[str]) -> subprocess.CompletedProcess[str]:
    """Run one local fixture under the same GNU timeout utility as the route."""
    executable = shutil.which("timeout")
    if executable is None:
        fail("GNU coreutils timeout is required to exercise the documented route")
    return subprocess.run(
        [executable, "--signal=TERM", "--kill-after=0.1s", timeout, *command],
        check=False,
        capture_output=True,
        text=True,
    )


def check_deadline_and_cleanup() -> None:
    """Exercise normal exit, timeout, forced termination, and tree cleanup."""
    success = run_timeout("2s", [sys.executable, "-c", "raise SystemExit(0)"])
    if success.returncode != 0:
        fail("timeout changed a successful child exit")

    failure = run_timeout("2s", [sys.executable, "-c", "raise SystemExit(7)"])
    if failure.returncode != 7:
        fail("timeout changed a failed child exit")

    with tempfile.TemporaryDirectory(prefix="ci-watch-check-") as directory:
        marker = Path(directory) / "descendant-survived"
        descendant = (
            "import pathlib, time; time.sleep(0.4); "
            f"pathlib.Path({str(marker)!r}).write_text('alive')"
        )
        parent = (
            "import signal, subprocess, sys, time; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            f"subprocess.Popen([sys.executable, '-c', {descendant!r}]); "
            "time.sleep(30)"
        )
        expired = run_timeout(
            "0.1s", [sys.executable, "-c", parent]
        )
        if expired.returncode != 124:
            fail("timeout did not return 124 when the CI wait expired")
        time.sleep(0.5)
        if marker.exists():
            fail("deadline left a descendant process running")

    invalid = run_timeout("not-a-duration", [sys.executable, "-c", "pass"])
    if invalid.returncode != 125:
        fail("timeout accepted an invalid deadline")


def main() -> None:
    """Run the Omp route checks without GitHub credentials or network access."""
    check_documented_routes()
    check_deadline_and_cleanup()
    print(
        "check-omp-review-cycle-route: named Omp CI service is bounded, "
        "inspectable, and cleans up its process group"
    )


if __name__ == "__main__":
    main()
