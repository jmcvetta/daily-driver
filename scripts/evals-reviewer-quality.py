#!/usr/bin/env python3
"""Collect bounded reviewer-quality evidence from explicit coder_eval runs."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import statistics
import math
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

CASE_IDS = (
    "reviewer-quality-01-boundary",
    "reviewer-quality-02-contract",
    "reviewer-quality-03-authorization",
    "reviewer-quality-04-integrity",
    "reviewer-quality-05-clean-boundary",
    "reviewer-quality-06-clean-contract",
    "reviewer-quality-07-delta-fixed",
    "reviewer-quality-08-delta-incomplete",
)
MAX_FINDINGS_CHARS = 4_000
CLASSIFICATION_RE = re.compile(r"^(TP:[\w-]+|FN:[\w-]+|FP:.+|DELTA:(?:clear|defects)|UNEXPECTED_VALID:.+)$")


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 without exposing its contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def final_response(path: Path | None) -> str | None:
    """Return the complete final response, never the full transcript."""
    if path is None or not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.name == "task.json":
        task = json.loads(text)
        iterations = task.get("iterations", [])
        output = str(iterations[-1].get("agent_output", "")) if iterations else ""
        marker = "[RESULT - SUCCESS] "
        if marker not in output:
            return None
        text = output.rsplit(marker, 1)[1].strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, dict) or not {"reviewer_reported_identity", "verdict", "findings"} <= value.keys():
            return None
    text = "".join(ch for ch in text if ch in "\n\t" or ord(ch) >= 32)
    return text.strip()


def bounded_response(text: str) -> str:
    """Limit recorded response text after verifying its complete content."""
    if len(text) > MAX_FINDINGS_CHARS:
        return text[:MAX_FINDINGS_CHARS] + "\n...[truncated]"
    return text

def reviewer_delivery_observed(path: Path | None, final: str | None) -> bool:
    """Require the parent's JSON to match a captured completed reviewer result."""
    if path is None or path.name != "task.json" or not path.is_file() or final is None:
        return False
    try:
        expected = json.loads(final)
    except json.JSONDecodeError:
        return False
    task = json_file(path)
    for iteration in task.get("iterations", []):
        for command in iteration.get("commands", []):
            if command.get("tool_name") not in {"Agent", "Task", "Wait", "wait", "Read"}:
                continue
            if str(command.get("result_status", "")).lower() not in {"ok", "success"}:
                continue
            result = str(command.get("result_summary") or "")
            match = re.search(r'<task-result\b[^>]*\bagent="reviewer"[^>]*\bstatus="completed"[^>]*>.*?<output>(.*?)</output>', result, re.DOTALL)
            if not match:
                continue
            output = match.group(1)
            for index, character in enumerate(output):
                if character != "{":
                    continue
                try:
                    value, _ = json.JSONDecoder().raw_decode(output[index:])
                except json.JSONDecodeError:
                    continue
                if value == expected:
                    return True
    return False


REVIEWER_TELEMETRY_FILENAME = "omp-reviewer-telemetry.json"


def delivered_reviewer_id(path: Path | None) -> str | None:
    """The subagent id a completed `<task-result>` delivered to the parent, if any.

    The delivery text names the reviewer that produced the result, so the
    adapter's child telemetry can be matched to that exact id rather than to
    whichever reviewer happened to run last.
    """
    if path is None or path.name != "task.json" or not path.is_file():
        return None
    task = json_file(path)
    found: list[str] = []
    for iteration in task.get("iterations", []):
        for command in iteration.get("commands", []):
            result = str(command.get("result_summary") or "")
            for tag in re.finditer(r'<task-result\b[^>]*\bagent="reviewer"[^>]*\bstatus="completed"[^>]*>', result):
                match = re.search(r'\bid="([^"]+)"', tag.group(0))
                if match:
                    found.append(match.group(1))
    return found[-1] if found else None


def reviewer_telemetry_evidence(artifact_dir: Path, delivered_id: str | None) -> dict[str, Any]:
    """Read the adapter's reviewer-child telemetry for one attempt.

    `artifact_dir` is the attempt directory; the adapter writes inside the task
    sandbox, which coder_eval preserves under `artifacts/<task>`. A `.pending`
    guard, a missing file, an incomplete document and an unreadable one all
    mean the same thing for the cost comparison: the reviewer's usage is
    unavailable. They are reported distinctly so the reason survives the run.
    """
    candidates = [artifact_dir]
    nested = [
        path.parent
        for path in artifact_dir.glob("artifacts/*/omp-reviewer-telemetry.json")
        if path.is_file()
    ]
    if artifact_dir.name != "artifacts":
        candidates.extend(nested)
    if not nested and artifact_dir.is_dir():
        candidates.extend(path.parent for path in artifact_dir.glob("artifacts/*/omp-reviewer-telemetry.json.pending"))
    if any((directory / f"{REVIEWER_TELEMETRY_FILENAME}.pending").exists() for directory in candidates):
        return {"status": "guard"}
    existing = [directory for directory in candidates if (directory / REVIEWER_TELEMETRY_FILENAME).is_file()]
    if not existing:
        return {"status": "missing"}
    if len(existing) > 1:
        return {"status": "ambiguous", "candidate_directories": len(existing)}
    path = existing[0] / REVIEWER_TELEMETRY_FILENAME
    try:
        document = json_file(path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"status": "unreadable", "error": str(exc)}
    if document.get("version") != 1 or document.get("complete") is not True:
        return {"status": "incomplete"}
    reviewers: list[dict[str, Any]] = []
    for attempt in document.get("attempts", []):
        if not isinstance(attempt, dict):
            continue
        for subagent in attempt.get("subagents", []):
            if isinstance(subagent, dict) and subagent.get("agent") == "reviewer":
                reviewers.append(subagent)
    if not reviewers:
        return {"status": "no_reviewer"}
    if delivered_id is not None:
        matched = [subagent for subagent in reviewers if subagent.get("id") == delivered_id]
        if not matched:
            return {"status": "delivery_mismatch", "delivered_id": delivered_id}
        subagent = matched[-1]
    else:
        completed = [subagent for subagent in reviewers if subagent.get("status") == "completed"]
        if len(completed) != 1:
            return {"status": "ambiguous", "reviewer_records": len(reviewers)}
        subagent = completed[0]
    messages = [message for message in subagent.get("messages", []) if isinstance(message, dict)]
    models = sorted({str(message.get("model")) for message in messages if isinstance(message.get("model"), str)})
    peak_multipliers = [
        message.get("peak_multiplier")
        for message in messages
        if isinstance(message.get("peak_multiplier"), (int, float))
        and not isinstance(message.get("peak_multiplier"), bool)
    ]
    peak_messages = sum(1 for value in peak_multipliers if value > 1)
    usage: dict[str, Any] | None = {
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cache_read": 0,
        "cache_write": 0,
    }
    reasoning_reported = True
    for message in messages:
        message_usage = message.get("usage")
        if not isinstance(message_usage, dict):
            usage = None
            break
        assert usage is not None
        for bucket in ("input", "output", "cache_read", "cache_write"):
            value = message_usage.get(bucket)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
                usage = None
                break
            usage[bucket] += int(value)
        if usage is None:
            break
        reasoning = message_usage.get("reasoning")
        if isinstance(reasoning, (int, float)) and not isinstance(reasoning, bool) and reasoning >= 0:
            usage["reasoning"] += int(reasoning)
        else:
            reasoning_reported = False
    if usage is not None and not reasoning_reported:
        usage["reasoning"] = None
    return {
        "status": "verified",
        "subagent_id": subagent.get("id"),
        "status_detail": subagent.get("status"),
        "requested_model": subagent.get("requested_model"),
        "model_role": subagent.get("model_role"),
        "resolved_model_identity": subagent.get("resolved_model_identity"),
        "resolved_thinking_level": subagent.get("resolved_thinking_level"),
        "backend_provider": subagent.get("backend_provider"),
        "backend_model": subagent.get("backend_model"),
        "harness_models": models,
        "elapsed_ms": subagent.get("elapsed_ms"),
        "generation_ms": subagent.get("generation_ms"),
        "message_count": subagent.get("message_count"),
        "peak_priced_messages": peak_messages,
        "peak_multipliers_seen": sorted(set(peak_multipliers)),
        "usage": usage,
        "cost_usd": subagent.get("cost_usd", "unreported"),
    }


def selector_key(value: str) -> str:
    """A selector without its trailing thinking level."""
    return value.rsplit(":", 1)[0] if ":" in value.rsplit("/", 1)[-1] else value


def verify_reviewer_telemetry(
    evidence: dict[str, Any], requested: str, expected_upstreams: list[str] | None
) -> dict[str, Any]:
    """Check that the child evidence is the requested reviewer route and effort.

    The adapter reports what Omp recorded; this function compares it with the
    arm's fixed selector. Any disagreement is an attribution mismatch: the
    record keeps the evidence, but the usage and cost do not enter a measured
    comparison.
    """
    if evidence.get("status") != "verified":
        return evidence
    problems: list[str] = []
    telem_requested = evidence.get("requested_model")
    if not isinstance(telem_requested, str) or selector_key(telem_requested) != selector_key(requested):
        problems.append(f"requested_model {telem_requested!r} != {requested!r}")
    effort = requested.rsplit(":", 1)[1] if ":" in requested.rsplit("/", 1)[-1] else None
    resolved = evidence.get("resolved_thinking_level")
    if effort is not None and resolved != effort:
        problems.append(f"resolved_thinking_level {resolved!r} != {effort!r}")
    models = evidence.get("harness_models") or []
    expected_model = normalize_model(requested)
    if not models or any(normalize_model(model) != expected_model for model in models):
        problems.append(f"harness models {models!r} != {expected_model!r}")
    backend = evidence.get("backend_provider")
    if expected_upstreams:
        if backend not in expected_upstreams:
            problems.append(f"backend_provider {backend!r} not in {expected_upstreams!r}")
    role = evidence.get("model_role")
    if role is not None and role != "review":
        problems.append(f"model_role {role!r} != 'review'")
    evidence = dict(evidence)
    evidence["attribution_problems"] = problems
    evidence["attribution_valid"] = not problems
    if problems:
        evidence["status"] = "attribution_mismatch"
    return evidence


def reviewer_result_fields(text: str | None) -> tuple[str, str]:
    """Read explicit reported identity and verdict from the final response."""
    if not text:
        return "unreported", "unreported"
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        identity_match = re.search(r'"reviewer_reported_identity"\s*:\s*"([^"]+)"', text)
        verdict_match = re.search(r'"verdict"\s*:\s*"(clear|defects)"', text)
        return identity_match.group(1) if identity_match else "unreported", verdict_match.group(1) if verdict_match else "unreported"
    if not isinstance(value, dict):
        return "unreported", "unreported"
    identity = value.get("reviewer_reported_identity")
    verdict = value.get("verdict")
    return (
        identity if isinstance(identity, str) and identity else "unreported",
        verdict if isinstance(verdict, str) and verdict in {"clear", "defects"} else "unreported",
    )



def task_rows(run: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    """Index coder_eval result rows by variant, case, and replicate."""
    rows = {}
    for row in run.get("task_results", []):
        key = (str(row.get("variant_id", "unknown")), str(row.get("task_id", "unknown")), int(row.get("replicate_index", 0)))
        if key in rows:
            raise ValueError(f"duplicate task result: {key}")
        rows[key] = row
    return rows


def find_record(run_id: str, explicit: Path | None, provenance: Path) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve the standard run record, refusing ambiguous matches."""
    if explicit:
        record = json_file(explicit)
        if record.get("run_id") != run_id:
            raise ValueError(f"record {explicit} does not match run id {run_id}")
        return explicit, record
    matches = []
    if provenance.is_dir():
        for path in provenance.glob("*.json"):
            try:
                record = json_file(path)
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if record.get("run_id") == run_id:
                matches.append((path, record))
    if len(matches) > 1:
        raise ValueError(f"multiple provenance records match run {run_id}; pass --record explicitly")
    return matches[0] if matches else (None, None)


def result_text(run_dir: Path, variant: str, case: str, repeat: int) -> Path | None:
    """Find the designated result artifact or the adapter's final JSON response."""
    run_root = run_dir.resolve()
    path = run_dir / variant / case / f"{repeat:02d}" / "reviewer-result.txt"
    if path.is_file() and path.resolve().is_relative_to(run_root):
        return path
    root = path.parent
    if root.is_dir():
        matches = [
            candidate for candidate in root.glob("**/reviewer-result.txt")
            if candidate.is_file() and candidate.resolve().is_relative_to(run_root)
        ]
        if len(matches) == 1:
            return matches[0]
        task_path = root / "task.json"
        if task_path.is_file() and task_path.resolve().is_relative_to(run_root):
            return task_path
    return None


def normalize_model(value: str) -> str:
    """Compare model ids without provider prefixes or thinking-level suffixes."""
    model = value.rsplit("/", 1)[-1]
    return model.rsplit(":", 1)[0]


def classification_tokens(values: list[Any]) -> list[str]:
    """Keep only bounded classifier labels supplied by a judge."""
    found = []
    for value in values:
        if not isinstance(value, str):
            continue
        token = value.strip().strip("` -*")
        label = re.match(r"^((?:TP|FN):[\w-]+|DELTA:(?:clear|defects))(?=$|[\s`.,;:])", token)
        if label:
            token = label.group(1)
        if CLASSIFICATION_RE.fullmatch(token) and token not in found:
            found.append(token[:512] + "...[truncated]" if len(token) > 512 else token)
    return found


def judge_evidence(
    run_dir: Path,
    run_record: dict[str, Any] | None,
    variant: str,
    case: str,
    repeat: int,
) -> dict[str, Any]:
    """Read verdict classifications only from independent judge evidence."""
    manifests = sorted((run_dir / "judge").glob("*/manifest.json"))
    if len(manifests) > 1:
        return {"status": "error", "classifications": [], "score": "unavailable", "error": "multiple judge manifests"}
    if manifests:
        manifest = json_file(manifests[0])
        sidecar_path = manifests[0].parent / variant / case / f"{repeat:02d}.json"
        if sidecar_path.is_file():
            sidecar = json_file(sidecar_path)
            criteria = sidecar.get("criteria", [])
            judged = [c for c in criteria if isinstance(c, dict) and c.get("status") == "judged"]
            errors = [c for c in criteria if isinstance(c, dict) and c.get("status") == "error"]
            tokens = classification_tokens([finding for c in judged for finding in c.get("findings", [])])
            status = "judged" if judged and not errors else ("error" if errors else "unavailable")
            return {
                "status": status,
                "classifications": tokens,
                "score": sidecar.get("weighted_score", judged[0].get("score", "unavailable") if judged else "unavailable"),
                "error": errors[0].get("error") if errors else None,
                "freeze_sha": sidecar.get("freeze_sha", manifest.get("freeze_sha", "unreported")),
            }
    attempt = next((a for a in (run_record or {}).get("attempts", []) if a.get("task_id") == case and a.get("variant_id") == variant and a.get("replicate_index") == repeat), {})
    criteria = [c for c in attempt.get("criteria", []) if isinstance(c, dict) and c.get("criterion_type") == "agent_judge"]
    if not criteria:
        return {"status": "unavailable", "classifications": [], "score": "unavailable", "error": None}
    errors = [c for c in criteria if c.get("error")]
    details = [line for c in criteria for line in str(c.get("details", "")).splitlines()]
    tokens = classification_tokens(details)
    return {
        "status": "error" if errors else "judged",
        "classifications": tokens,
        "score": attempt.get("measured_score", "unavailable"),
        "error": errors[0].get("error") if errors else None,
        "freeze_sha": "task-pinned",
    }


def reported_identity(
    record: dict[str, Any] | None,
    case: str,
    repeat: int,
    parent_requested: str,
    helper_requested: str,
    reviewer_requested: str = "unreported",
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return parent, helper, reviewer, and judge identities without conflating roles."""
    case_rows = [row for row in (record or {}).get("cases", []) if row.get("task_id") == case and row.get("replicate_index") == repeat]
    parent_served = case_rows[0].get("model_served", "unreported") if case_rows else "unreported"
    judge = (record or {}).get("judge") or {}
    evidence = telemetry or {}
    return {
        "parent": {"requested": parent_requested, "served": parent_served},
        "helper": {"requested": helper_requested, "served": "unreported"},
        "reviewer": {
            "requested": reviewer_requested,
            "harness": ", ".join(evidence.get("harness_models") or []) or "unreported",
            "role_route": evidence.get("requested_model") or "unreported",
            "backend_served": evidence.get("backend_provider") or "unreported",
            "resolved_thinking_level": evidence.get("resolved_thinking_level") or "unreported",
        },
        "judge": {
            "requested": judge.get("model_requested", "unreported"),
            "served": judge.get("models_observed", "unreported"),
        },
    }


def rubric_correct(entry: dict[str, Any]) -> bool:
    """Whether the independent judge found this attempt's review correct.

    Full reviews need a 1.0; a corrected delta is the suite's accepted pass at
    0.7 with the clear/defect verdict and classification it defines.
    """
    if entry.get("status") != "completed":
        return False
    score = entry.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        return False
    case = entry["case_id"]
    if case.endswith("07-delta-fixed"):
        return (
            score >= 0.7
            and "DELTA:clear" in entry["judge_classifications"]
            and entry["reviewer_verdict"] == "clear"
        )
    if case.endswith("08-delta-incomplete"):
        return (
            score >= 0.7
            and "TP:still-open" in entry["judge_classifications"]
            and entry["reviewer_verdict"] == "defects"
        )
    return score >= 1.0


def summarize(entries: list[dict[str, Any]], cases: list[str]) -> dict[str, Any]:
    """Compute metrics from attempts with both reviewer and judge evidence."""
    classes = [entry for entry in entries if entry["status"] == "completed"]
    actual_positive = {case for case in cases if case.endswith((
        "01-boundary", "02-contract", "03-authorization", "04-integrity"
    ))}
    positive_entries = [entry for entry in classes if entry["case_id"] in actual_positive]
    tp = sum(1 for entry in positive_entries if f"TP:{entry['case_id']}" in entry["judge_classifications"])
    fn = len(positive_entries) - tp
    full = [entry for entry in classes if entry["case_id"].endswith((
        "01-boundary", "02-contract", "03-authorization", "04-integrity", "05-clean-boundary", "06-clean-contract"
    ))]
    fp = sum(1 for entry in full for token in entry["judge_classifications"] if token.startswith("FP:"))
    clean = [entry for entry in classes if entry["case_id"].endswith(("05-clean-boundary", "06-clean-contract"))]
    clean_false_alarms = sum(1 for entry in clean if any(token.startswith("FP:") for token in entry["judge_classifications"]))
    delta = [entry for entry in classes if entry["case_id"].endswith(("07-delta-fixed", "08-delta-incomplete"))]
    delta_correct = sum(
        1 for entry in delta
        if isinstance(entry["score"], (int, float)) and entry["score"] >= 0.7 and (
            (entry["case_id"].endswith("07-delta-fixed") and "DELTA:clear" in entry["judge_classifications"] and entry["reviewer_verdict"] == "clear")
            or (entry["case_id"].endswith("08-delta-incomplete") and "TP:still-open" in entry["judge_classifications"] and entry["reviewer_verdict"] == "defects")
        )
    )
    latencies = [entry["attempt_seconds"] for entry in entries if isinstance(entry.get("attempt_seconds"), (int, float)) and entry["attempt_seconds"] > 0]
    per_case: dict[str, dict[str, int]] = {}
    for case in cases:
        group = [entry for entry in entries if entry["case_id"] == case]
        eligible = [entry for entry in group if entry["status"] == "completed"]
        misses = sum(
            1 for entry in eligible if (
                (case in actual_positive and f"TP:{case}" not in entry["judge_classifications"])
                or (
                    case.endswith("08-delta-incomplete")
                    and "DELTA:clear" in entry["judge_classifications"]
                    and entry["reviewer_verdict"] == "clear"
                )
            )
        )
        per_case[case] = {
            "planned": len(group),
            "eligible": len(eligible),
            "verified_reviewer_completions": sum(entry["reviewer_status"] == "completed" for entry in group),
            "reviewer_errors": sum(entry["reviewer_status"] in {"incomplete", "provider_error", "harness_error"} for entry in group),
            "judge_errors": sum(entry["judge_status"] == "error" for entry in group),
            "reviewer_telemetry_verified": sum(entry["reviewer_telemetry_status"] == "verified" for entry in group),
            "missing": sum(entry["status"] == "unattempted" for entry in group),
            "misses": misses,
        }
    reviewer_completed = sum(entry["reviewer_status"] == "completed" for entry in entries)
    completed = [entry for entry in entries if entry["status"] == "completed"]
    telemetry_verified = [entry for entry in entries if entry["reviewer_telemetry_status"] == "verified"]
    telemetry_costed = [
        entry
        for entry in completed
        if entry["reviewer_telemetry_status"] == "verified"
        and isinstance(entry["reviewer_cost_usd"], (int, float))
        and not isinstance(entry["reviewer_cost_usd"], bool)
    ]
    usage_totals: dict[str, Any] | None = None
    for entry in telemetry_verified:
        usage = entry.get("reviewer_usage")
        if not isinstance(usage, dict):
            continue
        if usage_totals is None:
            usage_totals = {bucket: 0 for bucket in ("input", "output", "reasoning", "cache_read", "cache_write")}
        for bucket in usage_totals:
            value = usage.get(bucket)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if usage_totals[bucket] is not None:
                    usage_totals[bucket] += int(value)
            else:
                usage_totals[bucket] = None
    reviewer_latencies = [
        entry["latency_reviewer_seconds"]
        for entry in telemetry_verified
        if isinstance(entry.get("latency_reviewer_seconds"), (int, float))
    ]
    correct_costed = [entry for entry in telemetry_costed if rubric_correct(entry)]
    total_cost = sum(entry["reviewer_cost_usd"] for entry in telemetry_costed) if telemetry_costed else None
    cost_comparison_valid = bool(completed) and all(
        entry["reviewer_telemetry_status"] == "verified"
        and isinstance(entry["reviewer_cost_usd"], (int, float))
        for entry in completed
    )
    return {
        "attempts": len(entries),
        "eligible": len(classes),
        "verified_reviewer_completions": reviewer_completed,
        "verified_reviewer_completion_rate": reviewer_completed / len(entries) if entries else None,
        "provider_errors": sum(entry["provider_error"] for entry in entries),
        "harness_errors": sum(entry["harness_error"] for entry in entries),
        "judge_errors": sum(entry["judge_status"] == "error" for entry in entries),
        "judge_unavailable": sum(entry["judge_status"] == "unavailable" for entry in entries),
        "reviewer_delivery_unverified": sum(entry["status"] == "reviewer_unverified" for entry in entries),
        "unattempted": sum(entry["status"] == "unattempted" for entry in entries),
        "classification": {
            "unexpected_valid": [
                {"case_id": entry["case_id"], "repeat": entry["repeat"], "evidence": token}
                for entry in classes for token in entry["judge_classifications"]
                if token.startswith("UNEXPECTED_VALID:")
            ],
            "full_review": {
                "tp": tp, "fn": fn, "fp": fp,
                "precision": tp / (tp + fp) if tp + fp else None,
                "precision_denominator": tp + fp,
                "recall": tp / len(positive_entries) if positive_entries else None,
                "recall_eligible_denominator": len(positive_entries),
                "recall_planned_denominator": sum(entry["case_id"] in actual_positive for entry in entries),
            },
            "clean": {
                "false_alarms": clean_false_alarms,
                "eligible_denominator": len(clean),
                "planned_denominator": sum(entry["case_id"].endswith(("05-clean-boundary", "06-clean-contract")) for entry in entries),
            },
            "delta": {
                "correct": delta_correct,
                "eligible_denominator": len(delta),
                "planned_denominator": sum(entry["case_id"].endswith(("07-delta-fixed", "08-delta-incomplete")) for entry in entries),
                "accuracy": delta_correct / len(delta) if delta else None,
            },
        },
        "latency_attempt_seconds": {
            "count": len(latencies),
            "min": min(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
            "mean": sum(latencies) / len(latencies) if latencies else None,
            "population_stddev": math.sqrt(sum((value - sum(latencies) / len(latencies)) ** 2 for value in latencies) / len(latencies)) if latencies else None,
        },
        "reviewer_telemetry": {
            "verified": len(telemetry_verified),
            "guard": sum(entry["reviewer_telemetry_status"] == "guard" for entry in entries),
            "missing": sum(entry["reviewer_telemetry_status"] == "missing" for entry in entries),
            "incomplete": sum(entry["reviewer_telemetry_status"] in {"incomplete", "unreadable"} for entry in entries),
            "no_reviewer": sum(entry["reviewer_telemetry_status"] == "no_reviewer" for entry in entries),
            "delivery_mismatch": sum(entry["reviewer_telemetry_status"] == "delivery_mismatch" for entry in entries),
            "ambiguous": sum(entry["reviewer_telemetry_status"] == "ambiguous" for entry in entries),
            "attribution_mismatch": sum(entry["reviewer_telemetry_status"] == "attribution_mismatch" for entry in entries),
            "usage": usage_totals if usage_totals is not None else "unavailable",
            "cost_usd": total_cost if total_cost is not None else "unavailable",
            "peak_priced_messages": sum(
                entry.get("reviewer_peak_priced_messages", 0)
                for entry in telemetry_verified
                if isinstance(entry.get("reviewer_peak_priced_messages"), int)
            ),
            "peak_priced_attempts": sum(
                1
                for entry in telemetry_verified
                if isinstance(entry.get("reviewer_peak_priced_messages"), int)
                and entry["reviewer_peak_priced_messages"] > 0
            ),
            "cost_reported_attempts": len(telemetry_costed),
            "completed_attempts": len(completed),
            "cost_comparison_valid": cost_comparison_valid,
            "cost_per_rubric_correct_review_usd": (
                total_cost / len(correct_costed) if total_cost is not None and correct_costed else None
            ),
            "rubric_correct_denominator": len(correct_costed),
        },
        "latency_reviewer_seconds": {
            "count": len(reviewer_latencies),
            "min": min(reviewer_latencies) if reviewer_latencies else None,
            "median": statistics.median(reviewer_latencies) if reviewer_latencies else None,
            "max": max(reviewer_latencies) if reviewer_latencies else None,
            "mean": sum(reviewer_latencies) / len(reviewer_latencies) if reviewer_latencies else None,
            "population_stddev": math.sqrt(sum((value - sum(reviewer_latencies) / len(reviewer_latencies)) ** 2 for value in reviewer_latencies) / len(reviewer_latencies)) if reviewer_latencies else None,
        },
        "per_case": per_case,
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    cases = args.case or list(CASE_IDS)
    unknown = sorted(set(cases) - set(CASE_IDS))
    if unknown:
        raise ValueError(f"unknown case id(s): {', '.join(unknown)}")
    if len(set(cases)) != len(cases):
        raise ValueError("case ids must be unique")
    try:
        import yaml
    except ImportError as exc:
        raise ValueError(f"PyYAML is required to read experiment YAML: {exc}") from exc
    experiments = yaml.safe_load(args.experiment.read_text(encoding="utf-8"))
    route_args = experiments.get("defaults", {}).get("agent", {}).get("extra_args", [])
    if "--config" not in route_args:
        raise ValueError("experiment does not pin a reviewer route overlay")
    route_index = route_args.index("--config")
    overlay_path = args.experiment.resolve().parent.parent / "fixtures" / "reviewer-quality" / "shared" / route_args[route_index + 1]
    overlay = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    route_models = overlay.get("modelRoles", {})
    requested = route_models.get("review", "unreported")
    parent_requested = experiments.get("defaults", {}).get("agent", {}).get("model", "unreported")
    helper_requested = route_models.get("task", "unreported")
    restriction = experiments.get("defaults", {}).get("agent", {}).get("vercel_gateway_only")
    expected_upstreams: list[str] | None = None
    if isinstance(restriction, dict):
        for selector, upstreams in restriction.items():
            if selector_key(str(selector)) == selector_key(str(requested)) and isinstance(upstreams, list):
                expected_upstreams = [str(value) for value in upstreams]
                break
    settings_sha = sha256_file(args.experiment)
    overlay_sha = sha256_file(overlay_path)
    entries = []
    observed_identities: list[str] = []
    attribution_mismatches: list[dict[str, str]] = []
    links = []
    for run_dir, record_path in zip(args.run_dir, args.record or [None] * len(args.run_dir)):
        run = json_file(run_dir / "run.json")
        run_id = str(run.get("run_id", run_dir.name))
        resolved_path, record = find_record(run_id, record_path, args.provenance)
        run_experiment = json_file(run_dir / "experiment.json")
        if run_experiment.get("experiment_id") != experiments.get("experiment_id"):
            raise ValueError(f"experiment mismatch in {run_dir}")
        links.append({
            "run_id": run_id,
            "run_dir": run_dir.as_posix(),
            "run_record": resolved_path.as_posix() if resolved_path else "unavailable",
            "run_record_sha256": sha256_file(resolved_path) if resolved_path else "unavailable",
        })
        rows = task_rows(run)
        for case in cases:
            for repeat in range(args.repeats):
                row = rows.get((args.variant, case, repeat))
                artifact = run_dir / args.variant / case / f"{repeat:02d}" / "task.json"
                details = json_file(artifact).get("error_details", {}) if artifact.is_file() else {}
                interrupted = isinstance(details, dict) and details.get("origin") == "manual interruption reconciliation"
                row_status = str(row.get("status", "unreported")).upper() if row else "unattempted"
                error_text = str(row.get("error_message", "") or "") if row else ""
                provider_error = bool(re.search(r"rate[ -]?limit|quota|too many requests|(?:HTTP|status)[ :=]+429", error_text, re.IGNORECASE))
                harness_error = bool(row) and not provider_error and row_status in {"ERROR", "TIMEOUT", "TIMED_OUT", "CRASHED"}
                result_path = result_text(run_dir, args.variant, case, repeat) if row else None
                text = final_response(result_path)
                reviewer_identity, reviewer_verdict = reviewer_result_fields(text)
                delivery_observed = reviewer_delivery_observed(artifact, text)
                telemetry = verify_reviewer_telemetry(
                    reviewer_telemetry_evidence(artifact.parent, delivered_reviewer_id(artifact)),
                    str(requested),
                    expected_upstreams,
                )
                if telemetry.get("status") == "attribution_mismatch":
                    attribution_mismatches.append({
                        "run_id": run_id,
                        "case_id": case,
                        "repeat": str(repeat),
                        "reported": "; ".join(telemetry.get("attribution_problems") or []),
                        "expected_selector": str(requested),
                    })
                telemetry_verified = telemetry.get("status") == "verified"
                reviewer_completed = bool(text) and reviewer_verdict in {"clear", "defects"} and delivery_observed
                parent_reported_reviewer_identity = reviewer_identity
                if not delivery_observed:
                    reviewer_identity = "unreported"
                run_record_attempt = next((v for v in (record or {}).get("attempts", []) if v.get("task_id") == case and v.get("variant_id") == args.variant and v.get("replicate_index") == repeat), {})
                judge = judge_evidence(run_dir, record, args.variant, case, repeat) if row else {"status": "unavailable", "classifications": [], "score": "unavailable"}
                if reviewer_identity != "unreported":
                    observed_identities.append(reviewer_identity)
                    expected_provider = requested.split("/", 1)[0]
                    reported_provider = reviewer_identity.split("/", 1)[0] if "/" in reviewer_identity else None
                    # A Vercel child reports its provider-local id (`mistral/…`),
                    # not the gateway prefix; its upstream is checked from the
                    # adapter's resolved identity instead.
                    provider_mismatch = (
                        expected_provider != "vercel-ai-gateway"
                        and reported_provider is not None
                        and reported_provider != expected_provider
                    )
                    effort_mismatch = ":" in reviewer_identity and reviewer_identity.rsplit(":", 1)[1] != requested.rsplit(":", 1)[1]
                    if provider_mismatch or effort_mismatch or normalize_model(reviewer_identity) != normalize_model(requested):
                        attribution_mismatches.append({"run_id": run_id, "case_id": case, "repeat": str(repeat), "reported": reviewer_identity, "expected_selector": requested})
                if not row:
                    status = "unattempted"
                elif interrupted:
                    status = "interrupted"
                elif provider_error:
                    status = "provider_error"
                elif harness_error:
                    status = "harness_error"
                elif text and not delivery_observed:
                    status = "reviewer_unverified"
                elif not reviewer_completed:
                    status = "reviewer_error"
                elif judge["status"] == "error":
                    status = "judge_error"
                elif judge["status"] != "judged":
                    status = "judge_unavailable"
                else:
                    status = "completed"
                classifications = judge["classifications"]
                case_alias = case.rsplit("-", 1)[-1]
                classifications = [
                    token.replace(f"TP:{case_alias}", f"TP:{case}").replace(f"FN:{case_alias}", f"FN:{case}")
                    if token in {f"TP:{case_alias}", f"FN:{case_alias}"} else token
                    for token in classifications
                ]
                run_record_case = next((v for v in (record or {}).get("cases", []) if v.get("task_id") == case and v.get("replicate_index") == repeat), {})
                attempt_seconds = run_record_case.get("elapsed_seconds")
                if not isinstance(attempt_seconds, (int, float)) and row:
                    attempt_seconds = row.get("duration")
                reviewer_latency = telemetry.get("elapsed_ms")
                reviewer_latency_seconds = (
                    reviewer_latency / 1000
                    if isinstance(reviewer_latency, (int, float)) and not isinstance(reviewer_latency, bool)
                    else "unavailable"
                )
                cost = telemetry.get("cost_usd")
                if not telemetry_verified or not delivery_observed:
                    reviewer_cost: float | str = "unavailable"
                elif isinstance(cost, (int, float)) and not isinstance(cost, bool):
                    reviewer_cost = cost
                else:
                    reviewer_cost = "unreported"
                entries.append({
                    "case_id": case, "repeat": repeat, "arm": args.arm, "variant_id": args.variant,
                    "run_id": run_id, "status": status,
                    "task_status": row.get("status", "unreported") if row else "unattempted",
                    "reviewer_status": "completed" if reviewer_completed else ("interrupted" if interrupted else ("provider_error" if provider_error else ("harness_error" if harness_error else ("unattempted" if not row else ("delivery_unverified" if text and not delivery_observed else "incomplete"))))),
                    "provider_error": provider_error,
                    "harness_error": harness_error and not interrupted,
                    "judge_status": judge["status"],
                    "judge_error": judge.get("error", "unavailable"),
                    "score": judge.get("score", "unavailable"),
                    "reviewer_result": bounded_response(text) if delivery_observed and text is not None else "unavailable",
                    "parent_final_response": bounded_response(text) if not delivery_observed and text is not None else "unavailable",
                    "reviewer_verdict": reviewer_verdict if delivery_observed else "unreported",
                    "judge_classifications": classifications,
                    "reviewer_requested": requested,
                    "reviewer_delivery_observed": delivery_observed,
                    "parent_reported_reviewer_identity": parent_reported_reviewer_identity,
                    "reviewer_reported_identity": reviewer_identity,
                    "reviewer_harness_model": ", ".join(telemetry.get("harness_models") or []) or "unreported",
                    "reviewer_backend_served": telemetry.get("backend_provider") or "unreported",
                    "reviewer_telemetry_status": telemetry.get("status"),
                    "reviewer_telemetry": telemetry,
                    "reviewer_subagent_id": telemetry.get("subagent_id", "unreported"),
                    "reviewer_resolved_thinking_level": telemetry.get("resolved_thinking_level") or "unreported",
                    "reviewer_peak_priced_messages": telemetry.get("peak_priced_messages", "unavailable"),
                    "identity": reported_identity(record, case, repeat, parent_requested, helper_requested, str(requested), telemetry),
                    "latency_reviewer_seconds": reviewer_latency_seconds,
                    "attempt_seconds": attempt_seconds if not interrupted and isinstance(attempt_seconds, (int, float)) else None,
                    "reviewer_usage": telemetry.get("usage") if telemetry_verified else "unavailable",
                    "reviewer_cost_usd": reviewer_cost,
                    "parent_token_usage": run_record_case.get("token_usage", "unavailable"),
                    "parent_cost_usd": run_record_case.get("cost", "unavailable")
                    if isinstance(run_record_case.get("cost"), (int, float))
                    else "unavailable",
                    "parent_cost_source": run_record_case.get("cost_source", "unavailable"),
                    "judge_freeze_sha": judge.get("freeze_sha", "unreported"),
                    "artifact_sha256": sha256_file(result_path) if result_path and result_path.is_file() else "unavailable",
                })
    identity_required = sum(entry["reviewer_status"] == "completed" for entry in entries)
    attribution_valid = (
        not attribution_mismatches
        if identity_required > 0 and len(observed_identities) == identity_required
        else None
    )
    summary = summarize(entries, cases)
    telemetry_summary = summary["reviewer_telemetry"]
    telemetry_attribution_valid = (
        telemetry_summary["attribution_mismatch"] == 0
        and telemetry_summary["delivery_mismatch"] == 0
        and telemetry_summary["ambiguous"] == 0
        if telemetry_summary["verified"] > 0
        else None
    )
    parent_tokens: dict[str, int | None] = {
        "uncached_input_tokens": 0,
        "output_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "reasoning_tokens": 0,
    }
    parent_cost: float | None = 0.0
    for entry in entries:
        usage = entry.get("parent_token_usage")
        if isinstance(usage, dict):
            for bucket in parent_tokens:
                value = usage.get(bucket)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if parent_tokens[bucket] is not None:
                        parent_tokens[bucket] += int(value)
                else:
                    parent_tokens[bucket] = None
        else:
            parent_tokens = {bucket: None for bucket in parent_tokens}
        cost = entry.get("parent_cost_usd")
        if isinstance(cost, (int, float)) and parent_cost is not None:
            parent_cost += cost
        else:
            parent_cost = None
    judge_usage = (record or {}).get("judge", {}).get("usage", "unavailable") if args.run_dir else "unavailable"
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "arm": args.arm,
        "attribution": {
            "expected_reviewer_selector": requested,
            "expected_reviewer_upstreams": expected_upstreams or "unrestricted",
            "expected_model_id": normalize_model(requested),
            "reviewer_reported_identities": sorted(set(observed_identities)),
            "reported_model_ids": sorted({normalize_model(value) for value in observed_identities}),
            "valid": attribution_valid,
            "telemetry_valid": telemetry_attribution_valid,
            "mismatches": attribution_mismatches,
            "basis": (
                "captured reviewer delivery, adapter child telemetry, and Omp's resolved "
                "role route, thinking level and upstream; a missing served identity is unreported"
            ),
        },
        "analysis_valid": attribution_valid,
        "cost_comparison_valid": telemetry_summary["cost_comparison_valid"],
        "usage": {
            "parent": {
                "tokens": parent_tokens,
                "cost_usd": parent_cost if parent_cost is not None else "unavailable",
                "source": "coder_eval record: parent Omp messages; Omp's own catalog is not used",
            },
            "reviewer": {
                "tokens": telemetry_summary["usage"],
                "cost_usd": telemetry_summary["cost_usd"],
                "source": "adapter child telemetry, priced per message from the endpoint cards",
            },
            "judge": {
                "requested": (record or {}).get("judge", {}).get("model_requested", "unreported"),
                "served": (record or {}).get("judge", {}).get("models_observed", "unreported"),
                "tokens": judge_usage,
                "source": "the run record's judge usage; per-attempt judge usage is in its sidecar",
            },
        },
        "settings": {
            "experiment_path": args.experiment.as_posix(),
            "experiment_sha256": settings_sha,
            "route_overlay_path": overlay_path.as_posix(),
            "route_overlay_sha256": overlay_sha,
        },
        "planned": {"cases": cases, "repeats_per_case": args.repeats, "attempts": len(cases) * args.repeats * len(args.run_dir)},
        "coverage_complete": all(entry["status"] not in {"unattempted", "interrupted"} for entry in entries),
        "cohort_complete": all(entry["status"] not in {"unattempted", "interrupted"} and str(entry["task_status"]).upper() not in {"UNREPORTED", "PENDING", "RUNNING"} for entry in entries),
        "runs": links,
        "summary": summary,
        "attempts": entries,
        "winner": None,
    }


# ---------------------------------------------------------------------------
# Self-tests: offline, inline frames and artifacts.
# ---------------------------------------------------------------------------


def _adapter_module(name: str) -> Any:
    """Import a pure adapter module from the checkout, without coder_eval."""
    src = Path(__file__).resolve().parent.parent / "evals" / "coder-eval-omp" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return importlib.import_module(f"coder_eval_omp.{name}")


def _telemetry_frames() -> list[dict[str, Any]]:
    """The shape Omp 18.22.2 emitted in the reviewer telemetry probe."""
    return [
        {
            "type": "subagent_lifecycle",
            "payload": {
                "id": "ReviewerChild",
                "agent": "reviewer",
                "parentToolCallId": "call_reviewer",
                "status": "started",
            },
        },
        {
            "type": "subagent_progress",
            "payload": {
                "agent": "reviewer",
                "parentToolCallId": "call_reviewer",
                "progress": {
                    "id": "ReviewerChild",
                    "status": "running",
                    "modelOverride": ["vercel-ai-gateway/mistral/mistral-large-4:low"],
                    "modelRole": "review",
                    "resolvedModelIdentity": "vercel-ai-gateway/mistral/mistral-large-4@mistral",
                    "resolvedThinkingLevel": "low",
                    "resolvedModel": "vercel-ai-gateway/mistral/mistral-large-4@mistral:low",
                },
            },
        },
        {
            "type": "subagent_event",
            "payload": {
                "id": "ReviewerChild",
                "event": {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "model": "mistral/mistral-large-4",
                        "provider": "vercel-ai-gateway",
                        "responseId": "gen_test",
                        "timestamp": 1795036498397,
                        "duration": 2069.2258299999994,
                        "ttft": 1333.5296550000003,
                        "stopReason": "stop",
                        "usage": {
                            "input": 1000,
                            "output": 200,
                            "cacheRead": 100,
                            "cacheWrite": 0,
                            "reasoningTokens": 50,
                        },
                    },
                },
            },
        },
        {
            "type": "subagent_lifecycle",
            "payload": {
                "id": "ReviewerChild",
                "agent": "reviewer",
                "parentToolCallId": "call_reviewer",
                "status": "completed",
            },
        },
    ]


def _test_reviewer_telemetry() -> None:
    telemetry = _adapter_module("telemetry")
    home = _adapter_module("home")
    recorder = telemetry.ReviewerTelemetry()
    for frame in _telemetry_frames():
        assert recorder.ingest(frame)
    document = recorder.document(1, 0, "vercel-ai-gateway/openai/gpt-6.1-sol:low")
    assert len(document["subagents"]) == 1
    child = document["subagents"][0]
    assert child["agent"] == "reviewer"
    assert child["parent_tool_call_id"] == "call_reviewer"
    assert child["requested_model"] == "vercel-ai-gateway/mistral/mistral-large-4:low"
    assert child["backend_provider"] == "mistral"
    assert child["resolved_thinking_level"] == "low"
    assert child["messages"][0]["usage"] == {
        "input": 1000,
        "output": 200,
        "cache_read": 100,
        "cache_write": 0,
        "reasoning": 50,
    }
    assert isinstance(child["cost_usd"], float)

    with tempfile.TemporaryDirectory(prefix="reviewer-selftest-") as tmp:
        attempt_dir = Path(tmp)
        sandbox = attempt_dir / "artifacts" / "reviewer-quality-01-boundary"
        sandbox.mkdir(parents=True)
        (sandbox / REVIEWER_TELEMETRY_FILENAME).write_text(
            telemetry.artifact_document([document], complete=True), encoding="utf-8"
        )
        evidence = reviewer_telemetry_evidence(attempt_dir, "ReviewerChild")
        assert evidence["status"] == "verified", evidence
        assert evidence["usage"] == {
            "input": 1000,
            "output": 200,
            "reasoning": 50,
            "cache_read": 100,
            "cache_write": 0,
        }
        assert isinstance(evidence["cost_usd"], float)

        verified = verify_reviewer_telemetry(
            evidence, "vercel-ai-gateway/mistral/mistral-large-4:low", ["mistral"]
        )
        assert verified["status"] == "verified"
        mismatch = verify_reviewer_telemetry(
            evidence, "vercel-ai-gateway/mistral/mistral-large-4:low", ["baseten"]
        )
        assert mismatch["status"] == "attribution_mismatch"
        assert any("backend_provider" in problem for problem in mismatch["attribution_problems"])

        wrong_effort = verify_reviewer_telemetry(
            evidence, "vercel-ai-gateway/mistral/mistral-large-4:high", ["mistral"]
        )
        assert wrong_effort["status"] == "attribution_mismatch"

        (sandbox / f"{REVIEWER_TELEMETRY_FILENAME}.pending").mkdir()
        assert reviewer_telemetry_evidence(attempt_dir, "ReviewerChild")["status"] == "guard"
        (sandbox / f"{REVIEWER_TELEMETRY_FILENAME}.pending").rmdir()
        (sandbox / REVIEWER_TELEMETRY_FILENAME).unlink()
        assert reviewer_telemetry_evidence(attempt_dir, "ReviewerChild")["status"] == "missing"

        # A child message without usage makes the priced total unreported.
        incomplete = telemetry.ReviewerTelemetry()
        frames = _telemetry_frames()
        frames[2]["payload"]["event"]["message"].pop("usage")
        for frame in frames:
            incomplete.ingest(frame)
        fragment = incomplete.document(1, 0, "parent:low")
        assert fragment["subagents"][0]["cost_usd"] == "unreported"
        assert fragment["subagents"][0]["messages"][0]["usage"] is None

        # Two role routes merge into one private models.yml; a duplicate is refused.
        agent_dir = Path(tmp) / "agent"
        agent_dir.mkdir()
        home.restrict_model_routes(
            agent_dir,
            [
                ("vercel-ai-gateway", "openai/gpt-6.1-sol", ["openai"]),
                ("vercel-ai-gateway", "mistral/mistral-large-4", ["mistral"]),
            ],
        )
        merged = yaml.safe_load((agent_dir / "models.yml").read_text(encoding="utf-8"))
        overrides = merged["providers"]["vercel-ai-gateway"]["modelOverrides"]
        assert overrides["openai/gpt-6.1-sol"]["compat"]["vercelGatewayRouting"]["only"] == ["openai"]
        assert overrides["mistral/mistral-large-4"]["compat"]["vercelGatewayRouting"]["only"] == ["mistral"]
        try:
            home.restrict_model_routes(
                agent_dir,
                [
                    ("vercel-ai-gateway", "mistral/mistral-large-4", ["mistral"]),
                    ("vercel-ai-gateway", "mistral/mistral-large-4", ["zai"]),
                ],
            )
        except ValueError:
            pass
        else:
            raise AssertionError("restrict_model_routes accepted two allowlists for one model")


def _test_delivery_and_cost_summary() -> None:
    with tempfile.TemporaryDirectory(prefix="reviewer-selftest-") as tmp:
        artifact = Path(tmp) / "task.json"
        artifact.write_text(
            json.dumps(
                {
                    "iterations": [
                        {
                            "commands": [
                                {
                                    "result_summary": (
                                        '<task-result id="ReviewerChild" agent="reviewer" status="completed">'
                                        "<output>{}</output></task-result>"
                                    )
                                }
                            ]
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        assert delivered_reviewer_id(artifact) == "ReviewerChild"

    entries = [
        {
            "case_id": "reviewer-quality-01-boundary",
            "repeat": 0,
            "status": "completed",
            "reviewer_status": "completed",
            "reviewer_telemetry_status": "verified",
            "reviewer_cost_usd": 0.5,
            "reviewer_usage": {
                "input": 100,
                "output": 10,
                "reasoning": 5,
                "cache_read": 0,
                "cache_write": 0,
            },
            "latency_reviewer_seconds": 2.0,
            "judge_classifications": ["TP:reviewer-quality-01-boundary"],
            "reviewer_verdict": "defects",
            "score": 1.0,
            "provider_error": False,
            "harness_error": False,
            "judge_status": "judged",
            "attempt_seconds": 10.0,
        },
        {
            "case_id": "reviewer-quality-02-contract",
            "repeat": 0,
            "status": "completed",
            "reviewer_status": "completed",
            "reviewer_telemetry_status": "missing",
            "reviewer_cost_usd": "unavailable",
            "reviewer_usage": "unavailable",
            "latency_reviewer_seconds": "unavailable",
            "judge_classifications": ["FN:reviewer-quality-02-contract"],
            "reviewer_verdict": "clear",
            "score": 0.0,
            "provider_error": False,
            "harness_error": False,
            "judge_status": "judged",
            "attempt_seconds": 10.0,
        },
    ]
    summary = summarize(entries, [entry["case_id"] for entry in entries])
    assert summary["reviewer_telemetry"]["verified"] == 1
    assert summary["reviewer_telemetry"]["missing"] == 1
    assert summary["reviewer_telemetry"]["cost_comparison_valid"] is False
    assert summary["reviewer_telemetry"]["cost_per_rubric_correct_review_usd"] == 0.5
    assert summary["latency_reviewer_seconds"]["median"] == 2.0


def _run_self_tests() -> None:
    _test_reviewer_telemetry()
    _test_delivery_and_cost_summary()


def parser() -> argparse.ArgumentParser:
    """Build the reviewer evidence collector's command-line parser."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--arm", required=True, help="explicit measured arm label")
    p.add_argument("--experiment", type=Path, required=True, help="frozen experiment YAML")
    p.add_argument("--run-dir", type=Path, action="append", required=True, help="one coder_eval run directory; repeat for distinct run attempts")
    p.add_argument("--record", type=Path, action="append", help="record path for each --run-dir, in matching order")
    p.add_argument("--repeats", type=int, required=True, help="planned repeats per case per run")
    p.add_argument("--case", action="append", help="planned case id; default is the frozen eight-case suite")
    p.add_argument("--variant", default="reviewer")
    p.add_argument("--provenance", type=Path, default=Path("evals/provenance"), help="directory containing evals-record outputs")
    p.add_argument("--output", type=Path, required=True, help="supplementary JSON output path")
    return p


def main(argv: list[str] | None = None) -> int:
    """Collect bounded evidence and write the supplementary JSON artifact."""
    args = parser().parse_args(argv)
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    if args.record is not None and len(args.record) != len(args.run_dir):
        raise SystemExit("pass exactly one --record per --run-dir")
    try:
        _run_self_tests()
    except AssertionError as exc:
        print(f"error: collector self-test failed: {exc}", file=sys.stderr)
        return 2
    try:
        result = build(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
