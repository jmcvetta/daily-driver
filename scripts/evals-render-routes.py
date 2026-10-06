#!/usr/bin/env python3
"""Render the `Measured routes` table in `omp.md` from committed provenance.

Reads every record under `evals/provenance/` -- never a run directory, so an
uncommitted run does not exist to this script -- and writes a markdown table
between the `<!-- measured-routes-start -->` / `<!-- measured-routes-end -->`
markers in `skills/issue-body/references/omp.md`. It lives in the
harness-specific reference, not in the provider-neutral `model-classes.md`,
because every route it names is a concrete Omp model or overlay -- see
`scripts/check-manifests.py`'s `model_identity_errors`. See `omp.md`'s
"Measured routes" section for what the table means, and `evals/README.md`'s
"The model-classes suite" for what a case measures.

USAGE

    python3 scripts/evals-render-routes.py   # make evals-render-routes
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evals_costs import uses_omp_codex_subscription

try:
    import yaml
except ImportError:  # pragma: no cover - the repository's uv environment has PyYAML.
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROVENANCE_DIR = ROOT / "evals" / "provenance"
DEFAULT_EXPERIMENTS_DIR = ROOT / "evals" / "experiments"
DEFAULT_OMP_CONFIGS_DIR = ROOT / "omp_configs"
DEFAULT_TARGET = ROOT / "skills" / "issue-body" / "references" / "omp.md"

START_MARKER = "<!-- measured-routes-start -->"
END_MARKER = "<!-- measured-routes-end -->"

# Highest first: the class earned is reported as the highest one a route
# clears, per model-classes.md's "Class earned" rule. `reasoning` is absent --
# evals-cases-from-prs.py builds no case for it today, and model_class_cases
# drops a case tagged with any class outside this tuple rather than let it
# reach `class_status`, which has no rule for scoring one.
BUILDABLE_CLASSES = ("implementation", "mechanical")

# "passed on at least two of three repeats" -- a fraction so any repeat count
# is judged the same way.
REPEAT_PASS_FRACTION = 2 / 3



def load_records(provenance_dir: Path) -> list[dict[str, Any]]:
    """Every committed provenance record under `provenance_dir`, oldest first."""
    records = [json.loads(path.read_text()) for path in sorted(provenance_dir.glob("*.json"))]
    records.sort(key=lambda record: str(record.get("completed_at", "")))
    return records


def list_overlays(omp_configs_dir: Path) -> list[str]:
    """Every Omp model-role overlay's name -- an `omp_configs/<name>.yml` stem."""
    return sorted(path.stem for path in omp_configs_dir.glob("*.yml"))


def overlay_settings(experiments_dir: Path, overlay: str) -> str:
    """The `experiment_id` `evals/experiments/classes-<overlay>.yaml` declares
    for `overlay` -- the settings value a real run of it would record. Falls
    back to `classes-<overlay>` when that experiment file does not exist,
    rather than guessing a spelling: two overlays in this repository already
    disagree on whether a `.` in the overlay name becomes a `-`.
    """
    experiment_path = experiments_dir / f"classes-{overlay}.yaml"
    if experiment_path.is_file():
        if yaml is None:
            raise RuntimeError("PyYAML is required to read experiment files")
        document = yaml.safe_load(experiment_path.read_text()) or {}
        experiment_id = document.get("experiment_id") if isinstance(document, dict) else None
        if isinstance(experiment_id, str) and experiment_id:
            return experiment_id
    return f"classes-{overlay}"


def model_class_cases(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every buildable-class case with its record's run, date and client.

    A case tagged with a class outside `BUILDABLE_CLASSES` (`reasoning`, or
    any future token) is dropped rather than kept: nothing computes a status
    for it, and keeping it would mark its route measured -- excluding it from
    the overlay `unmeasured` fallback -- while every column still read
    `unreported`, which is a more misleading state than reporting no case at
    all.
    """
    cases = []
    for record in records:
        completed_at = str(record.get("completed_at", ""))
        for case in record.get("cases", []):
            if case.get("class") not in BUILDABLE_CLASSES:
                continue
            cases.append(
                {
                    **case,
                    "run_id": record.get("run_id", "unknown"),
                    "completed_at": completed_at,
                    "date": completed_at[:10],
                    "client_name": record.get("client", {}).get("name", ""),
                }
            )
    return cases


def group_by_route(cases: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Case rows keyed by (model_requested, settings) -- the pair real dispatch
    would look up a route by.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in cases:
        groups.setdefault((case["model_requested"], case["settings"]), []).append(case)
    return groups


def class_status(cases: list[dict[str, Any]], klass: str) -> dict[str, Any] | None:
    """Whether `klass` is earned by `cases`, judged on only the most recent run
    that covers it. None when no case in `cases` carries this class at all.
    """
    covering = [case for case in cases if case["class"] == klass]
    if not covering:
        return None
    latest_run = max(covering, key=lambda case: case["completed_at"])["run_id"]
    latest = [case for case in covering if case["run_id"] == latest_run]
    by_task: dict[str, list[dict[str, Any]]] = {}
    for case in latest:
        by_task.setdefault(case["task_id"], []).append(case)
    earned = all(
        sum(1 for row in rows if row["outcome"] == "succeeded") / len(rows) >= REPEAT_PASS_FRACTION
        for rows in by_task.values()
    )
    passed = [case for case in latest if case["outcome"] == "succeeded"]
    cost_sources = [case.get("cost_source") for case in latest]
    if "subscription" in cost_sources:
        if (
            all(source == "subscription" for source in cost_sources)
            and all(case.get("cost") is None for case in latest)
            and all(
                uses_omp_codex_subscription(
                    case.get("client_name", ""),
                    "omp",
                    case.get("model_requested", ""),
                )
                for case in latest
            )
        ):
            cost_per_passed_case = "subscription"
        else:
            cost_per_passed_case = "unreported"
    else:
        costs = [case["cost"] for case in passed if isinstance(case.get("cost"), (int, float))]
        cost_per_passed_case = (
            f"${sum(costs) / len(costs):.2f}" if passed and len(costs) == len(passed) else "unreported"
        )
    return {
        "earned": earned,
        "pass_rate": f"{len(passed)}/{len(latest)}",
        "run_id": latest_run,
        "date": latest[0]["date"],
        "cost_per_passed_case": cost_per_passed_case,
    }


def build_routes(
    records: list[dict[str, Any]], overlays: list[str], experiments_dir: Path
) -> list[dict[str, Any]]:
    """One row per measured (model, settings) route, plus one `unmeasured` row
    per overlay whose settings carries no case at all.
    """
    cases = model_class_cases(records)
    groups = group_by_route(cases)
    routes = []
    for (model, settings), group in groups.items():
        statuses = {klass: class_status(group, klass) for klass in BUILDABLE_CLASSES}
        earned = next((klass for klass in BUILDABLE_CLASSES if statuses[klass] and statuses[klass]["earned"]), None)
        reference = statuses.get(earned) if earned else next((s for s in statuses.values() if s), None)
        routes.append(
            {
                "model": model,
                "settings": settings,
                "class_earned": earned or "none",
                "pass_rate": {
                    klass: (statuses[klass]["pass_rate"] if statuses[klass] else "unreported")
                    for klass in BUILDABLE_CLASSES
                },
                "cost_per_passed_case": reference["cost_per_passed_case"] if reference else "unreported",
                "run_id": reference["run_id"] if reference else "unreported",
                "date": reference["date"] if reference else "unreported",
            }
        )
    measured_settings = {settings for _, settings in groups}
    for overlay in overlays:
        settings = overlay_settings(experiments_dir, overlay)
        if settings in measured_settings:
            continue
        routes.append(
            {
                "model": overlay,
                "settings": settings,
                "class_earned": "unmeasured",
                "pass_rate": {klass: "unmeasured" for klass in BUILDABLE_CLASSES},
                "cost_per_passed_case": "unmeasured",
                "run_id": "unmeasured",
                "date": "unmeasured",
            }
        )
    return routes


def render_block(routes: list[dict[str, Any]]) -> str:
    """The markdown table for `routes`, sorted for a stable diff."""
    header = "| Model | Settings | Class earned | Mechanical pass rate | Implementation pass rate | Cost per passed case | Run | Recorded |"
    separator = "| --- | --- | --- | --- | --- | --- | --- | --- |"
    rows = [header, separator]
    for route in sorted(routes, key=lambda route: (route["model"], route["settings"])):
        pass_rate = route["pass_rate"]
        rows.append(
            "| {model} | {settings} | {class_earned} | {mechanical} | {implementation} | "
            "{cost} | {run_id} | {date} |".format(
                model=route["model"],
                settings=route["settings"],
                class_earned=route["class_earned"],
                mechanical=pass_rate["mechanical"],
                implementation=pass_rate["implementation"],
                cost=route["cost_per_passed_case"],
                run_id=route["run_id"],
                date=route["date"],
            )
        )
    return "\n".join(rows)


def replace_between_markers(text: str, block: str) -> str:
    """Rewrite only the text between the measured-routes markers in `text`."""
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER)
    if end < start:
        raise ValueError("measured-routes markers are out of order")
    return f"{text[:start]}\n{block}\n{text[end:]}"


def render(provenance_dir: Path, experiments_dir: Path, omp_configs_dir: Path, target: Path) -> None:
    """Read committed provenance and overlays, and rewrite `target`'s table."""
    records = load_records(provenance_dir)
    overlays = list_overlays(omp_configs_dir)
    routes = build_routes(records, overlays, experiments_dir)
    block = render_block(routes)
    target.write_text(replace_between_markers(target.read_text(), block))


def parse_args() -> argparse.Namespace:
    """Parse renderer command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provenance-dir", type=Path, default=DEFAULT_PROVENANCE_DIR)
    parser.add_argument("--experiments-dir", type=Path, default=DEFAULT_EXPERIMENTS_DIR)
    parser.add_argument("--omp-configs-dir", type=Path, default=DEFAULT_OMP_CONFIGS_DIR)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    return parser.parse_args()


def main() -> int:
    """Render the measured-routes table into its target file."""
    args = parse_args()
    render(args.provenance_dir, args.experiments_dir, args.omp_configs_dir, args.target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
