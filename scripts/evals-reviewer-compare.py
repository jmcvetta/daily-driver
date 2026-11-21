#!/usr/bin/env python3
"""Render the Vercel reviewer cohort comparison from committed collector artifacts.

Reads the reviewer-quality collector's JSON for each arm, checks coverage, and
writes a Markdown report. A full comparison is rendered only when the reference
arm and every candidate have a measurable cohort; otherwise the report states
each arm's coverage and refuses to compute a difference. It reads no run
directory and makes no model call.

Self-tests run on every invocation against inline fixtures.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROVENANCE = ROOT / "evals" / "provenance" / "reviewer-quality"

CASES = (
    "reviewer-quality-01-boundary",
    "reviewer-quality-02-contract",
    "reviewer-quality-03-authorization",
    "reviewer-quality-04-integrity",
    "reviewer-quality-05-clean-boundary",
    "reviewer-quality-06-clean-contract",
    "reviewer-quality-07-delta-fixed",
    "reviewer-quality-08-delta-incomplete",
)

#: Collector artifact stem for each arm, and the label the report uses.
ARMS: tuple[tuple[str, str], ...] = (
    ("deepseek-pro", "DeepSeek V4 Pro"),
    ("luna", "GPT-6 Luna"),
    ("kimi", "Kimi K3.1 Pro"),
    ("glm", "GLM 5.3"),
    ("qwen", "Qwen4 Max"),
    ("mimo", "MiMo V2.6 Pro"),
    ("mistral", "Mistral Large 4"),
)

REFERENCE = "deepseek-pro"


def rubric_correct(entry: dict[str, Any]) -> int:
    """One attempt's rubric-correct outcome: full reviews 1.0, deltas as declared."""
    if entry.get("status") != "completed":
        return 0
    score = entry.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        return 0
    case = entry["case_id"]
    if case.endswith("07-delta-fixed"):
        return int(
            score >= 0.7
            and "DELTA:clear" in entry["judge_classifications"]
            and entry["reviewer_verdict"] == "clear"
        )
    if case.endswith("08-delta-incomplete"):
        return int(
            score >= 0.7
            and "TP:still-open" in entry["judge_classifications"]
            and entry["reviewer_verdict"] == "defects"
        )
    return int(score >= 1.0)


def per_case(doc: dict[str, Any]) -> dict[str, list[int]]:
    """Rubric-correct outcomes grouped by case, in repeat order."""
    grouped: dict[str, list[int]] = {case: [] for case in CASES}
    for entry in doc.get("attempts", []):
        case = entry.get("case_id")
        if case in grouped:
            grouped[case].append(rubric_correct(entry))
    return grouped


def measurable(doc: dict[str, Any]) -> bool:
    """A cohort with no provider/harness errors and no unattempted slot."""
    coverage = doc.get("coverage") or {}
    return bool(
        coverage.get("measurable_cohort")
        and coverage.get("unattempted", 1) == 0
        and doc.get("cost_comparison_valid")
    )


def clustered_difference(
    reference: dict[str, list[int]],
    candidate: dict[str, list[int]],
    seed: int = 906,
    draws: int = 10_000,
) -> dict[str, Any]:
    """Case-clustered mean difference and percentile interval.

    One cluster is one case; its value is the difference between the candidate's
    and the reference's rubric-correct rate over that case's repeats. The
    interval describes these cases, not a general model population.
    """
    diffs: list[float] = []
    for case in CASES:
        reference_rates = reference.get(case) or []
        candidate_rates = candidate.get(case) or []
        if not reference_rates or not candidate_rates:
            continue
        diffs.append(
            sum(candidate_rates) / len(candidate_rates)
            - sum(reference_rates) / len(reference_rates)
        )
    if not diffs:
        return {"difference": None, "low": None, "high": None, "clusters": 0}
    rng = random.Random(seed)
    boot = sorted(
        statistics.fmean(rng.choice(diffs) for _ in diffs) for _ in range(draws)
    )
    return {
        "difference": statistics.fmean(diffs),
        "low": boot[int(draws * 0.025)],
        "high": boot[int(draws * 0.975)],
        "clusters": len(diffs),
    }


def load_arms(provenance: Path) -> dict[str, dict[str, Any]]:
    """Load each arm's collector artifact, or record why it is unavailable."""
    arms: dict[str, dict[str, Any]] = {}
    for stem, label in ARMS:
        path = provenance / f"vercel-{stem}-cohort.json"
        if not path.is_file():
            arms[stem] = {"label": label, "status": "missing", "path": path}
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        arms[stem] = {"label": label, "status": "present", "path": path, "document": document}
    return arms


def render(arms: dict[str, dict[str, Any]]) -> str:
    """The Markdown report. Refuses a comparison over an incomplete cohort."""
    lines = [
        "## Vercel reviewer cohort",
        "",
        "Generated from the committed collector artifacts. A difference is "
        "rendered only when every arm's cohort is measurable; otherwise this "
        "is a coverage statement, not a comparison.",
        "",
        "| Arm | Planned | Terminal | Completed | Refused (billing/pushback) | Harness errors | Unattempted | Measurable |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for stem, label in ARMS:
        arm = arms.get(stem, {})
        if arm.get("status") != "present":
            lines.append(f"| {label} | - | - | - | - | - | - | missing artifact |")
            continue
        coverage = arm["document"].get("coverage") or {}
        lines.append(
            "| {label} | {planned} | {terminal} | {completed} | {provider} | {harness} | {unattempted} | {measurable} |".format(
                label=label,
                planned=coverage.get("planned", "-"),
                terminal=coverage.get("terminal", "-"),
                completed=coverage.get("completed", "-"),
                provider=coverage.get("provider_errors", "-"),
                harness=coverage.get("harness_errors", "-"),
                unattempted=coverage.get("unattempted", "-"),
                measurable="yes" if measurable(arm["document"]) else "no",
            )
        )
    reference = arms.get(REFERENCE, {})
    complete = (
        reference.get("status") == "present"
        and measurable(reference["document"])
        and all(
            arms[stem].get("status") == "present" and measurable(arms[stem]["document"])
            for stem, _ in ARMS
        )
    )
    if not complete:
        lines += [
            "",
            "The comparison is not rendered: at least one arm lacks a measurable "
            "cohort. Restore the blocked route, complete the planned slots in fresh "
            "run directories, and regenerate the collector artifacts before reading "
            "a difference.",
        ]
        return "\n".join(lines) + "\n"
    reference_cases = per_case(reference["document"])
    lines += [
        "",
        "| Arm | Reviewer cost | Cost / rubric-correct review | Reviewer median latency | TP | FP | Precision | Clean FA | Delta correct | Case-clustered difference vs reference (95%) |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for stem, label in ARMS:
        document = arms[stem]["document"]
        summary = document["summary"]
        telemetry = summary["reviewer_telemetry"]
        difference = clustered_difference(reference_cases, per_case(document))
        if stem == REFERENCE:
            comparison = "reference"
        elif difference["difference"] is None:
            comparison = "unavailable"
        else:
            comparison = (
                f"{difference['difference']:+.3f} "
                f"[{difference['low']:+.3f}, {difference['high']:+.3f}] "
                f"over {difference['clusters']} cases"
            )
        full = summary["classification"]["full_review"]
        clean = summary["classification"]["clean"]
        delta = summary["classification"]["delta"]
        lines.append(
            "| {label} | ${cost} | ${per} | {median} s | {tp}/{tpn} | {fp} | {precision} | {fa}/{fan} | {dc}/{dcn} | {comparison} |".format(
                label=label,
                cost=_money(telemetry.get("cost_usd")),
                per=_money(telemetry.get("cost_per_rubric_correct_review_usd")),
                median=_number(summary["latency_reviewer_seconds"].get("median")),
                tp=full["tp"],
                tpn=full["recall_eligible_denominator"],
                fp=full["fp"],
                precision=_rate(full["precision"]),
                fa=clean["false_alarms"],
                fan=clean["eligible_denominator"],
                dc=delta["correct"],
                dcn=delta["eligible_denominator"],
                comparison=comparison,
            )
        )
    lines += ["", "Per-case rubric-correct counts (repeats in order):", ""]
    lines.append("| Case | " + " | ".join(label for _, label in ARMS) + " |")
    lines.append("| --- | " + " | ".join("---" for _ in ARMS) + " |")
    for case in CASES:
        cells = []
        for stem, _ in ARMS:
            values = per_case(arms[stem]["document"]).get(case) or []
            cells.append("/".join(str(value) for value in values) or "-")
        lines.append(f"| `{case}` | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _money(value: Any) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else "unavailable"


def _number(value: Any) -> str:
    return f"{value:.1f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else "unavailable"


def _rate(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) and not isinstance(value, bool) else "unavailable"


# ---------------------------------------------------------------------------
# Self-tests: offline, inline collector-shaped artifacts.
# ---------------------------------------------------------------------------


def _fixture(complete: bool) -> dict[str, Any]:
    attempts = []
    for case in CASES:
        for repeat in range(2 if complete else 1):
            attempts.append(
                {
                    "case_id": case,
                    "repeat": repeat,
                    "status": "completed",
                    "score": 1.0,
                    "judge_classifications": (
                        [f"TP:{case}", "DELTA:clear"] if case.endswith("07-delta-fixed")
                        else [f"TP:{case}", "TP:still-open"] if case.endswith("08-delta-incomplete")
                        else [f"TP:{case}"]
                    ),
                    "reviewer_verdict": "clear" if case.endswith("07-delta-fixed") else "defects",
                }
            )
    return {
        "attempts": attempts,
        "coverage": {
            "planned": len(attempts),
            "terminal": len(attempts),
            "completed": len(attempts),
            "provider_errors": 0,
            "harness_errors": 0,
            "unattempted": 0,
            "measurable_cohort": complete,
        },
        "cost_comparison_valid": complete,
        "summary": {
            "reviewer_telemetry": {
                "cost_usd": 0.1,
                "cost_per_rubric_correct_review_usd": 0.01,
            },
            "latency_reviewer_seconds": {"median": 12.0},
            "classification": {
                "full_review": {
                    "tp": 6, "fp": 0, "precision": 1.0,
                    "recall_eligible_denominator": 6,
                },
                "clean": {"false_alarms": 0, "eligible_denominator": 2},
                "delta": {"correct": 2, "eligible_denominator": 2},
            },
        },
    }


def _run_self_tests() -> None:
    reference = per_case(_fixture(True))
    candidate = per_case(_fixture(True))
    assert all(values == [1, 1] for values in reference.values())
    difference = clustered_difference(reference, candidate, draws=200)
    assert difference["difference"] == 0.0
    assert difference["clusters"] == len(CASES)
    arms = {stem: {"label": label, "status": "present", "document": _fixture(True)} for stem, label in ARMS}
    rendered = render(arms)
    assert "Case-clustered difference" in rendered
    assert "+0.000" in rendered
    partial = {stem: {"label": label, "status": "present", "document": _fixture(False)} for stem, label in ARMS}
    blocked = render(partial)
    assert "The comparison is not rendered" in blocked
    assert "Case-clustered difference" not in blocked


def main(argv: list[str] | None = None) -> int:
    """Render the report to stdout, or to `--output`."""
    _run_self_tests()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = render(load_arms(args.provenance))
    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(args.output)
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
