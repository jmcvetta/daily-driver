#!/usr/bin/env python3
"""Exercise the eval provenance recorder with offline synthetic artifacts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RECORDER = ROOT / "scripts" / "evals-record.py"


class Failed(Exception):
    """A synthetic provenance case did not hold."""


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
                        },
                        {
                            "task_id": "one",
                            "variant_id": "bare",
                            "agent_config": {
                                "type": "claude-code",
                                "model": "requested-model",
                            },
                        },
                        {
                            "task_id": "one",
                            "variant_id": "with-plugin",
                            "agent_config": {
                                "type": "claude-code",
                                "model": "treated-model",
                            },
                            "model_used": "served-model",
                        },
                    ],
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
        run = json.loads((run_dir / "run.json").read_text())
        for row in run["task_results"]:
            row["agent_config"]["type"] = "omp"
            row["model_used"] = "requested-model"
        (run_dir / "run.json").write_text(json.dumps(run))
        omp = json.loads(run_recorder(run_dir, experiment, temp / "omp", base_env).read_text())
        require(omp["variants"][0]["model_served"] == "unknown", "Omp request was recorded as served")
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
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Failed as failure:
        print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)
