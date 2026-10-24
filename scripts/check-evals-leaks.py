#!/usr/bin/env python3
"""Report behavior cases that pass without the plugin.

A leak is a behavior case that the bare variant passes on at least 80% of
three or more attempts. The skill-firing criterion is ignored because this
check measures behavior, not whether the skill loaded.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROVENANCE_DIR = ROOT / "evals" / "provenance"
TASKS_DIR = ROOT / "evals" / "tasks"
IGNORED_STATUSES = {"MAX_TURNS_EXHAUSTED", "ERROR"}
LEAK_THRESHOLD = 0.8
FAIL_THRESHOLD = 0.2
HELPED_DELTA = 0.6
MIN_LEAK_ATTEMPTS = 3


def load_records(provenance_dir: Path) -> list[dict[str, Any]]:
    """Load every committed record in the provenance directory."""
    records = []
    for path in sorted(provenance_dir.glob("*.json")):
        record = json.loads(path.read_text())
        record["_source_name"] = path.name
        records.append(record)
    return records


def task_directories(tasks_dir: Path) -> tuple[dict[str, str], list[str]]:
    """Map task IDs to their directories and return directory names, deepest first."""
    task_ids: dict[str, str] = {}
    directories = sorted(
        (path.name for path in tasks_dir.iterdir() if path.is_dir()),
        key=len,
        reverse=True,
    ) if tasks_dir.is_dir() else []
    for path in tasks_dir.rglob("*.yaml") if tasks_dir.is_dir() else ():
        for line in path.read_text().splitlines():
            match = re.match(r"^\s*task_id:\s*([^\s#]+)", line)
            if match:
                task_ids[match.group(1).strip("'\"")] = path.parent.name
    return task_ids, directories


def directory_for_task(task_id: str, task_ids: dict[str, str], directories: list[str]) -> str:
    """Return the task directory for an ID, including retired task IDs."""
    if task_id in task_ids:
        return task_ids[task_id]
    path = Path(task_id)
    if path.suffix in {".yaml", ".yml"} and len(path.parts) > 1:
        return path.parent.name
    for directory in directories:
        if task_id.startswith(directory + "-"):
            return directory
    return "unmapped"


def behavior_criteria(attempt: dict[str, Any]) -> list[dict[str, Any]]:
    """Return gating behavior criteria, excluding the skill-firing check."""
    return [
        criterion
        for criterion in attempt.get("criteria", [])
        if criterion.get("gating") is True
        and criterion.get("criterion_type") != "skill_triggered"
    ]


def behavior_pass(attempt: dict[str, Any]) -> bool:
    """Whether one attempt passes all its gating behavior criteria."""
    criteria = behavior_criteria(attempt)
    if not criteria or attempt.get("final_status") in IGNORED_STATUSES:
        return False
    return all(
        isinstance(criterion.get("score"), (int, float))
        and not isinstance(criterion.get("score"), bool)
        and isinstance(criterion.get("pass_threshold"), (int, float))
        and not isinstance(criterion.get("pass_threshold"), bool)
        and criterion["score"] >= criterion["pass_threshold"]
        for criterion in criteria
    )


def classify_record(record: dict[str, Any], active_task_ids: set[str] | None = None) -> dict[str, Any]:
    """Classify behavior cases in one record and collect skipped entries."""
    attempts = record.get("attempts", [])
    variant_ids = {attempt.get("variant_id") for attempt in attempts}
    if "bare" not in variant_ids or len(variant_ids) < 2:
        return {"skipped": True, "reason": "missing bare variant or fewer than two variants", "cases": []}

    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        task_id = attempt.get("task_id")
        if not task_id or (active_task_ids is not None and task_id not in active_task_ids):
            continue
        if behavior_criteria(attempt):
            by_case[task_id].append(attempt)

    cases = []
    for task_id, task_attempts in sorted(by_case.items()):
        by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for attempt in task_attempts:
            by_variant[attempt["variant_id"]].append(attempt)
        rates = {}
        pass_counts = {}
        attempt_counts = {}
        for variant, variant_attempts in by_variant.items():
            pass_counts[variant] = sum(behavior_pass(attempt) for attempt in variant_attempts)
            attempt_counts[variant] = len(variant_attempts)
            rates[variant] = pass_counts[variant] / attempt_counts[variant]
        bare_attempts = by_variant.get("bare", [])
        bare_rate = rates.get("bare", 0.0)
        treated_attempts = [attempt for variant, rows in by_variant.items() if variant != "bare" for attempt in rows]
        treated_rate = (
            sum(behavior_pass(attempt) for attempt in treated_attempts) / len(treated_attempts)
            if treated_attempts
            else 0.0
        )
        both_fail = bool(bare_attempts and treated_attempts) and bare_rate <= FAIL_THRESHOLD and all(
            rate <= FAIL_THRESHOLD for variant, rate in rates.items() if variant != "bare"
        )
        cases.append(
            {
                "task_id": task_id,
                "rates": rates,
                "pass_counts": pass_counts,
                "attempt_counts": attempt_counts,
                "bare_attempts": len(bare_attempts),
                "leak": len(bare_attempts) >= MIN_LEAK_ATTEMPTS and bare_rate >= LEAK_THRESHOLD,
                "both_fail": both_fail,
                "helped": bool(bare_attempts and treated_attempts) and treated_rate - bare_rate >= HELPED_DELTA,
            }
        )
    return {"skipped": False, "cases": cases}


def newest_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the newest record for each experiment ID."""
    latest: dict[str, tuple[datetime, int, dict[str, Any]]] = {}
    unkeyed: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        experiment_id = record.get("experiment_id")
        if not experiment_id:
            unkeyed.append(record)
            continue
        recorded_at = str(record.get("recorded_at", ""))
        try:
            timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
        except ValueError:
            timestamp = datetime.min.replace(tzinfo=timezone.utc)
        current = latest.get(experiment_id)
        if current is None or (timestamp, index) > (current[0], current[1]):
            latest[experiment_id] = (timestamp, index, record)
    return unkeyed + [entry[2] for entry in latest.values()]


def render_report(
    records: list[dict[str, Any]],
    task_ids: dict[str, str],
    directories: list[str],
    active_task_ids: set[str] | None = None,
) -> tuple[str, bool, list[str]]:
    """Render the report, return whether any leak exists, and skipped record names."""
    output = ["Eval behavior leak report"]
    has_leaks = False
    skipped: list[str] = []
    behavior_case_count = 0
    for record in records:
        name = f"{record.get('experiment_id', 'unknown experiment')} [{record.get('_source_name', 'record')}]"
        classification = classify_record(record, active_task_ids)
        if classification["skipped"]:
            skipped.append(name)
            output.append(f"\n{ name }: skipped ({classification['reason']})")
            continue
        cases = classification["cases"]
        leaks = sum(case["leak"] for case in cases)
        both_failures = sum(case["both_fail"] for case in cases)
        helped = sum(case["helped"] for case in cases)
        behavior_case_count += len(cases)
        output.append(
            f"\n{name}: {len(cases)} behavior cases, {leaks} leaks, "
            f"{both_failures} both-fail, {helped} helped"
        )
        for label, key in (("Leaks", "leak"), ("Both-fail", "both_fail"), ("Helped", "helped")):
            grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for case in cases:
                if case[key]:
                    grouped[directory_for_task(case["task_id"], task_ids, directories)].append(case)
            output.append(f"  {label}:")
            if not grouped:
                output.append("    none")
            for directory in sorted(grouped):
                output.append(f"    {directory}/")
                for case in sorted(grouped[directory], key=lambda item: item["task_id"]):
                    rates = ", ".join(
                        f"{variant} {rate:.0%} "
                        f"({case['pass_counts'][variant]}/{case['attempt_counts'][variant]})"
                        for variant, rate in sorted(case["rates"].items())
                    )
                    output.append(f"      {case['task_id']}: {rates}")
                    if case["leak"]:
                        has_leaks = True
    output.insert(1, f"Behavior cases: {behavior_case_count}")
    if skipped:
        output.append("\nSkipped records: " + ", ".join(skipped))
    return "\n".join(output), has_leaks, skipped


def selftest() -> bool:
    """Catch silent misclassification of leaks, both-fail cases, and firing-only cases."""
    def attempt(task_id: str, variant_id: str, status: str, score: float, firing: float = 0.0) -> dict[str, Any]:
        return {
            "task_id": task_id,
            "variant_id": variant_id,
            "final_status": status,
            "criteria": [
                {"criterion_type": "skill_triggered", "gating": True, "score": firing, "pass_threshold": 0.9},
                {"criterion_type": "behavior", "gating": True, "score": score, "pass_threshold": 0.8},
            ],
        }

    attempts = [
        *(attempt("tasks/undertake/leak.yaml", "bare", "SUCCESS", 1.0, 0.0) for _ in range(3)),
        *(attempt("tasks/undertake/leak.yaml", "with-plugin", "SUCCESS", 0.0, 1.0) for _ in range(3)),
        *(attempt("tasks/undertake/both-fail.yaml", variant, "SUCCESS", 0.0) for variant in ("bare", "with-plugin") for _ in range(3)),
        *(attempt("tasks/issue/helped.yaml", "bare", "SUCCESS", 0.0) for _ in range(3)),
        *(attempt("tasks/issue/helped.yaml", "with-plugin", "SUCCESS", 1.0) for _ in range(3)),
        *(
            {
                "task_id": "tasks/pr/firing-only.yaml",
                "variant_id": variant,
                "final_status": "SUCCESS",
                "criteria": [
                    {"criterion_type": "skill_triggered", "gating": True, "score": 1.0, "pass_threshold": 0.9}
                ],
            }
            for variant in ("bare", "with-plugin")
        ),
    ]
    result = classify_record({"attempts": attempts})
    observed = {case["task_id"]: (case["leak"], case["both_fail"], case["helped"]) for case in result["cases"]}
    expected = {
        "tasks/undertake/leak.yaml": (True, False, False),
        "tasks/undertake/both-fail.yaml": (False, True, False),
        "tasks/issue/helped.yaml": (False, False, True),
    }
    if observed != expected:
        print(f"selftest failed: expected {expected!r}, got {observed!r}", file=sys.stderr)
        return False
    return True


def parse_args() -> argparse.Namespace:
    """Parse leak-check arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", type=Path, help="read one provenance record instead of the directory")
    parser.add_argument("--check", action="store_true", help="exit 1 when a current behavior case leaks")
    parser.add_argument("--selftest", action="store_true", help="run the inline classifier self-test")
    return parser.parse_args()


def main() -> int:
    """Report behavior leaks or run the self-test."""
    args = parse_args()
    if args.selftest:
        if args.record or args.check:
            print("--selftest cannot be combined with --record or --check", file=sys.stderr)
            return 2
        if not selftest():
            return 1
        print("Leak classifier selftest passed")
        return 0

    if args.record:
        record = json.loads(args.record.read_text())
        record["_source_name"] = args.record.name
        records = [record]
    else:
        records = load_records(DEFAULT_PROVENANCE_DIR)
    task_ids, directories = task_directories(TASKS_DIR)
    if args.check and args.record is None:
        records = newest_records(records)
    active_ids = set(task_ids) if args.check else None
    report, has_leaks, _ = render_report(records, task_ids, directories, active_ids)
    print(report)
    return 1 if args.check and has_leaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
