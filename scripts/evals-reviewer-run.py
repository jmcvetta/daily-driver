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
    r"usage limit (?:exceeded|reached)|too many requests|(?:HTTP|status)[ :=]+429|"
    r"insufficient[_ ]funds|positive credit balance|(?:HTTP|status)[ :=]+402",
    re.IGNORECASE,
)


def _selftest_pushback() -> None:
    """The provider stop must recognize a 402 credit refusal, not only 429s."""
    for text in (
        "omp provider error: 402 A positive credit balance is required",
        "insufficient_funds",
        "HTTP 402",
        "rate limit exceeded",
        "status 429",
        "quota exhausted",
    ):
        assert PUSHBACK.search(text), text
    for text in ("iteration 402 completed", "no error", "turn 4/2"):
        assert not PUSHBACK.search(text), text


SMOKE_GATE_CHECKS = (
    ("analysis_valid", "true", lambda value: value is True),
    ("attribution.valid", "true", lambda value: value is True),
    ("attribution.telemetry_valid", "true", lambda value: value is True),
    ("cost_comparison_valid", "true", lambda value: value is True),
    ("coverage.planned", "2", lambda value: value == 2),
    ("coverage.completed", "2", lambda value: value == 2),
    ("coverage.measurable_cohort", "true", lambda value: value is True),
    ("summary.reviewer_telemetry.verified", "2", lambda value: value == 2),
    ("summary.classification.full_review.tp", "1", lambda value: value == 1),
    ("summary.classification.clean.false_alarms", "0", lambda value: value == 0),
)


def nested_value(record: dict, path: str) -> object:
    """Read a dotted path, returning a distinct value when a key is absent."""
    value: object = record
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return "missing"
        value = value[part]
    return value


def validate_smoke_record(record: dict, arm: str) -> list[str]:
    """Return every reason a smoke record cannot open the cohort.

    The smoke is the campaign's only pre-dispatch check on attribution,
    telemetry and pricing, so an absent field is as blocking as a false one.
    """
    reasons = []
    if record.get("arm") != arm:
        reasons.append(f"arm is {record.get('arm')!r}; expected {arm!r}")
    for path, expected, accept in SMOKE_GATE_CHECKS:
        value = nested_value(record, path)
        if not accept(value):
            reasons.append(f"{path} is {value!r}; expected {expected}")
    return reasons


def _selftest_smoke_gate() -> None:
    """The cohort gate refuses every missing smoke condition, not only a bad arm."""
    valid = {
        "arm": "vercel-luna",
        "analysis_valid": True,
        "attribution": {"valid": True, "telemetry_valid": True},
        "cost_comparison_valid": True,
        "coverage": {"planned": 2, "completed": 2, "measurable_cohort": True},
        "summary": {
            "reviewer_telemetry": {"verified": 2},
            "classification": {"full_review": {"tp": 1}, "clean": {"false_alarms": 0}},
        },
    }
    assert validate_smoke_record(valid, "vercel-luna") == []
    for path, _, _ in SMOKE_GATE_CHECKS:
        broken = json.loads(json.dumps(valid))
        target = broken
        parts = path.split(".")
        for part in parts[:-1]:
            target = target[part]
        target[parts[-1]] = "wrong"
        reasons = validate_smoke_record(broken, "vercel-luna")
        assert any(path in reason for reason in reasons), (path, reasons)
    assert any("arm" in reason for reason in validate_smoke_record(valid, "vercel-glm"))


def main() -> int:
    """Dispatch only the named arm and phase into a fresh explicit run directory."""
    _selftest_pushback()
    _selftest_smoke_gate()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arm",
        choices=(
            "glm",
            "deepseek",
            "vercel-deepseek-pro",
            "vercel-luna",
            "vercel-kimi",
            "vercel-glm",
            "vercel-qwen",
            "vercel-mimo",
            "vercel-mistral",
        ),
        required=True,
    )
    parser.add_argument("--phase", choices=("smoke", "cohort", "delta"), required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--smoke-record",
        type=Path,
        help="collected smoke artifact that must pass before --phase cohort dispatches",
    )
    args = parser.parse_args()
    if args.phase == "cohort":
        if args.smoke_record is None:
            parser.error(
                "--phase cohort requires --smoke-record; run the smoke phase and collect it first"
            )
        try:
            smoke = json.loads(args.smoke_record.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            parser.error(f"cannot read --smoke-record {args.smoke_record}: {exc}")
        if not isinstance(smoke, dict):
            parser.error(f"--smoke-record {args.smoke_record} must contain a JSON object")
        reasons = validate_smoke_record(smoke, args.arm)
        if reasons:
            print(
                f"error: smoke record {args.smoke_record} cannot open the cohort:",
                file=sys.stderr,
            )
            for reason in reasons:
                print(f"  {reason}", file=sys.stderr)
            print(
                "collect a passing smoke with scripts/evals-reviewer-quality.py; "
                "do not dispatch the cohort",
                file=sys.stderr,
            )
            return 2
    run_dir = args.run_dir.resolve()
    if run_dir.exists():
        parser.error("run directory already exists; attempts are never silently retried")
    experiment = {
        "glm": "omp-reviewer-glm-5.3-go.yaml",
        "deepseek": "omp-reviewer-deepseek-v4-pro-go.yaml",
        "vercel-deepseek-pro": "omp-reviewer-deepseek-v4-pro-vercel.yaml",
        "vercel-luna": "omp-reviewer-luna-vercel.yaml",
        "vercel-kimi": "omp-reviewer-kimi-vercel.yaml",
        "vercel-glm": "omp-reviewer-glm-5.3-vercel.yaml",
        "vercel-qwen": "omp-reviewer-qwen4-max-vercel.yaml",
        "vercel-mimo": "omp-reviewer-mimo-v2.6-pro-vercel.yaml",
        "vercel-mistral": "omp-reviewer-mistral-large-4-vercel.yaml",
    }[args.arm]
    cases = sorted((ROOT / "evals/tasks-judged/reviewer-quality").glob("*.yaml"))
    if len(cases) != 8:
        parser.error("materialize all eight tasks with evals-judge preflight first")
    if args.phase == "smoke":
        cases = [path for path in cases if path.name.startswith(("01-", "05-"))]
    elif args.phase == "delta":
        cases = [path for path in cases if path.name.startswith(("07-", "08-"))]
    command = [
        "uv", "tool", "run", "--isolated", "--python", "3.13",
        "--from", "coder-eval==0.11.6",
        "--with", "typer==0.24.1",
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
