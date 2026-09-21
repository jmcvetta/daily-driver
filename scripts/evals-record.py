#!/usr/bin/env python3
"""Record durable provenance for one coder_eval run."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - the repository's uv environment has PyYAML.
    yaml = None

REQUIRED_RECORD_FIELDS = {
    "schema_version",
    "run_id",
    "experiment_id",
    "started_at",
    "completed_at",
    "recorded_at",
    "plugin_revision",
    "coder_eval_version",
    "client",
    "host",
    "variants",
}


def command_version(command: str) -> str:
    """Return a client version, or ``unknown`` when the client is unavailable."""
    executable = shutil.which(command)
    if executable is None:
        return "unknown"
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    output = (result.stdout or result.stderr).strip()
    return output if result.returncode == 0 and output else "unknown"


def git_value(root: Path, *args: str) -> str:
    """Return a git value from ``root``, or ``unknown`` on a missing repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else "unknown"


def git_is_dirty(root: Path) -> bool:
    """Return whether ``root`` has uncommitted or untracked repository changes."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    return result.returncode != 0 or bool(result.stdout.strip())


def experiment_models(experiment_path: Path) -> dict[str, str]:
    """Read each variant's requested model from an experiment YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to read experiment files")
    data = yaml.safe_load(experiment_path.read_text()) or {}
    defaults = data.get("defaults", {}).get("agent", {}).get("model", "unknown")
    models: dict[str, str] = {}
    for variant in data.get("variants", []):
        agent = variant.get("agent", {})
        models[variant["variant_id"]] = agent.get("model", defaults)
    return models


def run_model(run: dict[str, Any], variant_id: str) -> str:
    """Return the served model for one variant without copying its request."""
    served = {
        row.get("model_used")
        for row in run.get("task_results", [])
        if row.get("variant_id") == variant_id and row.get("model_used")
    }
    return served.pop() if len(served) == 1 else "unknown"


def run_task_ids(run: dict[str, Any], variant_id: str) -> list[str]:
    """Return distinct task ids in run order for one variant."""
    task_ids: list[str] = []
    seen: set[str] = set()
    for row in run.get("task_results", []):
        task_id = row.get("task_id")
        if row.get("variant_id") == variant_id and task_id and task_id not in seen:
            task_ids.append(task_id)
            seen.add(task_id)
    return task_ids


def build_record(run_dir: Path, experiment_path: Path, root: Path) -> dict[str, Any]:
    """Build a committed provenance record from a coder_eval run directory."""
    run = json.loads((run_dir / "run.json").read_text())
    experiment = json.loads((run_dir / "experiment.json").read_text())
    requested = experiment_models(experiment_path)
    variants = []
    for variant_id in experiment["variant_ids"]:
        variants.append(
            {
                "variant_id": variant_id,
                "model_requested": requested.get(variant_id, "unknown"),
                "model_served": run_model(run, variant_id),
                "task_ids": run_task_ids(run, variant_id),
                "per_replicate_scores": experiment["per_replicate_scores"].get(variant_id, {}),
            }
        )

    client_name = run.get("task_results", [{}])[0].get("agent_type", "unknown")
    client_command = {
        "claude-code": "claude",
        "omp": "omp",
        "codex-daily-driver": "codex",
    }.get(client_name, "unknown")
    client_version = command_version(client_command) if client_command != "unknown" else "unknown"
    session_present = "CLAUDE_CODE_SESSION_ID" in os.environ
    return {
        "schema_version": 1,
        "run_id": run["run_id"],
        "experiment_id": experiment["experiment_id"],
        "started_at": run["start_time"],
        "completed_at": run["end_time"],
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "plugin_revision": {
            "commit": git_value(root, "rev-parse", "HEAD"),
            "dirty": git_is_dirty(root),
        },
        "coder_eval_version": run.get("framework_version", "unknown"),
        "client": {
            "name": client_name,
            "version": client_version,
        },
        "host": {
            "kind": "cloud" if session_present else "laptop",
            "hostname": socket.gethostname(),
            "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID") if session_present else None,
            "platform": platform.platform(),
        },
        "variants": variants,
    }

def validate_record(record: dict[str, Any]) -> list[str]:
    """Return validation errors for one provenance record."""
    errors = sorted(REQUIRED_RECORD_FIELDS - record.keys())
    if record.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("run_id", "experiment_id", "started_at", "completed_at"):
        if not isinstance(record.get(field), str) or not record[field]:
            errors.append(f"{field} must be a non-empty string")
    revision = record.get("plugin_revision", {})
    if not isinstance(revision, dict) or not isinstance(revision.get("commit"), str) or not isinstance(revision.get("dirty"), bool):
        errors.append("plugin_revision must contain commit and dirty")
    client = record.get("client", {})
    if not isinstance(client, dict) or not client.get("name") or not client.get("version"):
        errors.append("client must contain name and version")
    host = record.get("host", {})
    if not isinstance(host, dict) or host.get("kind") not in {"laptop", "cloud"}:
        errors.append("host.kind must be laptop or cloud")
    if not isinstance(host, dict) or not host.get("hostname"):
        errors.append("host.hostname must be non-empty")
    if not isinstance(record.get("variants"), list) or not record["variants"]:
        errors.append("variants must be non-empty")
    else:
        for index, variant in enumerate(record["variants"]):
            prefix = f"variants[{index}]"
            if not isinstance(variant, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("variant_id", "model_requested", "model_served"):
                if not isinstance(variant.get(field), str) or not variant[field]:
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            if not isinstance(variant.get("task_ids"), list):
                errors.append(f"{prefix}.task_ids must be a list")
            if not isinstance(variant.get("per_replicate_scores"), dict):
                errors.append(f"{prefix}.per_replicate_scores must be an object")
    return errors


def parse_args() -> argparse.Namespace:
    """Parse recorder command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path, help="coder_eval run directory")
    parser.add_argument("--experiment", type=Path, required=True, help="experiment YAML")
    parser.add_argument("--output", type=Path, default=Path("evals/provenance"))
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Record one run, or validate an existing record when requested."""
    args = parse_args()
    if args.validate:
        errors = validate_record(json.loads(args.run.read_text()))
        if errors:
            for error in errors:
                print(error)
            return 1
        return 0
    root = Path(__file__).resolve().parent.parent
    record = build_record(args.run, args.experiment, root)
    errors = validate_record(record)
    if errors:
        raise SystemExit("invalid generated record:\n" + "\n".join(errors))
    args.output.mkdir(parents=True, exist_ok=True)
    date = record["started_at"][:10]
    path = args.output / f"{record['experiment_id']}-{date}-{record['run_id']}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
