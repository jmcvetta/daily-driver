#!/usr/bin/env python3
"""Run one frozen reviewer arm serially and stop on provider pushback.

The wrapper never retries or changes providers. Run artifacts remain local;
make evals-record publishes the bounded provenance after grading.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PUSHBACK = re.compile(
    r"rate[ -]?limit(?:ed| exceeded| reached)?|quota (?:exceeded|exhausted|reached)|"
    r"usage limit (?:exceeded|reached)|too many requests|(?:HTTP|status)[ :=]+429",
    re.IGNORECASE,
)


def main() -> int:
    """Dispatch only the named arm and phase into a fresh explicit run directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("glm", "deepseek"), required=True)
    parser.add_argument("--phase", choices=("smoke", "cohort"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        parser.error("run directory already exists; attempts are never silently retried")
    experiment = {
        "glm": "omp-reviewer-glm-5.3-go.yaml",
        "deepseek": "omp-reviewer-deepseek-v4-pro-go.yaml",
    }[args.arm]
    cases = sorted((ROOT / "evals/tasks-judged/reviewer-quality").glob("*.yaml"))
    if len(cases) != 8:
        parser.error("materialize all eight tasks with evals-judge preflight first")
    if args.phase == "smoke":
        cases = [path for path in cases if path.name.startswith(("01-", "05-"))]
    command = [
        "uv", "tool", "run", "--isolated", "--python", "3.13",
        "--from", "coder-eval==0.11.6",
        "--with-editable", str(ROOT / "evals/coder-eval-omp"),
        "--with-editable", str(ROOT / "evals/coder-eval-codex"),
        "coder-eval", "run", "--include-skipped", "--max-parallel", "1", "--stream", "full",
        "--repeats", "1" if args.phase == "smoke" else "5",
        "--run-dir", str(run_dir), "-e", f"experiments/{experiment}",
        *[str(path.relative_to(ROOT / "evals")) for path in cases],
    ]
    env = {**os.environ, "TELEMETRY_ENABLED": "false"}
    process = subprocess.Popen(
        command, cwd=ROOT / "evals", env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, start_new_session=True, bufsize=1,
    )
    stopped = False
    assert process.stdout is not None
    try:
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if not stopped and PUSHBACK.search(line):
                stopped = True
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "provider-stop.json").write_text(json.dumps({
                    "reason": "provider quota or rate-limit pushback observed",
                    "arm": args.arm, "phase": args.phase,
                    "action": "stop process group; no further dispatch or retry",
                }, indent=2) + "\n")
                os.killpg(process.pid, signal.SIGTERM)
        status = process.wait(timeout=30)
    except BaseException:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        raise
    return 3 if stopped else status


if __name__ == "__main__":
    raise SystemExit(main())
