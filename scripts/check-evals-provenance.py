#!/usr/bin/env python3
"""Exercise the eval provenance recorder with offline synthetic artifacts."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RECORDER = ROOT / "scripts" / "evals-record.py"
RENDERER = ROOT / "scripts" / "evals-render-routes.py"
RESULTS_RENDERER = ROOT / "scripts" / "evals-render-results.py"


class Failed(Exception):
    """A synthetic provenance case did not hold."""


def load_renderer():
    """Import `evals-render-routes.py` under a valid module name."""
    spec = importlib.util.spec_from_file_location("evals_render_routes", RENDERER)
    if spec is None or spec.loader is None:
        raise Failed(f"could not load {RENDERER.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    """Raise a named failure when an acceptance condition is false."""
    if not condition:
        raise Failed(message)


def recorder_result(
    run_dir: Path, experiment: Path, output: Path, env: dict[str, str], prices: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the recorder, against the committed price table unless `prices` names another."""
    command = [sys.executable, str(RECORDER), str(run_dir), "--experiment", str(experiment), "--output", str(output)]
    if prices is not None:
        command += ["--prices", str(prices)]
    return subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)


def run_recorder(
    run_dir: Path, experiment: Path, output: Path, env: dict[str, str], prices: Path | None = None
) -> Path:
    """Run the recorder and return its generated record path."""
    result = recorder_result(run_dir, experiment, output, env, prices)
    require(result.returncode == 0, result.stderr or result.stdout)
    record = Path(result.stdout.strip())
    require(record.is_file(), "recorder did not write a record")
    return record


def _case_row(
    task_id: str,
    klass: str,
    outcome: str,
    replicate_index: int,
    *,
    model_requested: str,
    settings: str,
    model_served: str = "unreported",
    cost: float | str | None = "unreported",
) -> dict[str, object]:
    """One `cases[]` row shaped like `evals-record.py`'s `run_cases` output."""
    return {
        "task_id": task_id,
        "variant_id": "default",
        "replicate_index": replicate_index,
        "class": klass,
        "model_requested": model_requested,
        "model_served": model_served,
        "settings": settings,
        "outcome": outcome,
        "elapsed_seconds": 30.0,
        "tokens": "unreported",
        "cost": cost,
    }


def check_renderer() -> None:
    """A Codex subscription route must not be labeled unreported or dollar-priced."""
    renderer = load_renderer()
    subscription_case = _case_row(
        "one",
        "mechanical",
        "succeeded",
        0,
        model_requested="openai-codex/gpt-6-luna",
        settings="classes-luna",
        cost=None,
    )
    subscription_case.update(
        {
            "run_id": "codex-subscription",
            "completed_at": "2026-10-06T10:00:00Z",
            "date": "2026-10-06",
            "client_name": "omp",
            "cost_source": "subscription",
        }
    )
    subscription_status = renderer.class_status([subscription_case], "mechanical")
    require(
        subscription_status["cost_per_passed_case"] == "subscription",
        "a Codex subscription route was rendered as unreported or dollar-priced",
    )
    unknown_case = {**subscription_case, "model_requested": "openai-codex/gpt-6-unknown"}
    unknown_status = renderer.class_status([unknown_case], "mechanical")
    require(
        unknown_status["cost_per_passed_case"] == "unreported",
        "an unknown Codex model was labeled as a subscription",
    )
    mixed_case = {**subscription_case, "cost": 0.1, "cost_source": "reported"}
    mixed_status = renderer.class_status([subscription_case, mixed_case], "mechanical")
    require(
        mixed_status["cost_per_passed_case"] == "unreported",
        "a mixed subscription and dollar total was rendered as a whole price",
    )
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        provenance_dir = temp / "provenance"
        provenance_dir.mkdir()
        experiments_dir = temp / "experiments"
        experiments_dir.mkdir()
        omp_configs_dir = temp / "omp_configs"
        omp_configs_dir.mkdir()
        target = temp / "model-classes.md"

        # model-x: 2/3 mechanical repeats pass (earned), 1/3 implementation
        # repeats pass (not earned) -- a stale run, an unreported served
        # model, and the "pass" scenario.
        (provenance_dir / "run-old.json").write_text(
            json.dumps(
                {
                    "run_id": "run-old",
                    "completed_at": "2026-01-01T00:00:00Z",
                    "cases": [
                        _case_row(
                            "t1", "mechanical", "succeeded", 0,
                            model_requested="model-x-pinned", settings="classes-model-x", cost=0.10,
                        ),
                        _case_row(
                            "t1", "mechanical", "succeeded", 1,
                            model_requested="model-x-pinned", settings="classes-model-x", cost=0.20,
                        ),
                        _case_row(
                            "t1", "mechanical", "failed", 2,
                            model_requested="model-x-pinned", settings="classes-model-x",
                        ),
                        _case_row(
                            "t2", "implementation", "failed", 0,
                            model_requested="model-x-pinned", settings="classes-model-x",
                        ),
                        _case_row(
                            "t2", "implementation", "failed", 1,
                            model_requested="model-x-pinned", settings="classes-model-x",
                        ),
                        _case_row(
                            "t2", "implementation", "succeeded", 2,
                            model_requested="model-x-pinned", settings="classes-model-x", cost=0.30,
                        ),
                    ],
                }
            )
        )

        # model-y: every mechanical repeat fails -- the "fail" scenario, with
        # no case tagged implementation for this route at all.
        (provenance_dir / "run-new.json").write_text(
            json.dumps(
                {
                    "run_id": "run-new",
                    "completed_at": "2026-09-20T00:00:00Z",
                    "cases": [
                        _case_row(
                            "t3", "mechanical", "failed", index,
                            model_requested="model-y-pinned", settings="classes-model-y",
                            model_served="served-y",
                        )
                        for index in range(3)
                    ],
                }
            )
        )

        # model-z: two runs complete on the same calendar day: the earlier
        # passes every mechanical repeat, the later fails every one. Only the
        # true latest (by full timestamp, not the truncated date) may win.
        (provenance_dir / "run-tie-early.json").write_text(
            json.dumps(
                {
                    "run_id": "run-tie-early",
                    "completed_at": "2026-05-01T08:00:00Z",
                    "cases": [
                        _case_row(
                            "t4", "mechanical", "succeeded", index,
                            model_requested="model-z-pinned", settings="classes-model-z",
                        )
                        for index in range(3)
                    ],
                }
            )
        )
        (provenance_dir / "run-tie-late.json").write_text(
            json.dumps(
                {
                    "run_id": "run-tie-late",
                    "completed_at": "2026-05-01T20:00:00Z",
                    "cases": [
                        _case_row(
                            "t4", "mechanical", "failed", index,
                            model_requested="model-z-pinned", settings="classes-model-z",
                        )
                        for index in range(3)
                    ],
                }
            )
        )

        # model-r: the only case for this route is tagged `reasoning`, a class
        # this renderer never scores. It must not create a measured-but-empty
        # row, and its overlay must still read `unmeasured`.
        (provenance_dir / "run-reasoning.json").write_text(
            json.dumps(
                {
                    "run_id": "run-reasoning",
                    "completed_at": "2026-06-01T00:00:00Z",
                    "cases": [
                        _case_row(
                            "t5", "reasoning", "succeeded", 0,
                            model_requested="model-r-pinned", settings="classes-model-r",
                        )
                    ],
                }
            )
        )

        for overlay in ("model-x", "model-y", "model-z", "model-r", "unmeasured-overlay"):
            (omp_configs_dir / f"{overlay}.yml").write_text("modelRoles: {}\n")

        # model-x's own experiment file quotes its experiment_id -- a shape a
        # hand-written regex over the raw YAML text would mis-parse (keeping
        # the quote characters), silently missing the route it already has a
        # measured case for.
        (experiments_dir / "classes-model-x.yaml").write_text('experiment_id: "classes-model-x"\n')

        target.write_text(
            "# Model classes\n\n"
            f"{renderer.START_MARKER}\n{renderer.END_MARKER}\n"
        )
        renderer.render(provenance_dir, experiments_dir, omp_configs_dir, target)
        rendered = target.read_text()

        require("| model-x-pinned | classes-model-x | mechanical |" in rendered, "the earned class was not reported")
        require("| 2/3 | 1/3 |" in rendered, "per-class pass rates were not both reported")
        require("$0.15" in rendered, "cost per passed case was not averaged over the earned class's passes")
        require("2026-01-01" in rendered, "a stale row's own date was not rendered")
        require("| model-y-pinned | classes-model-y | none | 0/3 | unreported |" in rendered, "an all-fail route was not reported as earning no class")
        require("| unmeasured-overlay | classes-unmeasured-overlay | unmeasured |" in rendered, "an overlay with no case row was not listed unmeasured")
        require(
            "| model-z-pinned | classes-model-z | none | 0/3 |" in rendered,
            "same-day runs were not ranked by full timestamp -- the earlier, passing run won",
        )
        require(
            "model-z-pinned" in rendered and "3/3" not in rendered.split("model-z-pinned")[1].split("\n")[0],
            "the earlier same-day run's 3/3 leaked into the model-z row",
        )
        require(
            "| model-r | classes-model-r | unmeasured |" in rendered,
            "an overlay whose only case is tagged `reasoning` was not listed unmeasured",
        )
        require(
            "model-x | classes" not in rendered,
            "a quoted experiment_id was mis-parsed, spuriously listing model-x's overlay as unmeasured too",
        )
        require(rendered.count(renderer.START_MARKER) == 1 and rendered.count(renderer.END_MARKER) == 1, "the markers were duplicated or lost")


# A price table for `requested-model`, the default the synthetic experiment
# requests. `treated-model` has no entry here, so a run on it cannot be priced.
PARTIAL_PRICE_TABLE = """\
models:
  requested-model:
    input: 0.000001
    output: 0.000002
    cache_read: 0.0000001
    cache_write: 0.000003
    source: https://example.invalid/prices
    read_on: 2026-10-01
"""

# The same table with `treated-model` priced too.
PRICE_TABLE = PARTIAL_PRICE_TABLE + """\
  treated-model:
    input: 0.000002
    output: 0.000004
    cache_read: 0.0000002
    cache_write: 0.000006
    source: https://example.invalid/prices
    read_on: 2026-10-01
"""


def validate(record: dict[str, Any], path: Path) -> subprocess.CompletedProcess[str]:
    """Write `record` to `path` and run the recorder's validator on it."""
    path.write_text(json.dumps(record))
    return subprocess.run(
        [sys.executable, str(RECORDER), str(path), "--experiment", str(path), "--validate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def check_version_3_rules(record: dict[str, Any], temp: Path) -> None:
    """Every version-3 case rule rejects a record that breaks it."""
    require(validate(record, temp / "v3.json").returncode == 0, "a valid version-3 record was rejected")
    breaks = {
        "a missing cost": ("cost", None),
        "a non-numeric cost": ("cost", "0.05"),
        "an 'unreported' cost": ("cost", "unreported"),
        "a boolean cost": ("cost", True),
        "a negative cost": ("cost", -0.01),
        "a missing cost source": ("cost_source", None),
        "an unknown cost source": ("cost_source", "guessed"),
        "a zero elapsed time": ("elapsed_seconds", 0),
        "a negative elapsed time": ("elapsed_seconds", -1.0),
        "a missing elapsed time": ("elapsed_seconds", None),
    }
    for name, (field, value) in breaks.items():
        broken = json.loads(json.dumps(record))
        if value is None:
            del broken["cases"][0][field]
        else:
            broken["cases"][0][field] = value
        result = validate(broken, temp / "v3-broken.json")
        require(result.returncode != 0 and field in result.stdout, f"a version-3 record with {name} was accepted")
    version_2 = json.loads(json.dumps(record))
    version_2["schema_version"] = 2
    version_2["cases"][0]["cost"] = "unreported"
    require(
        validate(version_2, temp / "v2.json").returncode == 0,
        "a version-2 record with an unreported cost is no longer valid history",
    )


def check_unpriceable(run: dict[str, Any], run_dir: Path, experiment: Path, temp: Path, env: dict[str, str]) -> None:
    """A token-only row the table cannot price, or with no tokens, fails to record."""
    unpriced = json.loads(json.dumps(run))
    unpriced_path = run_dir / "run.json"
    prices = temp / "partial-prices.yaml"
    prices.write_text(PARTIAL_PRICE_TABLE)
    original = unpriced_path.read_text()
    try:
        # `treated-model`, requested by the with-plugin variant, has no entry.
        unpriced_path.write_text(json.dumps(unpriced))
        result = recorder_result(run_dir, experiment, temp / "unpriced", env, prices)
        require(
            result.returncode != 0 and "treated-model" in result.stderr and "price table" in result.stderr,
            "a token-only row whose model has no price-table entry was recorded",
        )
        require(not (temp / "unpriced").exists(), "a record was written for a run that could not be priced")
        thinking = temp / "thinking.yaml"
        thinking.write_text(experiment.read_text().replace("treated-model", "requested-model:high"))
        for row in unpriced["task_results"]:
            row["agent_config"]["model"] = "requested-model:high" if row["variant_id"] == "with-plugin" else row["agent_config"]["model"]
        unpriced_path.write_text(json.dumps(unpriced))
        result = recorder_result(run_dir, thinking, temp / "thinking", env, prices)
        require(result.returncode == 0, f"a :<level> suffix was not stripped for the price lookup: {result.stderr}")
        for row in unpriced["task_results"]:
            for field in ("input_tokens", "output_tokens"):
                row.pop(field, None)
        unpriced_path.write_text(json.dumps(unpriced))
        result = recorder_result(run_dir, thinking, temp / "tokenless", env, prices)
        require(
            result.returncode != 0 and "neither a price nor token counts" in result.stderr and "requested-model" in result.stderr,
            "a harness reporting neither a price nor tokens was recorded",
        )
        require("replicate 0 (SUCCESS)" in result.stderr, "an unpriceable row's error did not name its replicate and status")
        for row in unpriced["task_results"]:
            row["input_tokens"], row["output_tokens"] = 10, 10
        for duration in (0.0, None):
            unpriced["task_results"][2]["duration"] = duration
            if duration is None:
                del unpriced["task_results"][2]["duration"]
            unpriced_path.write_text(json.dumps(unpriced))
            result = recorder_result(run_dir, thinking, temp / "no-duration", env, prices)
            require(
                result.returncode != 0 and "no positive wall time" in result.stderr and "one/with-plugin replicate 0" in result.stderr,
                f"a replicate with duration {duration!r} did not fail naming it",
            )
    finally:
        unpriced_path.write_text(original)


def check_subscription_recording(
    run: dict[str, Any],
    run_dir: Path,
    experiment: Path,
    temp: Path,
    env: dict[str, str],
    prices: Path,
) -> None:
    """Codex subscription records must not use API prices or lose token usage."""
    experiment_text = experiment.read_text()
    subscription_experiment = temp / "subscription.yaml"
    subscription_experiment.write_text(
        experiment_text.replace("requested-model", "openai-codex/gpt-6-luna").replace(
            "treated-model", "openai-codex/gpt-6-luna"
        )
    )
    run_path = run_dir / "run.json"
    original = run_path.read_text()
    codex_run = json.loads(json.dumps(run))
    for row in codex_run["task_results"]:
        row["agent_config"]["model"] = "openai-codex/gpt-6-luna"
    try:
        run_path.write_text(json.dumps(codex_run))
        record_path = run_recorder(run_dir, subscription_experiment, temp / "subscription", env, prices)
        record = json.loads(record_path.read_text())
        require(record["schema_version"] == 4, "the subscription record did not use schema version 4")
        require(
            all(case["cost"] is None and case["cost_source"] == "subscription" for case in record["cases"]),
            "an Omp Codex subscription was given an API-equivalent dollar cost",
        )
        require(record["cases"][0]["tokens"] == 1000, "subscription recording discarded reported token usage")
        recorder = load_recorder()
        judge_model = "openai-codex/gpt-6.1-sol"
        judge = recorder.judge_block(
            {
                "judge": {"route": "omp", "model_requested": judge_model, "judge_id": "omp-gpt-6.1-sol"},
                "prompt_version": "synthetic-v1",
                "freeze_sha": "abc123",
                "criterion_errors": [],
            },
            {
                ("bare", "one", 0): {
                    "criteria": [
                        {
                            "observed": {"model": judge_model},
                            "usage": {"input": 10, "output": 5, "cacheRead": 2, "cacheWrite": 1},
                        }
                    ]
                }
            },
            [],
            ROOT,
        )
        require(
            judge["cost_source"] == "subscription"
            and judge["usage"] == {"input": 10, "output": 5, "cacheRead": 2, "cacheWrite": 1},
            "the Codex judge lost its subscription source or token usage",
        )
        record["judge"] = judge
        require(not recorder.validate_record(record), "the subscription judge record failed schema validation")
        invalid = json.loads(json.dumps(record))
        invalid["cases"][0]["model_requested"] = "openai-codex/gpt-6-unknown"
        require(
            any("approved Omp Codex model" in error for error in recorder.validate_record(invalid)),
            "an unknown Codex model was accepted as a subscription",
        )
        for row in codex_run["task_results"]:
            row["agent_config"]["model"] = "openai-codex/gpt-6-unknown"
        unknown_experiment = temp / "unknown-codex.yaml"
        unknown_experiment.write_text(
            experiment_text.replace("requested-model", "openai-codex/gpt-6-unknown").replace(
                "treated-model", "openai-codex/gpt-6-unknown"
            )
        )
        run_path.write_text(json.dumps(codex_run))
        result = recorder_result(run_dir, unknown_experiment, temp / "unknown-codex", env, prices)
        require(
            result.returncode != 0 and "openai-codex/gpt-6-unknown" in result.stderr and "price table" in result.stderr,
            "an unknown Codex model did not fail closed without a price-table entry",
        )
    finally:
        run_path.write_text(original)


def load_results_renderer() -> Any:
    """Import `evals-render-results.py` under a valid module name."""
    spec = importlib.util.spec_from_file_location("evals_render_results", RESULTS_RENDERER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_results_renderer() -> None:
    """The results page prices only what was priced, and `--check` catches a stale page."""
    renderer = load_results_renderer()

    def record(run_id: str, version: int, client: str, costs: list[Any], statuses: list[str], served: str = "m") -> dict[str, Any]:
        return {
            "schema_version": version,
            "run_id": run_id,
            "experiment_id": f"exp-{run_id}",
            "started_at": f"2026-09-0{run_id[-1]}T10:00:00",
            "completed_at": f"2026-09-0{run_id[-1]}T11:02:03",
            "client": {"name": client},
            "variants": [{"model_requested": "req", "model_served": served}],
            "attempts": [
                {"final_status": status, "answer_key_contact": ["reached"] if index == 9 else []}
                for index, status in enumerate(statuses)
            ],
            "cases": [{"cost": cost} for cost in costs] if version > 1 else None,
        }

    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        provenance = temp / "provenance"
        provenance.mkdir()
        records = {
            "run1": record("run1", 1, "claude-code", [], ["SUCCESS", "FAILURE"]),
            "run2": record("run2", 2, "omp", [0.5, 0.5], ["SUCCESS", "SUCCESS"], served="unknown"),
            "run3": record("run3", 3, "omp", [1.0, 2.0, 0.5], ["SUCCESS", "SUCCESS", "FAILURE"]),
            "run4": record("run4", 3, "codex", [0.25], ["FAILURE"]),
            "run5": record("run5", 2, "claude-code", [1.0, "unreported"], ["SUCCESS", "SUCCESS"]),
            "run6": record("run6", 4, "omp", [None, None], ["SUCCESS", "SUCCESS"]),
            "run7": record("run7", 4, "omp", [None, 0.1], ["SUCCESS", "SUCCESS"]),
            "run8": record("run8", 4, "omp", [None], ["SUCCESS"]),
        }
        for case in records["run6"]["cases"]:
            case.update({"cost": None, "cost_source": "subscription", "model_requested": "openai-codex/gpt-6-luna"})
        records["run7"]["cases"] = [
            {"cost": None, "cost_source": "subscription", "model_requested": "openai-codex/gpt-6-luna"},
            {"cost": 0.1, "cost_source": "reported", "model_requested": "reported-model"},
        ]
        records["run8"]["cases"] = [
            {"cost": None, "cost_source": "subscription", "model_requested": "openai-codex/gpt-6-unknown"}
        ]
        for name, value in records.items():
            (provenance / f"{name}.json").write_text(json.dumps(value))
        page = renderer.render_page(renderer.load_records(provenance))
        rows = [line for line in page.splitlines() if line.startswith("| 2026-")]
        require(len(rows) == len(records), "the results page did not carry one row per record")
        require(
            "| 2026-09-01 | exp-run1 | claude-code | m | not recorded | 2 | 1/2 | not recorded | not recorded | 1h 02m 03s |" in rows,
            "a record with no price was not shown `not recorded`",
        )
        require(
            "| 2026-09-02 | exp-run2 | omp | req (requested) | not recorded | 2 | 2/2 | not recorded | not recorded | 1h 02m 03s |" in rows,
            "a version-2 non-Claude price -- the judge's alone -- was shown, or the requested model was not marked",
        )
        require("| 3 | 2/3 | $3.50 | $1.75 |" in rows[2], "a version-3 price or its per-completed-task figure was wrong")
        require("| 1 | 0/1 | $0.25 | no task completed |" in rows[3], "a run with no pass divided by zero")
        require("| not recorded | not recorded |" in rows[4], "a partly priced record was shown as a whole price")
        require("| 2 | 2/2 | subscription | subscription |" in rows[5], "an Omp Codex subscription was given a dollar price or hidden")
        require("| not recorded | not recorded |" in rows[6], "a mixed subscription and dollar total was rendered as complete")
        require("| not recorded | not recorded |" in rows[7], "an unknown Codex model was labeled as a subscription")
        require("$0.00" not in page, "a missing price was rendered as $0")
        require(renderer.judge_text({"judge": {"selection": "run-selected", "judge_id": "omp-glm-5.3"}}) == "omp-glm-5.3 (run-selected)", "a run-selected judge was not named")
        require(
            renderer.judge_text({"judge": {"selection": "task-pinned", "route": "claude-code", "model_requested": ["claude-sonnet-5"]}})
            == "claude-code claude-sonnet-5 (task-pinned)",
            "a task-pinned judge was not named",
        )
        require(renderer.judge_text({}) == "not recorded", "a record with no judge provenance was given one")

        target = temp / "RESULTS.md"
        target.write_text(page)
        script = [sys.executable, str(RESULTS_RENDERER), "--provenance-dir", str(provenance), "--target", str(target), "--check"]
        fresh = subprocess.run(script, capture_output=True, text=True, check=False)
        require(fresh.returncode == 0, f"a fresh page was reported stale: {fresh.stderr}")
        (provenance / "run6.json").write_text(json.dumps(record("run6", 3, "omp", [1.0], ["SUCCESS"])))
        stale = subprocess.run(script, capture_output=True, text=True, check=False)
        require(stale.returncode != 0 and "stale" in stale.stderr, "a page missing a committed record's row passed --check")


def validate_committed_records() -> None:
    """Validate every committed provenance record in the repository."""
    records_dir = ROOT / "evals" / "provenance"
    for record in sorted(records_dir.glob("*.json")):
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(record), "--experiment", str(ROOT / "evals/experiments/with-without.yaml"), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(result.returncode == 0, f"{record}: {result.stdout}{result.stderr}")


def load_recorder() -> Any:
    """Import the recorder module, whose file name is not an identifier."""
    spec = importlib.util.spec_from_file_location("evals_record", RECORDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classes_artifact(*commands: dict[str, Any], description: str = "jmcvetta/career#469: perf: a change") -> dict[str, Any]:
    """A model-classes task artifact whose one iteration ran `commands`."""
    return {
        "task_id": "model-classes-career-469",
        "task_description": description,
        "iterations": [{"commands": list(commands)}],
    }


def bash(command: str, result: str = "") -> dict[str, Any]:
    """One recorded Bash call."""
    return {"tool_name": "Bash", "parameters": {"command": command}, "result_summary": result}


def check_answer_key_contact() -> None:
    """Every road to the answer is flagged, and ordinary work is not."""
    recorder = load_recorder()
    root = Path("/srv/daily-driver")
    clean = [
        bash("git status && git diff --stat"),
        bash('git commit -qam "fetch the pull refs lazily"'),
        bash("git -C kokoro log --oneline -5"),
        bash("gh issue view 2853 --repo googleapis/release-please"),
        bash("gh api repos/googleapis/release-please/issues/2853"),
        bash("curl -s https://api.github.com/repos/googleapis/release-please/issues/2853"),
        bash("cat .fixture/apply-tests.sh", 'patch="${REFERENCE_DIR:?}/tests.patch"'),
        bash("grep -rn compile-bytecode .", "./kokoro/pyproject.toml:12:compile-bytecode = true"),
        {"tool_name": "WebFetch", "parameters": {"url": "https://github.com/googleapis/release-please/issues/2853"}},
        {"tool_name": "Edit", "parameters": {"file_path": "README.md", "new_string": "see github.com/jmcvetta/career-scan"}},
    ]
    for command in clean:
        evidence = recorder.answer_key_contact(classes_artifact(command), root)
        require(evidence == [], f"ordinary work was flagged: {command} -> {evidence}")

    reaching = {
        "names the old in-sandbox key": bash("cat .fixture/tests.patch"),
        "prints the key from a broad grep": bash("grep -rn bytecode .", "./.fixture/tests.patch:34:+    compile"),
        "names the staged reference": bash("ls /tmp/coder_eval_reference_ab12/reference"),
        "reads this repository's fixtures": bash("find / -name tests.patch", "/srv/daily-driver/evals/x"),
        "fetches the default branch": bash("git fetch origin master"),
        "fetches with a global option first": bash("git -C . fetch https://github.com/jmcvetta/career"),
        "adds a remote": bash("git remote add upstream https://example.invalid/x.git"),
        "reads a pull ref": bash("git log refs/pull/469/head"),
        "views a pull request": bash("gh pr view 469"),
        "views the issue on the checkout's repo": bash("gh issue view 468"),
        "views the issue with the source named": bash("gh issue view 468 -R jmcvetta/career"),
        "calls the API on the source": bash("gh api repos/jmcvetta/career/pulls/469"),
        "searches GitHub": bash('gh search prs "compile bytecode"'),
        "curls the source": bash("curl -s https://api.github.com/repos/jmcvetta/career/pulls/469"),
        "downloads the diff": bash("curl -sS https://patch-diff.githubusercontent.com/raw/jmcvetta/career/pull/469.diff"),
        "fetches the source page": {"tool_name": "WebFetch", "parameters": {"url": "https://github.com/jmcvetta/career/pull/469"}},
    }
    for name, command in reaching.items():
        evidence = recorder.answer_key_contact(classes_artifact(command), root)
        require(len(evidence) == 1, f"{name} was not flagged: {command}")

    try:
        recorder.answer_key_contact(classes_artifact(bash("ls"), description="no source here"), root)
    except ValueError:
        pass
    else:
        raise Failed("a model-classes artifact with no source repository was scanned as clean")


def check_contaminated_replicate(temp: Path) -> None:
    """A replicate that reached the answer is recorded, and scored 0."""
    run_dir = temp / "runs" / "2026-09-28_10-00-00"
    run_dir.mkdir(parents=True)
    experiment = temp / "classes.yaml"
    experiment.write_text("experiment_id: classes\ndefaults:\n  agent:\n    model: m\nvariants:\n  - variant_id: default\n")
    task_id = "model-classes-career-469"
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": "2026-09-28_10-00-00",
                "start_time": "2026-09-28T10:00:00+00:00",
                "end_time": "2026-09-28T10:02:00+00:00",
                "task_results": [
                    {
                        "task_id": task_id,
                        "variant_id": "default",
                        "replicate_index": index,
                        "weighted_score": 1.0,
                        "agent_config": {"type": "claude-code", "model": "m"},
                        "duration": 30.0,
                        "agent_cost_usd": 0.1,
                        "total_cost_usd": 0.1,
                    }
                    for index in (0, 1)
                ],
            }
        )
    )
    for index, command in enumerate((bash("git diff"), bash("git fetch origin master"))):
        artifact_dir = run_dir / "default" / task_id / f"{index:02d}"
        artifact_dir.mkdir(parents=True)
        artifact = classes_artifact(command)
        artifact.update({"weighted_score": 1.0, "success_criteria_results": [], "early_stop": None})
        (artifact_dir / "task.json").write_text(json.dumps(artifact))
    (run_dir / "experiment.json").write_text(
        json.dumps(
            {
                "experiment_id": "classes",
                "variant_ids": ["default"],
                "per_replicate_scores": {"default": {task_id: [1.0, 1.0]}},
            }
        )
    )
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    record_path = run_recorder(run_dir, experiment, temp / "classes-out", env)
    record = json.loads(record_path.read_text())
    clean, reached = record["attempts"]
    require(clean["answer_key_contact"] == [] and clean["measured_score"] == 1.0, "a clean replicate lost its score")
    require(reached["answer_key_contact"], "the git fetch replicate carries no evidence")
    require(reached["measured_score"] == 0.0, "a replicate that reached the answer kept its score")
    require(reached["raw_weighted_score"] == 1.0, "the raw score was not kept beside the measured one")
    require(
        record["variants"][0]["per_replicate_scores"][task_id] == [1.0, 0.0],
        "per_replicate_scores still count the replicate that reached the answer",
    )
    reached["measured_score"] = 1.0
    record_path.write_text(json.dumps(record))
    result = subprocess.run(
        [sys.executable, str(RECORDER), str(record_path), "--experiment", str(experiment), "--validate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    require(
        result.returncode != 0 and "answer_key_contact" in result.stdout,
        "a record scoring a contaminated replicate above 0 was accepted",
    )


def check_eval_result_comment() -> None:
    """The comment renders from a fixture record; the marker decides edit or create."""
    recorder = load_recorder()
    cases = []
    for model, outcomes in (("m/a:high", ["succeeded", "succeeded", "failed"]), ("m/b", ["error", "failed", "failed"])):
        for index, outcome in enumerate(outcomes):
            cases.append(
                {
                    **_case_row("t", "implementation", outcome, index, model_requested=model, settings="s"),
                    "variant_id": "bare",
                    "elapsed_seconds": 360.0 + 60 * index,
                    "source": "o/r#7",
                }
            )
    cases.append({**_case_row("u", "implementation", "succeeded", 0, model_requested="m/a:high", settings="s"), "source": "o/r#8"})
    record = {"run_id": "run-1", "started_at": "2026-10-03T10:00:00+00:00", "cases": cases}
    body = recorder.render_comment(record, "o/r#7", "evals/provenance/x.json")
    require(body.startswith("<!-- eval-result: run-1 -->\n## Eval result"), "comment opens with the run marker")
    require("| `m/a:high` | bare | pass 2/3 | 7 min median |" in body, "repeats collapse to pass n/m and a median")
    require("| `m/b` | bare | pass 0/3 | 7 min median |" in body, "a failed run still posts a row")
    require("o/r#8" not in body and body.count("| `m/a:high`") == 1, "only the pull request's own cases appear")
    require("Run `run-1`, recorded in `evals/provenance/x.json`." in body, "the comment cites the record")
    older = [{"id": 1, "body": "unrelated"}, {"id": 2, "body": "<!-- eval-result: run-0 -->\nold"}]
    require(recorder.find_result_comment(older, "run-1") is None, "a different run's marker means create")
    older.append({"id": 3, "body": body})
    require(recorder.find_result_comment(older, "run-1")["id"] == 3, "the same run's marker means edit")


def main() -> int:
    """Run laptop, cloud, invalid-record, committed-record and answer-key cases."""
    validate_committed_records()
    check_answer_key_contact()
    check_eval_result_comment()
    with tempfile.TemporaryDirectory() as directory:
        check_contaminated_replicate(Path(directory))
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        run_dir = temp / "runs" / "2026-09-21_10-00-00"
        run_dir.mkdir(parents=True)
        experiment = temp / "experiment.yaml"
        experiment.write_text(
            """experiment_id: synthetic\ndefaults:\n  agent:\n    model: requested-model\nvariants:\n  - variant_id: bare\n  - variant_id: with-plugin\n    agent:\n      model: treated-model\n"""
        )
        (run_dir / "run.json").write_text(
            json.dumps(
                {
                    "run_id": "2026-09-21_10-00-00",
                    "start_time": "2026-09-21T10:00:00+00:00",
                    "end_time": "2026-09-21T10:02:00+00:00",
                    "framework_version": "0.11.6",
                    "task_results": [
                        {
                            "task_id": "one",
                            "variant_id": "bare",
                            "agent_config": {
                                "type": "claude-code",
                                "model": "requested-model",
                            },
                            "status": "SUCCESS",
                            "tags": ["model-classes", "class:mechanical"],
                            "duration": 12.5,
                            "total_tokens": 1000,
                            "input_tokens": 600,
                            "output_tokens": 400,
                            "agent_cost_usd": 0.04,
                            "total_cost_usd": 0.05,
                        },
                        {
                            "task_id": "one",
                            "variant_id": "bare",
                            "agent_config": {
                                "type": "claude-code",
                                "model": "requested-model",
                            },
                            "status": "FAILURE",
                            "tags": ["model-classes", "class:mechanical"],
                            "duration": 9.0,
                            "input_tokens": 100,
                            "output_tokens": 10,
                            "cache_read_input_tokens": 1000,
                            "cache_creation_input_tokens": 50,
                            "agent_cost_usd": None,
                            "judge_cost_usd": 0.5,
                            "total_cost_usd": 0.5,
                        },
                        {
                            "task_id": "one",
                            "variant_id": "with-plugin",
                            "agent_config": {
                                "type": "claude-code",
                                "model": "treated-model",
                            },
                            "model_used": "served-model",
                            "status": "SUCCESS",
                            "tags": [],
                            "duration": 5.0,
                            "input_tokens": 100,
                            "output_tokens": 100,
                            "agent_cost_usd": 0.02,
                            "total_cost_usd": 0.02,
                        },
                    ],
                }
            )
        )
        for variant_id in ("bare", "with-plugin"):
            artifact_dir = run_dir / variant_id / "one" / "00"
            artifact_dir.mkdir(parents=True)
            (artifact_dir / "task.json").write_text(
                json.dumps(
                    {
                        "success_criteria_results": [
                            {"criterion_type": "synthetic", "score": 1.0, "error": None}
                        ],
                        "early_stop": None,
                    }
                )
            )
        (run_dir / "experiment.json").write_text(
            json.dumps(
                {
                    "experiment_id": "synthetic",
                    "variant_ids": ["bare", "with-plugin"],
                    "per_replicate_scores": {
                        "bare": {"one": [0.0]},
                        "with-plugin": {"one": [1.0]},
                    },
                }
            )
        )
        prices = temp / "prices.yaml"
        prices.write_text(PRICE_TABLE)
        base_env = os.environ.copy()
        base_env.pop("CLAUDE_CODE_SESSION_ID", None)
        laptop = json.loads(run_recorder(run_dir, experiment, temp / "laptop", base_env, prices).read_text())
        require(laptop["host"]["kind"] == "laptop", "laptop run was not recorded as laptop")
        require(laptop["variants"][0]["model_served"] == "unknown", "missing served model was fabricated")
        require(laptop["variants"][1]["model_requested"] == "treated-model", "variant request was not recorded")
        require(laptop["variants"][0]["task_ids"] == ["one"], "task ids were not de-duplicated")
        require(laptop["client"]["name"] == "claude-code", "client type was not read from agent_config")
        require(len(laptop["attempts"]) == 3, "attempt-level evidence was not recorded")
        require(laptop["attempts"][0]["criteria"][0]["criterion_type"] == "synthetic", "criterion evidence was not recorded")
        require(laptop["schema_version"] == 4, "schema_version was not bumped to 4")
        require(len(laptop["cases"]) == 3, "case rows were not recorded one per task result")
        passed, failed = laptop["cases"][0], laptop["cases"][1]
        require(passed["class"] == "mechanical", "class tag was not read from the row's tags")
        require(passed["outcome"] == "succeeded", "a SUCCESS status did not categorise as succeeded")
        require(failed["outcome"] == "failed", "a FAILURE status did not categorise as failed")
        require(passed["tokens"] == 1000 and passed["cost"] == 0.05, "reported tokens/cost were not recorded")
        require(passed["cost_source"] == "reported", "a harness-reported price was not marked reported")
        # 100 x 1e-6 + 10 x 2e-6 + 1000 x 1e-7 + 50 x 3e-6, plus the 0.5 judge.
        require(abs(failed["cost"] - 0.50037) < 1e-9, f"a token-only row was mispriced: {failed['cost']}")
        require(failed["cost_source"] == "computed", "a table-priced row was not marked computed")
        require(failed["tokens"] == "unreported", "missing total tokens were not marked unreported")
        require(passed["model_served"] == "unreported", "case model_served used a different sentinel than 'unreported'")
        require(passed["model_requested"] == "requested-model", "case model_requested was not read from the experiment")
        require(passed["settings"] == "synthetic", "case settings did not carry the experiment_id")
        untagged = laptop["cases"][2]
        require(untagged["class"] is None, "a row with no class: tag was given a class")
        run = json.loads((run_dir / "run.json").read_text())
        for row in run["task_results"]:
            row["agent_config"]["type"] = "omp"
            row["model_used"] = "requested-model"
            row["agent_cost_usd"] = None
        (run_dir / "run.json").write_text(json.dumps(run))
        omp = json.loads(run_recorder(run_dir, experiment, temp / "omp", base_env, prices).read_text())
        require(
            all(case["cost_source"] == "computed" for case in omp["cases"]),
            "a token-only harness's judge-only total was recorded as its reported price",
        )
        require(
            abs(omp["cases"][0]["cost"] - 0.0014) < 1e-9,
            "a token-only row was priced from total_cost_usd instead of its tokens",
        )
        check_unpriceable(run, run_dir, experiment, temp, base_env)
        check_subscription_recording(run, run_dir, experiment, temp, base_env, prices)
        require(omp["variants"][0]["model_served"] == "unknown", "Omp request was recorded as served")
        require(
            all(case["model_served"] == "unreported" for case in omp["cases"]),
            "Omp case rows recorded a served model instead of 'unreported'",
        )
        require(omp["client"]["version"] == "unknown", "Omp recorder version was recorded as historical evidence")
        wrong_experiment = temp / "wrong-experiment.yaml"
        wrong_experiment.write_text(
            experiment.read_text().replace("experiment_id: synthetic", "experiment_id: wrong")
        )
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(run_dir), "--experiment", str(wrong_experiment)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "experiment_id" in result.stderr,
            "mismatched experiment file was accepted",
        )
        changed_model_experiment = temp / "changed-model-experiment.yaml"
        changed_model_experiment.write_text(experiment.read_text().replace("treated-model", "other-model"))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(run_dir), "--experiment", str(changed_model_experiment)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "experiment model" in result.stderr,
            "changed experiment model was accepted",
        )
        run["task_results"][1]["agent_config"]["model"] = "other-model"
        (run_dir / "run.json").write_text(json.dumps(run))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(run_dir), "--experiment", str(experiment)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "experiment model" in result.stderr,
            "mixed resolved models were accepted",
        )
        run["task_results"][1]["agent_config"]["model"] = "requested-model"
        (run_dir / "run.json").write_text(json.dumps(run))
        cloud_env = {**base_env, "CLAUDE_CODE_SESSION_ID": "session-123"}
        cloud = json.loads(run_recorder(run_dir, experiment, temp / "cloud", cloud_env, prices).read_text())
        require(cloud["host"]["kind"] == "cloud", "web session was not recorded as cloud")
        require(cloud["host"]["session_id"] == "session-123", "session id was not recorded")
        missing = dict(cloud)
        del missing["coder_eval_version"]
        invalid = temp / "invalid.json"
        invalid.write_text(json.dumps(missing))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(invalid), "--experiment", str(experiment), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "coder_eval_version" in result.stdout,
            "record missing a required field was accepted",
        )
        cloud["host"]["session_id"] = None
        invalid.write_text(json.dumps(cloud))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(invalid), "--experiment", str(experiment), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "host.session_id" in result.stdout,
            "cloud record without a session id was accepted",
        )
        cloud["host"]["session_id"] = "session-123"
        cloud["host"]["kind"] = "desktop"
        invalid.write_text(json.dumps(cloud))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(invalid), "--experiment", str(experiment), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(result.returncode != 0 and "host.kind" in result.stdout, "invalid host kind was accepted")
        missing_cases = dict(laptop)
        del missing_cases["cases"]
        invalid.write_text(json.dumps(missing_cases))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(invalid), "--experiment", str(experiment), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "cases" in result.stdout,
            "a schema_version 2 record with no cases was accepted",
        )
        bad_case = dict(laptop)
        bad_case["cases"] = [dict(laptop["cases"][0])]
        del bad_case["cases"][0]["model_requested"]
        invalid.write_text(json.dumps(bad_case))
        result = subprocess.run(
            [sys.executable, str(RECORDER), str(invalid), "--experiment", str(experiment), "--validate"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        require(
            result.returncode != 0 and "model_requested" in result.stdout,
            "a case row missing model_requested was accepted",
        )
        legacy_v3 = json.loads(json.dumps(laptop))
        legacy_v3["schema_version"] = 3
        check_version_3_rules(legacy_v3, temp)
    check_renderer()
    check_results_renderer()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Failed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)
