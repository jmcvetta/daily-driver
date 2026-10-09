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
import statistics
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tree_sitter_bash
from tree_sitter import Language, Parser
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

# The per-token rates every `evals/prices.yaml` entry gives, in USD.
PRICE_RATE_FIELDS = ("input", "output", "cache_read", "cache_write")

# The schema version `build_record` writes. Version 3 makes a numeric price
# and a positive per-replicate wall time required on every case row.
SCHEMA_VERSION = 3


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


def load_prices(path: Path) -> dict[str, dict[str, Any]]:
    """Read per-token rates and explicit subscription-billed models.

    Priced entries give four USD-per-token rates. An unpriced entry names a
    billing reason, such as a subscription with no applicable per-token price.
    Both forms cite their source and read date.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required to read the price table")
    document = yaml.safe_load(path.read_text()) or {}
    models = document.get("models") if isinstance(document, dict) else None
    if models is None:
        models = {}
    if not isinstance(models, dict):
        raise ValueError(f"{path}: models must be a mapping of model id to rates")
    for model, entry in models.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: {model} must be a mapping")
        unpriced_reason = entry.get("unpriced_reason")
        if unpriced_reason:
            if not isinstance(unpriced_reason, str) or not unpriced_reason.strip():
                raise ValueError(f"{path}: {model}.unpriced_reason must be non-empty")
            if any(field in entry for field in PRICE_RATE_FIELDS):
                raise ValueError(f"{path}: {model} cannot declare both rates and unpriced_reason")
        else:
            for field in PRICE_RATE_FIELDS:
                value = entry.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                    raise ValueError(f"{path}: {model}.{field} must be a non-negative number (USD per token)")
        for field in ("source", "read_on"):
            if not str(entry.get(field) or "").strip():
                raise ValueError(f"{path}: {model}.{field} must be non-empty")
    return models


def price_key(model: str) -> str:
    """The price-table key for a requested model: the id without a trailing
    `:<level>` thinking suffix, which changes the tokens spent, not the rate."""
    return model.rsplit(":", 1)[0] if ":" in model.rsplit("/", 1)[-1] else model


def _number(value: Any) -> bool:
    """Whether `value` is a real number rather than a bool or a sentinel."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def row_label(row: dict[str, Any]) -> str:
    """Name one task result for an error: task, variant, replicate and status,
    plus the harness's own error message where it recorded one."""
    label = (
        f"{row.get('task_id', 'unknown')}/{row.get('variant_id', 'unknown')} "
        f"replicate {row.get('replicate_index', 0)} ({row.get('status', 'no status')})"
    )
    error = row.get("error_message")
    return f"{label}, error: {error}" if error else label


def case_price(row: dict[str, Any], model: str, prices: dict[str, dict[str, Any]]) -> tuple[float | None, str]:
    """The USD price of one task result, and whether it was `reported`, `computed`
    or `unreported`.

    The harness's own figure wins where the subject agent was priced: the row's
    `total_cost_usd` is then the whole bill, judge included. A row whose agent
    spend is unpriced -- a token-only harness -- prices the agent's tokens from
    `prices` and adds whatever judge and simulator spend was reported. Its
    `total_cost_usd` is not used, because there it holds the judge alone.
    Missing token counts and no reported price leave the cost unreported; they
    are never treated as zero or reconstructed from the configured model.
    """
    task = row_label(row)
    if _number(row.get("agent_cost_usd")):
        total = row.get("total_cost_usd")
        return (float(total) if _number(total) else float(row["agent_cost_usd"])), "reported"
    if not _number(row.get("input_tokens")) or not _number(row.get("output_tokens")):
        return None, "unreported"
    key = price_key(model)
    rates = prices.get(key)
    if rates is None:
        raise ValueError(f"{task}: no entry for model {key} in the price table; add its rates rather than guess")
    if rates.get("unpriced_reason"):
        return None, "unreported"
    tokens = {
        "input": row["input_tokens"],
        "output": row["output_tokens"],
        "cache_read": row.get("cache_read_input_tokens") or 0,
        "cache_write": row.get("cache_creation_input_tokens") or 0,
    }
    agent = sum(tokens[field] * rates[field] for field in PRICE_RATE_FIELDS)
    overhead = sum(row[field] for field in ("judge_cost_usd", "simulator_cost_usd") if _number(row.get(field)))
    return agent + overhead, "computed"


def run_cases(
    run: dict[str, Any],
    experiment_id: str,
    requested: dict[str, str],
    client_name: str,
    prices: dict[str, dict[str, Any]],
    sources: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """One row per task result in `run`: model, settings, class, outcome,
    elapsed seconds, tokens, price and the price's source, plus the pull
    request a case was built from (`source`, `owner/repo#N`) where it has one --
    `evals-render-routes.py`'s and `evals-render-results.py`'s input.
    """
    cases = []
    for row in run.get("task_results", []):
        variant_id = row.get("variant_id")
        model_served = "unreported" if client_name == "omp" else (row.get("model_used") or "unreported")
        tokens = row.get("total_tokens")
        model_requested = requested.get(variant_id, "unknown")
        cost, cost_source = case_price(row, model_requested, prices)
        elapsed = row.get("duration")
        if not _number(elapsed) or elapsed <= 0:
            raise ValueError(
                f"{row_label(row)}: no positive wall time (duration {elapsed!r}); "
                "schema version 3 records only replicates that ran"
            )
        case_source = (sources or {}).get(row.get("task_id", ""))
        cases.append(
            {
                **({"source": case_source} if case_source else {}),
                "task_id": row.get("task_id", "unknown"),
                "variant_id": variant_id,
                "replicate_index": row.get("replicate_index", 0),
                "class": row_class(row),
                "model_requested": model_requested,
                "model_served": model_served,
                "settings": experiment_id,
                "outcome": row_outcome(row.get("status", "")),
                "elapsed_seconds": elapsed,
                "tokens": tokens if isinstance(tokens, int) else "unreported",
                "cost": cost,
                "cost_source": cost_source,
            }
        )
    return cases


# A model-classes row's description is "owner/repo#N: title", written by
# `scripts/evals-cases-from-prs.py`; it names the repository whose later
# history holds the answer.
_MODEL_CLASSES_SOURCE = re.compile(r"^\s*([\w.-]+/[\w.-]+)#\d+:")
_SOURCE_PR = re.compile(r"^\s*([\w.-]+/[\w.-]+)#(\d+):")

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
_GIT_REF_COMMANDS = {
    "branch",
    "cat-file",
    "checkout",
    "diff",
    "fetch",
    "log",
    "merge",
    "pull",
    "rev-parse",
    "show",
    "switch",
    "worktree",
}
_GH_REPO_COMMANDS = {"pr", "issue", "repo", "browse", "run", "release", "workflow"}


_BASH_LANGUAGE = Language(tree_sitter_bash.language())


def _shell_nodes(root: Any) -> list[Any]:
    """Return every node below a Tree-sitter Bash node."""
    found = []
    stack = [root]
    while stack:
        node = stack.pop()
        found.append(node)
        stack.extend(reversed(node.children))
    return found


def _node_text(node: Any, source: bytes) -> str:
    """Return one parsed shell node's source text."""
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _heredoc_expansion(body: str) -> str:
    """Parse unquoted here-document substitutions in a double-quoted context."""
    encoded = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            if index + 1 < len(body) and body[index + 1] in "$`\\\n":
                encoded.extend(("\\", body[index + 1]))
                index += 2
            else:
                encoded.append("\\\\")
                index += 1
        elif char == '"':
            encoded.append('\\"')
            index += 1
        else:
            encoded.append(char)
            index += 1
    return 'printf "%s" "' + "".join(encoded) + '"'


def _shell_ast(command: str) -> list[tuple[Any, bytes]]:
    """Parse shell syntax, executable shell scripts, and here-document substitutions."""
    parser = Parser(_BASH_LANGUAGE)
    pending = [command.encode("utf-8")]
    trees = []
    while pending:
        source = pending.pop()
        root = parser.parse(source).root_node
        trees.append((root, source))
        for node in _shell_nodes(root):
            if node.type == "heredoc_redirect":
                start = next(child for child in node.children if child.type == "heredoc_start")
                body = next((child for child in node.children if child.type == "heredoc_body"), None)
                delimiter = _node_text(start, source)
                if any(char in delimiter for char in ("'", '"', "\\")):
                    continue
                body_text = _node_text(body, source) if body is not None else ""
                expansion = _heredoc_expansion(body_text).encode("utf-8")
                expanded_tree = parser.parse(expansion)
                if expanded_tree.root_node.has_error:
                    raise ValueError("could not parse an unquoted here-document expansion")
                pending.extend(
                    _node_text(child, expansion).encode("utf-8")
                    for expanded_node in _shell_nodes(expanded_tree.root_node)
                    if expanded_node.type == "command_substitution"
                    for child in _shell_nodes(expanded_node)
                    if child.type == "command"
                )
            elif node.type == "command":
                name = node.child_by_field_name("name")
                if name is None:
                    continue
                argument_nodes = [
                    child
                    for index, child in enumerate(node.children)
                    if node.field_name_for_child(index) == "argument"
                ]
                arguments = [_word_value(_node_text(child, source)) for child in argument_nodes]
                executable = _word_value(_node_text(name, source)).rsplit("/", 1)[-1]
                if executable in {"bash", "sh", "dash", "ksh", "zsh"}:
                    script_index = next(
                        (index + 1 for index, item in enumerate(arguments) if item == "-c" or item.startswith("-") and "c" in item[1:]),
                        None,
                    )
                    if script_index is not None and script_index < len(arguments):
                        pending.append(arguments[script_index].encode("utf-8"))
                elif executable == "eval" and arguments:
                    dynamic_input = any(
                        child.type in {"simple_expansion", "expansion", "command_substitution", "process_substitution"}
                        for argument in argument_nodes
                        for child in _shell_nodes(argument)
                    )
                    if dynamic_input:
                        raise ValueError("cannot statically parse dynamic eval input")
                    pending.append(" ".join(arguments).encode("utf-8"))
    return trees


def _word_value(word: str) -> str:
    """Remove shell quoting from one parser-delimited command word."""
    try:
        words = shlex.split(word)
    except ValueError:
        return word
    return words[0] if len(words) == 1 else word


def _repo_flag(words: list[str]) -> str | None:
    """The repository a `gh` command names with `-R`/`--repo`, if any."""
    for index, word in enumerate(words):
        if word.startswith("--repo="):
            return word.split("=", 1)[1]
        if word in ("-R", "--repo") and index + 1 < len(words):
            return words[index + 1]
    return None


def _command_positions(words: list[str]) -> list[int]:
    """Find commands after common shell utility wrappers, not ordinary arguments."""
    index = 0
    wrappers = {"command", "exec", "env", "nohup", "nice", "sudo", "doas", "time"}
    options_with_values = {"-C", "-c", "-u", "-g", "-h", "-p", "-S", "--chdir"}
    while index < len(words):
        name = _word_value(words[index]).rsplit("/", 1)[-1]
        if name not in wrappers:
            return [index]
        index += 1
        while index < len(words) and words[index].startswith("-"):
            option = words[index]
            index += 1
            if option in options_with_values and index < len(words):
                index += 1
        while index < len(words) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[index]):
            index += 1
    return []


def _command_contacts(command: str, source: str, markers: tuple[str, ...] = ()) -> list[str]:
    """Why parsed shell commands or their executable expansions reach source history."""
    try:
        parsed = _shell_ast(command)
        if any(root.has_error for root, _ in parsed):
            return ["Bash parse failure: unsupported or incomplete shell syntax"]
    except Exception as error:
        return [f"Bash parse failure ({type(error).__name__}): {error}"]

    reasons = []
    unresolved_command = False
    source_url = re.compile(
        r"(?:github\.com[/:]|githubusercontent\.com/(?:raw/)?|api\.github\.com/repos/)"
        + re.escape(source)
        + r"(?![\w.-])",
        re.IGNORECASE,
    )
    shell_words = []

    def collect_words(node: Any, source_text: bytes) -> None:
        if node.type == "heredoc_body":
            for child in node.named_children:
                if child.type in ("command_substitution", "process_substitution"):
                    collect_words(child, source_text)
            return
        if node.type in ("word", "raw_string", "string", "number"):
            shell_words.append(_node_text(node, source_text))
        for child in node.named_children:
            collect_words(child, source_text)

    for root, source_text in parsed:
        collect_words(root, source_text)
        for node in _shell_nodes(root):
            if node.type != "command":
                continue
            name = node.child_by_field_name("name")
            if name is None:
                continue
            word_nodes = [name]
            word_nodes.extend(
                child
                for index, child in enumerate(node.children)
                if node.field_name_for_child(index) == "argument"
            )
            words = [_word_value(_node_text(item, source_text)) for item in word_nodes]
            positions = _command_positions(words)
            for position in positions:
                if any(
                    child.type in {"simple_expansion", "expansion", "command_substitution", "process_substitution"}
                    for child in _shell_nodes(word_nodes[position])
                ):
                    unresolved_command = True
                    continue
                word = words[position]
                executable = word.rsplit("/", 1)[-1]
                rest = words[position + 1 :]
                while rest and rest[0].startswith("-"):
                    rest = rest[2:] if rest[0] in ("-C", "-c", "-R", "--repo") else rest[1:]
                network_access = False
                if executable in ("git", "gh") and rest:
                    subcommand = rest[0]
                    if executable == "git":
                        network_access = subcommand in _GIT_NETWORK
                        if network_access:
                            reasons.append(f"git {subcommand}")
                        elif subcommand == "remote" and len(rest) > 1 and rest[1] in ("add", "set-url"):
                            network_access = True
                            reasons.append(f"git remote {rest[1]}")
                        if subcommand in _GIT_REF_COMMANDS and any(
                            "refs/pull/" in item for item in rest[1:]
                        ):
                            reasons.append("refs/pull/")
                    elif subcommand == "search":
                        network_access = True
                        reasons.append("gh search")
                    elif subcommand == "api":
                        network_access = True
                        named = [item for item in rest[1:] if "repos/" in item]
                        if not named or any(source.lower() in item.lower() for item in named):
                            reasons.append("gh api")
                    elif subcommand in _GH_REPO_COMMANDS:
                        network_access = True
                        other = _repo_flag(rest)
                        if other is None or other.lower() == source.lower():
                            reasons.append(f"gh {subcommand}")
                elif executable in {"curl", "http", "wget"}:
                    network_access = True
                if network_access and any(source_url.search(item) for item in words):
                    reasons.append(f"URL under {source}")
    if unresolved_command and not reasons:
        reasons.append("unresolved executable expansion")
    reasons.extend(f"names {marker}" for marker in markers if any(marker in word for word in shell_words))
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
        r"(?:github\.com[/:]|githubusercontent\.com/(?:raw/)?|api\.github\.com/repos/)"
        + re.escape(source)
        + r"(?![\w.-])",
        re.IGNORECASE,
    )
    markers = (*_ANSWER_KEY_MARKERS, str(root))

    evidence = []
    for iteration in artifact.get("iterations") or []:
        for command in iteration.get("commands") or []:
            tool = command.get("tool_name", "?")
            command_parameters = command.get("parameters") or {}
            parameters = json.dumps(command_parameters)
            result = command.get("result_summary") or ""
            shell = command_parameters.get("command")
            if tool == "Bash" and isinstance(shell, str):
                reasons = _command_contacts(shell, source, markers)
            else:
                reasons = [f"names {marker}" for marker in markers if marker in parameters]
                if source_url.search(parameters):
                    reasons.append(f"URL under {source}")
            reasons += [f"printed {marker}" for marker in markers if marker in result and marker not in parameters]
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


def task_sources(run_dir: Path, run: dict[str, Any]) -> dict[str, str]:
    """`owner/repo#N` per task id, for the tasks built from a pull request.

    The case builder writes it as the head of the task's description; a task
    whose description does not start that way has no source pull request.
    """
    sources: dict[str, str] = {}
    for result in run.get("task_results", []):
        task_id = result["task_id"]
        if task_id in sources:
            continue
        replicate = result.get("replicate_index", 0)
        artifact_path = run_dir / result["variant_id"] / task_id / f"{replicate:02d}" / "task.json"
        if not artifact_path.is_file():
            continue
        match = _SOURCE_PR.match(json.loads(artifact_path.read_text()).get("task_description") or "")
        if match:
            sources[task_id] = f"{match.group(1)}#{match.group(2)}"
    return sources


def judge_sidecars(run_dir: Path) -> tuple[dict[str, Any] | None, dict[tuple[str, str, int], dict[str, Any]]]:
    """The run-selected judge's manifest and per-replicate sidecars, or `(None, {})`.

    Written by `scripts/evals-judge.py judge-run` under `<run>/judge/<judge-id>/`.
    One judge per run: two directories are two measurements mixed in one record.
    """
    manifests = sorted((run_dir / "judge").glob("*/manifest.json"))
    if not manifests:
        return None, {}
    if len(manifests) > 1:
        raise ValueError(f"{run_dir}/judge holds more than one judge ({', '.join(m.parent.name for m in manifests)}); one judge per run")
    manifest = json.loads(manifests[0].read_text())
    sidecars: dict[tuple[str, str, int], dict[str, Any]] = {}
    for path in sorted(manifests[0].parent.glob("*/*/*.json")):
        data = json.loads(path.read_text())
        sidecars[(data["variant_id"], data["task_id"], data["replicate_index"])] = data
    return manifest, sidecars


def judged_status(coder_eval_status: str, sidecar: dict[str, Any]) -> str:
    """A replicate's final status once its semantic criteria are graded by the selected judge.

    `coder_eval` scored the disabled `agent_judge` criteria 1.0, so its own
    SUCCESS only says the deterministic criteria held. A judge error is an
    evaluation error; a gating criterion under its threshold is a failure.
    """
    if sidecar.get("evaluation_status") == "error":
        return "ERROR"
    if coder_eval_status != "SUCCESS":
        return coder_eval_status
    failed = [
        c
        for c in sidecar["criteria"]
        if c.get("section") == "success_criteria" and c.get("weight", 1.0) > 0 and c.get("score", 0.0) < c.get("pass_threshold", 0.7)
    ]
    return "FAILURE" if failed else "SUCCESS"


def apply_judge(
    attempts: list[dict[str, Any]],
    variants: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    sidecars: dict[tuple[str, str, int], dict[str, Any]],
) -> None:
    """Replace `coder_eval`'s scores for judged replicates with the selected judge's, in place.

    Each judged attempt keeps `coder_eval_status` and `raw_weighted_score` as
    `coder_eval` wrote them, so the substitution is visible, and gains a `judge`
    object. A replicate whose judge errored has no score at all: `measured_score`
    is null and the case outcome is `error`, never a 0.0 the subject earned.
    """
    for attempt in attempts:
        sidecar = sidecars.get((attempt["variant_id"], attempt["task_id"], attempt["replicate_index"]))
        if sidecar is None:
            continue
        attempt["coder_eval_status"] = attempt["final_status"]
        attempt["final_status"] = judged_status(attempt["final_status"], sidecar)
        # A replicate that reached the answer key stays at the forced 0.
        attempt["measured_score"] = 0.0 if attempt.get("answer_key_contact") else sidecar["weighted_score"]
        attempt["judge"] = {
            "freeze_sha": sidecar["freeze_sha"],
            "evaluation_status": sidecar["evaluation_status"],
            "criteria": sidecar["criteria"],
        }
    by_key = {(a["variant_id"], a["task_id"], a["replicate_index"]): a for a in attempts}
    for case in cases:
        attempt = by_key.get((case["variant_id"], case["task_id"], case["replicate_index"]))
        if attempt is not None and "judge" in attempt:
            case["outcome"] = row_outcome(attempt["final_status"])
    for variant in variants:
        for task_id, values in variant["per_replicate_scores"].items():
            for index in range(len(values)):
                attempt = by_key.get((variant["variant_id"], task_id, index))
                if attempt is not None and "judge" in attempt:
                    values[index] = attempt["measured_score"]


def judge_block(manifest: dict[str, Any] | None, sidecars: dict[tuple[str, str, int], dict[str, Any]], attempts: list[dict[str, Any]], root: Path) -> dict[str, Any] | None:
    """The judge's identity for a record, apart from the subject's.

    Run-selected: from the manifest and sidecars -- the requested judge, the
    models Omp reported, usage, errors and the freeze hash. Task-pinned (no
    `judge/` directory): the Claude Code `agent_judge` each task file pins,
    where observed identity and usage are unavailable. A run with no
    `agent_judge` criterion has no judge.
    """
    if manifest is not None:
        observed: set[str] = set()
        usage = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0}
        usage_known = True
        for sidecar in sidecars.values():
            for criterion in sidecar["criteria"]:
                model = (criterion.get("observed") or {}).get("model")
                if model:
                    observed.add(model)
                if isinstance(criterion.get("usage"), dict):
                    for key in usage:
                        usage[key] += int(criterion["usage"].get(key, 0))
                else:
                    usage_known = False
        return {
            "selection": "run-selected",
            **manifest["judge"],
            "prompt_version": manifest["prompt_version"],
            "freeze_sha": manifest["freeze_sha"],
            "models_observed": sorted(observed - {"unavailable"}) or "unavailable",
            "usage": usage if usage_known and sidecars else "unavailable",
            "criterion_errors": manifest["criterion_errors"],
            "price_included_in_cases": False,
        }
    if not any(c.get("criterion_type") == "agent_judge" for a in attempts for c in a["criteria"]):
        return None
    pins: set[tuple[str, str]] = set()
    wanted = {a["task_id"] for a in attempts}
    for path in sorted((root / "evals" / "tasks").glob("*/*.yaml")):
        task = yaml.safe_load(path.read_text()) if yaml is not None else {}
        if not isinstance(task, dict) or task.get("task_id") not in wanted:
            continue
        for section in ("success_criteria", "post_failure_criteria"):
            for criterion in task.get(section) or []:
                if isinstance(criterion, dict) and criterion.get("type") == "agent_judge":
                    agent = criterion.get("agent") or {}
                    pins.add((agent.get("type", "unknown"), agent.get("model", "unknown")))
    return {
        "selection": "task-pinned",
        "route": "claude-code",
        "model_requested": sorted({model for _, model in pins}) or "unknown",
        "models_observed": "unavailable",
        "usage": "unavailable",
    }


def build_record(run_dir: Path, experiment_path: Path, root: Path, prices: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build a committed provenance record from a coder_eval run directory,
    pricing token-only rows from `prices`."""
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
    judge_manifest, judge_sidecar_rows = judge_sidecars(run_dir)
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
    cases = run_cases(run, experiment["experiment_id"], requested, client_name, prices, task_sources(run_dir, run))
    apply_judge(attempts, variants, cases, judge_sidecar_rows)
    judge = judge_block(judge_manifest, judge_sidecar_rows, attempts, root)
    record = {
        "schema_version": SCHEMA_VERSION,
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
        "cases": cases,
    }
    if judge is not None:
        record["judge"] = judge
    return record

def validate_record(record: dict[str, Any]) -> list[str]:
    """Return validation errors for one provenance record."""
    errors = sorted(REQUIRED_RECORD_FIELDS - record.keys())
    version = record.get("schema_version")
    if version not in (1, 2, 3):
        errors.append("schema_version must be 1, 2 or 3")
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
    judge = record.get("judge")
    if judge is not None:
        if not isinstance(judge, dict) or judge.get("selection") not in ("run-selected", "task-pinned"):
            errors.append("judge.selection must be run-selected or task-pinned")
        else:
            if judge.get("route") not in ("claude-code", "omp"):
                errors.append("judge.route must be claude-code or omp")
            if not judge.get("model_requested"):
                errors.append("judge.model_requested must be present")
            for field in ("models_observed", "usage"):
                if field not in judge:
                    errors.append(f"judge.{field} must be present (use 'unavailable' where the route reports none)")
            if judge["selection"] == "run-selected":
                for field in ("judge_id", "freeze_sha", "prompt_version"):
                    if not isinstance(judge.get(field), str) or not judge[field]:
                        errors.append(f"judge.{field} must be a non-empty string")
                if judge.get("route") == "omp" and record.get("client", {}).get("name") == "claude-code":
                    pass  # a non-Claude judge may grade a Claude subject; they are separate measurements
    if version in (2, 3):
        if not isinstance(record.get("cases"), list) or not record["cases"]:
            errors.append(f"cases must be non-empty for schema_version {version}")
        else:
            for index, case in enumerate(record["cases"]):
                prefix = f"cases[{index}]"
                if not isinstance(case, dict):
                    errors.append(f"{prefix} must be an object")
                    continue
                for field in ("task_id", "variant_id", "model_requested", "model_served", "settings", "outcome"):
                    if not isinstance(case.get(field), str) or not case[field]:
                        errors.append(f"{prefix}.{field} must be a non-empty string")
                if case.get("source") is not None and not (isinstance(case["source"], str) and _SOURCE_PR.match(case["source"] + ":")):
                    errors.append(f"{prefix}.source must be 'owner/repo#N' when present")
                if case.get("class") is not None and not isinstance(case.get("class"), str):
                    errors.append(f"{prefix}.class must be a string or null")
                if not isinstance(case.get("replicate_index"), int):
                    errors.append(f"{prefix}.replicate_index must be an integer")
                if not _number(case.get("elapsed_seconds")):
                    errors.append(f"{prefix}.elapsed_seconds must be numeric")
                tokens = case.get("tokens")
                if tokens != "unreported" and not isinstance(tokens, int):
                    errors.append(f"{prefix}.tokens must be an integer or 'unreported'")
                cost = case.get("cost")
                if version == 3:
                    if cost is None:
                        if case.get("cost_source") != "unreported":
                            errors.append(f"{prefix}.cost_source must be 'unreported' when cost is null")
                    elif not _number(cost) or cost < 0:
                        errors.append(f"{prefix}.cost must be a non-negative number or null for schema_version 3")
                    elif case.get("cost_source") not in ("reported", "computed"):
                        errors.append(f"{prefix}.cost_source must be 'reported' or 'computed' when cost is numeric")
                    elapsed = case.get("elapsed_seconds")
                    if _number(elapsed) and elapsed <= 0:
                        errors.append(f"{prefix}.elapsed_seconds must be greater than 0 for schema_version 3")
                elif cost != "unreported" and not isinstance(cost, (int, float)):
                    errors.append(f"{prefix}.cost must be numeric or 'unreported'")
    return errors


_COMMENT_API = "https://api.github.com"


def render_comment(record: dict[str, Any], source: str, provenance_file: str) -> str:
    """The comment for one source pull request: one row per model and variant.

    Repeats collapse into `pass n/m` and a median elapsed. Tokens, cost and
    transcripts stay in the record.
    """
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for case in record["cases"]:
        if case.get("source") == source:
            groups.setdefault((case["model_requested"], case["variant_id"]), []).append(case)
    rows = []
    for (model, variant), cases in sorted(groups.items()):
        passed = sum(1 for case in cases if case["outcome"] == "succeeded")
        minutes = round(statistics.median(case["elapsed_seconds"] for case in cases) / 60)
        rows.append(f"| `{model}` | {variant} | pass {passed}/{len(cases)} | {max(minutes, 1)} min median |")
    run_id = record["run_id"]
    return "\n".join(
        [
            f"<!-- eval-result: {run_id} -->",
            "## Eval result",
            "",
            f"An agent re-implemented this pull request's task in an eval on {record['started_at'][:10]}, "
            "after the fact. The implementation above is the real one.",
            "",
            "| Model | Variant | Outcome | Elapsed |",
            "| --- | --- | --- | --- |",
            *rows,
            "",
            f"Run `{run_id}`, recorded in `{provenance_file}`.",
            "",
        ]
    )


def find_result_comment(comments: list[dict[str, Any]], run_id: str) -> dict[str, Any] | None:
    """The existing comment carrying this run's marker, or None where a new one is due."""
    marker = f"<!-- eval-result: {run_id} -->"
    for comment in comments:
        if (comment.get("body") or "").startswith(marker):
            return comment
    return None


def _api(token: str, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    request = urllib.request.Request(
        _COMMENT_API + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def post_comments(record: dict[str, Any], provenance_file: str, token: str) -> int:
    """Post or edit the run's comment on each distinct source pull request.

    A failure on one pull request is reported and the rest still post; the
    return value is the number that failed.
    """
    failed = 0
    for source in sorted({case["source"] for case in record["cases"] if case.get("source")}):
        repo, number = source.rsplit("#", 1)
        base = f"/repos/{repo}/issues"
        try:
            body = render_comment(record, source, provenance_file)
            comments: list[dict[str, Any]] = []
            page = 1
            while True:
                batch = _api(token, "GET", f"{base}/{number}/comments?per_page=100&page={page}")
                comments += batch
                if len(batch) < 100:
                    break
                page += 1
            existing = find_result_comment(comments, record["run_id"])
            if existing:
                _api(token, "PATCH", f"{base}/comments/{existing['id']}", {"body": body})
            else:
                _api(token, "POST", f"{base}/{number}/comments", {"body": body})
        except OSError as error:
            failed += 1
            print(f"cannot comment on {source}: {error}", file=sys.stderr)
            continue
        print(f"{'edited' if existing else 'posted'} eval result on {source}")
    return failed


def parse_args() -> argparse.Namespace:
    """Parse recorder command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path, help="coder_eval run directory")
    parser.add_argument("--experiment", type=Path, required=True, help="experiment YAML")
    parser.add_argument("--output", type=Path, default=Path("evals/provenance"))
    parser.add_argument("--prices", type=Path, default=Path(__file__).resolve().parent.parent / "evals" / "prices.yaml", help="price table for token-only harnesses")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--post-comments", action="store_true", help="post the run's result on each source pull request")
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
    try:
        record = build_record(args.run, args.experiment, root, load_prices(args.prices))
    except ValueError as error:
        raise SystemExit(f"cannot record {args.run} (price table {args.prices}): {error}")
    errors = validate_record(record)
    if errors:
        raise SystemExit("invalid generated record:\n" + "\n".join(errors))
    args.output.mkdir(parents=True, exist_ok=True)
    date = record["started_at"][:10]
    path = args.output / f"{record['experiment_id']}-{date}-{record['run_id']}.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(path)
    if args.post_comments:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("no GITHUB_TOKEN or GH_TOKEN: record written, comments skipped", file=sys.stderr)
            return 1
        return 1 if post_comments(record, f"{args.output.as_posix()}/{path.name}", token) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
