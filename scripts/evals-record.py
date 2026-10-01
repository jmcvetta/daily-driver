#!/usr/bin/env python3
"""Record durable provenance for one coder_eval run."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shlex
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
    "attempts",
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


def experiment_config(experiment_path: Path) -> dict[str, Any]:
    """Read and validate an experiment YAML document."""
    if yaml is None:
        raise RuntimeError("PyYAML is required to read experiment files")
    data = yaml.safe_load(experiment_path.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{experiment_path} must contain an object")
    return data


def experiment_models(experiment: dict[str, Any]) -> dict[str, str]:
    """Read each variant's requested model from an experiment document."""
    defaults = experiment.get("defaults", {}).get("agent", {}).get("model", "unknown")
    models: dict[str, str] = {}
    for variant in experiment.get("variants", []):
        agent = variant.get("agent", {})
        models[variant["variant_id"]] = agent.get("model", defaults)
    return models


def run_model(run: dict[str, Any], variant_id: str, client_name: str) -> str:
    """Return a served model without treating Omp's requested model as served."""
    if client_name == "omp":
        return "unknown"
    served = {
        row.get("model_used")
        for row in run.get("task_results", [])
        if row.get("variant_id") == variant_id and row.get("model_used")
    }
    return served.pop() if len(served) == 1 else "unknown"


def run_requested_models(run: dict[str, Any], variant_id: str) -> set[str]:
    """Return every resolved requested model observed for one variant."""
    return {
        row["agent_config"]["model"]
        for row in run.get("task_results", [])
        if row.get("variant_id") == variant_id and row.get("agent_config", {}).get("model")
    }

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


_CLASS_TAG_RE = re.compile(r"^class:(mechanical|implementation|reasoning)$")

# Mirrors coder_eval's FinalStatus.category -- this script never imports
# coder_eval, so the mapping is kept here rather than read from the enum.
_STATUS_OUTCOME = {
    "SUCCESS": "succeeded",
    "FAILURE": "failed",
    "ERROR": "error",
    "BUILD_FAILED": "error",
    "TIMEOUT": "failed",
    "MAX_TURNS_EXHAUSTED": "failed",
    "TOKEN_BUDGET_EXCEEDED": "failed",
    "COST_BUDGET_EXCEEDED": "failed",
}


def row_class(row: dict[str, Any]) -> str | None:
    """The `class:<token>` tag on a task result row, or None where it carries none."""
    for tag in row.get("tags") or []:
        match = _CLASS_TAG_RE.match(str(tag))
        if match:
            return match.group(1)
    return None


def row_outcome(status: str) -> str:
    """The reporting category for a raw final status, or `unreported` for one
    this script does not recognise."""
    return _STATUS_OUTCOME.get(status, "unreported")


def run_cases(run: dict[str, Any], experiment_id: str, requested: dict[str, str], client_name: str) -> list[dict[str, Any]]:
    """One row per task result in `run`: model, settings, class, outcome,
    elapsed seconds, tokens and cost -- `evals-render-routes.py`'s input for
    the measured-routes table.
    """
    cases = []
    for row in run.get("task_results", []):
        variant_id = row.get("variant_id")
        model_served = "unreported" if client_name == "omp" else (row.get("model_used") or "unreported")
        tokens = row.get("total_tokens")
        cost = row.get("total_cost_usd")
        cases.append(
            {
                "task_id": row.get("task_id", "unknown"),
                "variant_id": variant_id,
                "replicate_index": row.get("replicate_index", 0),
                "class": row_class(row),
                "model_requested": requested.get(variant_id, "unknown"),
                "model_served": model_served,
                "settings": experiment_id,
                "outcome": row_outcome(row.get("status", "")),
                "elapsed_seconds": row.get("duration", 0.0),
                "tokens": tokens if isinstance(tokens, int) else "unreported",
                "cost": cost if isinstance(cost, (int, float)) else "unreported",
            }
        )
    return cases


# A model-classes row's description is "owner/repo#N: title", written by
# `scripts/evals-cases-from-prs.py`; it names the repository whose later
# history holds the answer.
_MODEL_CLASSES_SOURCE = re.compile(r"^\s*([\w.-]+/[\w.-]+)#\d+:")

# Where the answer key, or a copy of it, can be read on the host that ran the
# replicate: the fixture's old in-sandbox layout, coder_eval's staged
# reference, and this repository's own fixtures.
_ANSWER_KEY_MARKERS = (
    ".fixture/tests.patch",
    ".fixture/base-test-files",
    ".fixture/base-skip-counts",
    "coder_eval_reference_",
    "evals/fixtures/model-classes",
)

_GIT_NETWORK = {"fetch", "pull", "clone", "ls-remote"}
_GH_REPO_COMMANDS = {"pr", "issue", "repo", "browse", "run", "release", "workflow"}


def _shell_words(command: str) -> list[str]:
    """Split a shell command into words and operators, or on whitespace where
    the command does not parse (an unclosed quote in a heredoc, say)."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return command.split()


def _repo_flag(words: list[str]) -> str | None:
    """The repository a `gh` command names with `-R`/`--repo`, if any."""
    for index, word in enumerate(words):
        if word.startswith("--repo="):
            return word.split("=", 1)[1]
        if word in ("-R", "--repo") and index + 1 < len(words):
            return words[index + 1]
    return None


def _command_contacts(command: str, source: str) -> list[str]:
    """Why a shell command reaches the source repository's history, if it does.

    Every `git` network command counts, because the sandbox's clone has no
    remote and nothing the task needs is fetched. A `gh` command counts unless
    it names another repository: without `-R` it means the checkout's own.
    """
    reasons = []
    words = _shell_words(command)
    for index, word in enumerate(words):
        if word.rsplit("/", 1)[-1] not in ("git", "gh"):
            continue
        rest = words[index + 1 :]
        # Skip global options -- `git -C dir`, `git -c key=value`.
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-C", "-c", "-R", "--repo") else rest[1:]
        if not rest:
            continue
        subcommand = rest[0]
        if word.endswith("git"):
            if subcommand in _GIT_NETWORK:
                reasons.append(f"git {subcommand}")
            elif subcommand == "remote" and len(rest) > 1 and rest[1] in ("add", "set-url"):
                reasons.append(f"git remote {rest[1]}")
        elif subcommand == "search":
            reasons.append("gh search")
        elif subcommand == "api":
            named = [w for w in rest[1:] if "repos/" in w]
            if not named or any(source.lower() in w.lower() for w in named):
                reasons.append("gh api")
        elif subcommand in _GH_REPO_COMMANDS:
            other = _repo_flag(rest)
            if other is None or other.lower() == source.lower():
                reasons.append(f"gh {subcommand}")
    if "refs/pull/" in command:
        reasons.append("refs/pull/")
    return reasons


def answer_key_contact(artifact: dict[str, Any], root: Path) -> list[str]:
    """Every tool call in a model-classes replicate that reached the answer.

    The answer is the merged change: its tests in the case's reference
    directory, and the source repository's history on GitHub. A call reaches
    it by naming the key's path, by printing it (a broad grep once surfaced
    `.fixture/tests.patch` without asking for it), or by contacting the source
    repository -- any git network command, a `gh` command on that repository,
    or a URL under it. Returns one line of evidence per offending call; an
    empty list is a clean replicate.
    """
    description = artifact.get("task_description") or ""
    match = _MODEL_CLASSES_SOURCE.match(description)
    if match is None:
        raise ValueError(f"{artifact.get('task_id')}: no source repository in description {description!r}")
    source = match.group(1)
    source_url = re.compile(
        r"(?:github\.com[/:]|githubusercontent\.com/(?:raw/)?|api\.github\.com/repos/)" + re.escape(source) + r"(?![\w.-])",
        re.IGNORECASE,
    )
    markers = (*_ANSWER_KEY_MARKERS, str(root))

    evidence = []
    for iteration in artifact.get("iterations") or []:
        for command in iteration.get("commands") or []:
            tool = command.get("tool_name", "?")
            parameters = json.dumps(command.get("parameters") or {})
            result = command.get("result_summary") or ""
            reasons = [f"names {m}" for m in markers if m in parameters]
            reasons += [f"printed {m}" for m in markers if m in result and m not in parameters]
            if source_url.search(parameters):
                reasons.append(f"URL under {source}")
            shell = (command.get("parameters") or {}).get("command")
            if tool == "Bash" and isinstance(shell, str):
                reasons += _command_contacts(shell, source)
            if reasons:
                evidence.append(f"{tool}: {', '.join(dict.fromkeys(reasons))}: {parameters[:160]}")
    return evidence


def run_attempts(run_dir: Path, run: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    """Read criterion and early-stop evidence from every preserved task artifact.

    A model-classes replicate that reached the answer key is recorded with its
    evidence under `answer_key_contact` and a measured score of 0: a copied
    answer is a failure to do the work, and leaving it out instead would hide
    exactly the replicates where a model went looking because it was stuck.
    """
    attempts = []
    for result in run.get("task_results", []):
        variant_id = result["variant_id"]
        task_id = result["task_id"]
        replicate = result.get("replicate_index", 0)
        artifact_path = run_dir / variant_id / task_id / f"{replicate:02d}" / "task.json"
        if not artifact_path.is_file():
            raise ValueError(f"missing task artifact: {artifact_path}")
        artifact = json.loads(artifact_path.read_text())
        attempt = {
            "variant_id": variant_id,
            "task_id": task_id,
            "replicate_index": replicate,
            "final_status": result.get("status", "unknown"),
            "measured_score": result.get("weighted_score", 0.0),
            "raw_weighted_score": artifact.get("weighted_score", result.get("weighted_score", 0.0)),
            "criteria": artifact["success_criteria_results"],
            "early_stop": artifact.get("early_stop"),
        }
        if task_id.startswith("model-classes-"):
            attempt["answer_key_contact"] = answer_key_contact(artifact, root)
            if attempt["answer_key_contact"]:
                attempt["measured_score"] = 0.0
        attempts.append(attempt)
    return attempts


def contaminated_scores(scores: dict[str, list[Any]], attempts: list[dict[str, Any]], variant_id: str) -> dict[str, list[Any]]:
    """`scores` with every replicate that reached the answer key set to 0."""
    measured = {task_id: list(values) for task_id, values in scores.items()}
    for attempt in attempts:
        if attempt["variant_id"] != variant_id or not attempt.get("answer_key_contact"):
            continue
        values = measured.get(attempt["task_id"])
        if values is not None and attempt["replicate_index"] < len(values):
            values[attempt["replicate_index"]] = 0.0
    return measured


def build_record(run_dir: Path, experiment_path: Path, root: Path) -> dict[str, Any]:
    """Build a committed provenance record from a coder_eval run directory."""
    run = json.loads((run_dir / "run.json").read_text())
    experiment = json.loads((run_dir / "experiment.json").read_text())
    configured_experiment = experiment_config(experiment_path)
    configured_variants = [variant["variant_id"] for variant in configured_experiment.get("variants", [])]
    if configured_experiment.get("experiment_id") != experiment.get("experiment_id"):
        raise ValueError("experiment file does not match run artifact experiment_id")
    if configured_variants != experiment.get("variant_ids"):
        raise ValueError("experiment file does not match run artifact variants")
    requested = experiment_models(configured_experiment)
    client_name = run.get("task_results", [{}])[0].get("agent_config", {}).get(
        "type",
        "unknown",
    )
    attempts = run_attempts(run_dir, run, root)
    variants = []
    for variant_id in experiment["variant_ids"]:
        observed_requested_models = run_requested_models(run, variant_id)
        if any(model != requested.get(variant_id) for model in observed_requested_models):
            raise ValueError(f"experiment model does not match run artifact for {variant_id}")
        variants.append(
            {
                "variant_id": variant_id,
                "model_requested": requested.get(variant_id, "unknown"),
                "model_served": run_model(run, variant_id, client_name),
                "task_ids": run_task_ids(run, variant_id),
                "per_replicate_scores": contaminated_scores(
                    experiment["per_replicate_scores"].get(variant_id, {}), attempts, variant_id
                ),
            }
        )

    client_command = {
        "claude-code": "claude",
        "omp": "omp",
        "codex-daily-driver": "codex",
    }.get(client_name, "unknown")
    historical_client_version = run.get("environment_info", {}).get("cli_version", "unknown")
    if not isinstance(historical_client_version, str) or not historical_client_version:
        historical_client_version = "unknown"
    session_present = "CLAUDE_CODE_SESSION_ID" in os.environ
    return {
        "schema_version": 2,
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
            "version": historical_client_version,
            "recorded_version": command_version(client_command) if client_command != "unknown" else "unknown",
        },
        "host": {
            "kind": "cloud" if session_present else "laptop",
            "hostname": socket.gethostname(),
            "session_id": os.environ.get("CLAUDE_CODE_SESSION_ID") if session_present else None,
            "platform": platform.platform(),
        },
        "variants": variants,
        "attempts": attempts,
        "cases": run_cases(run, experiment["experiment_id"], requested, client_name),
    }

def validate_record(record: dict[str, Any]) -> list[str]:
    """Return validation errors for one provenance record."""
    errors = sorted(REQUIRED_RECORD_FIELDS - record.keys())
    version = record.get("schema_version")
    if version not in (1, 2):
        errors.append("schema_version must be 1 or 2")
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
    if isinstance(host, dict) and host.get("kind") == "cloud":
        if not isinstance(host.get("session_id"), str) or not host["session_id"]:
            errors.append("host.session_id must be non-empty for cloud runs")
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
    if not isinstance(record.get("attempts"), list) or not record["attempts"]:
        errors.append("attempts must be non-empty")
    else:
        for index, attempt in enumerate(record["attempts"]):
            prefix = f"attempts[{index}]"
            if not isinstance(attempt, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for field in ("variant_id", "task_id"):
                if not isinstance(attempt.get(field), str) or not attempt[field]:
                    errors.append(f"{prefix}.{field} must be a non-empty string")
            final_status = attempt.get("final_status", attempt.get("status"))
            if not isinstance(final_status, str) or not final_status:
                errors.append(f"{prefix}.final_status must be a non-empty string")
            if not isinstance(attempt.get("replicate_index"), int):
                errors.append(f"{prefix}.replicate_index must be an integer")
            if not isinstance(attempt.get("criteria"), list):
                errors.append(f"{prefix}.criteria must be a list")
            if "early_stop" in attempt and attempt["early_stop"] is not None and not isinstance(attempt["early_stop"], dict):
                errors.append(f"{prefix}.early_stop must be an object or null")
            measured_score = attempt.get("measured_score", attempt.get("weighted_score"))
            raw_weighted_score = attempt.get("raw_weighted_score", attempt.get("weighted_score"))
            if measured_score is not None and not isinstance(measured_score, (int, float)):
                errors.append(f"{prefix}.measured_score must be numeric or null")
            if not isinstance(raw_weighted_score, (int, float)):
                errors.append(f"{prefix}.raw_weighted_score must be numeric")
            contact = attempt.get("answer_key_contact")
            if contact is not None:
                if not isinstance(contact, list) or not all(isinstance(line, str) for line in contact):
                    errors.append(f"{prefix}.answer_key_contact must be a list of strings")
                elif contact and measured_score != 0.0:
                    errors.append(f"{prefix}.measured_score must be 0 when answer_key_contact is non-empty")
    if version == 2:
        if not isinstance(record.get("cases"), list) or not record["cases"]:
            errors.append("cases must be non-empty for schema_version 2")
        else:
            for index, case in enumerate(record["cases"]):
                prefix = f"cases[{index}]"
                if not isinstance(case, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for field in ("task_id", "variant_id", "model_requested", "model_served", "settings", "outcome"):
                    if not isinstance(case.get(field), str) or not case[field]:
                        errors.append(f"{prefix}.{field} must be a non-empty string")
                if case.get("class") is not None and not isinstance(case.get("class"), str):
                    errors.append(f"{prefix}.class must be a string or null")
                if not isinstance(case.get("replicate_index"), int):
                    errors.append(f"{prefix}.replicate_index must be an integer")
                if not isinstance(case.get("elapsed_seconds"), (int, float)):
                    errors.append(f"{prefix}.elapsed_seconds must be numeric")
                tokens = case.get("tokens")
                if tokens != "unreported" and not isinstance(tokens, int):
                    errors.append(f"{prefix}.tokens must be an integer or 'unreported'")
                cost = case.get("cost")
                if cost != "unreported" and not isinstance(cost, (int, float)):
                    errors.append(f"{prefix}.cost must be numeric or 'unreported'")
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
