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

ROOT = Path(__file__).resolve().parent.parent
RECORDER = ROOT / "scripts" / "evals-record.py"
RENDERER = ROOT / "scripts" / "evals-render-routes.py"


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


def run_recorder(run_dir: Path, experiment: Path, output: Path, env: dict[str, str]) -> Path:
    """Run the recorder and return its generated record path."""
    result = subprocess.run(
        [sys.executable, str(RECORDER), str(run_dir), "--experiment", str(experiment), "--output", str(output)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
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
    cost: float | str = "unreported",
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
    """Exercise `evals-render-routes.py` on a fixture record set covering a
    pass, a fail, an unreported served model, a stale row, and an unmeasured
    overlay.
    """
    renderer = load_renderer()
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

        for overlay in ("model-x", "model-y", "unmeasured-overlay"):
            (omp_configs_dir / f"{overlay}.yml").write_text("modelRoles: {}\n")

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
        require(rendered.count(renderer.START_MARKER) == 1 and rendered.count(renderer.END_MARKER) == 1, "the markers were duplicated or lost")


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


def main() -> int:
    """Run laptop, cloud, invalid-record, and committed-record cases."""
    validate_committed_records()
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
        base_env = os.environ.copy()
        base_env.pop("CLAUDE_CODE_SESSION_ID", None)
        laptop = json.loads(run_recorder(run_dir, experiment, temp / "laptop", base_env).read_text())
        require(laptop["host"]["kind"] == "laptop", "laptop run was not recorded as laptop")
        require(laptop["variants"][0]["model_served"] == "unknown", "missing served model was fabricated")
        require(laptop["variants"][1]["model_requested"] == "treated-model", "variant request was not recorded")
        require(laptop["variants"][0]["task_ids"] == ["one"], "task ids were not de-duplicated")
        require(laptop["client"]["name"] == "claude-code", "client type was not read from agent_config")
        require(len(laptop["attempts"]) == 3, "attempt-level evidence was not recorded")
        require(laptop["attempts"][0]["criteria"][0]["criterion_type"] == "synthetic", "criterion evidence was not recorded")
        require(laptop["schema_version"] == 2, "schema_version was not bumped to 2")
        require(len(laptop["cases"]) == 3, "case rows were not recorded one per task result")
        passed, failed = laptop["cases"][0], laptop["cases"][1]
        require(passed["class"] == "mechanical", "class tag was not read from the row's tags")
        require(passed["outcome"] == "succeeded", "a SUCCESS status did not categorise as succeeded")
        require(failed["outcome"] == "failed", "a FAILURE status did not categorise as failed")
        require(passed["tokens"] == 1000 and passed["cost"] == 0.05, "reported tokens/cost were not recorded")
        require(failed["tokens"] == "unreported" and failed["cost"] == "unreported", "missing tokens/cost were not marked unreported")
        require(passed["model_served"] == "unreported", "case model_served used a different sentinel than 'unreported'")
        require(passed["model_requested"] == "requested-model", "case model_requested was not read from the experiment")
        require(passed["settings"] == "synthetic", "case settings did not carry the experiment_id")
        untagged = laptop["cases"][2]
        require(untagged["class"] is None, "a row with no class: tag was given a class")
        run = json.loads((run_dir / "run.json").read_text())
        for row in run["task_results"]:
            row["agent_config"]["type"] = "omp"
            row["model_used"] = "requested-model"
        (run_dir / "run.json").write_text(json.dumps(run))
        omp = json.loads(run_recorder(run_dir, experiment, temp / "omp", base_env).read_text())
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
        cloud = json.loads(run_recorder(run_dir, experiment, temp / "cloud", cloud_env).read_text())
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
    check_renderer()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Failed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)
