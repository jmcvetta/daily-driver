#!/usr/bin/env python3
"""Collect bounded reviewer-quality evidence from explicit coder_eval runs."""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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


def bounded_text(path: Path | None) -> str | None:
    """Return the bounded final reviewer response, never the full transcript."""
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
    if len(text) > MAX_FINDINGS_CHARS:
        text = text[:MAX_FINDINGS_CHARS] + "\n...[truncated]"
    return text.strip()


def reviewer_result_fields(text: str | None) -> tuple[str, str]:
    """Read explicit reported identity and verdict from the bounded reviewer result."""
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
) -> dict[str, Any]:
    """Return parent, helper, and judge identities without conflating roles."""
    case_rows = [row for row in (record or {}).get("cases", []) if row.get("task_id") == case and row.get("replicate_index") == repeat]
    parent_served = case_rows[0].get("model_served", "unreported") if case_rows else "unreported"
    judge = (record or {}).get("judge") or {}
    return {
        "parent": {"requested": parent_requested, "served": parent_served},
        "helper": {"requested": helper_requested, "served": "unreported"},
        "judge": {
            "requested": judge.get("model_requested", "unreported"),
            "served": judge.get("models_observed", "unreported"),
        },
    }


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
    clean_false_alarms = sum(1 for entry in clean if any(token.startswith(("TP:", "FP:", "UNEXPECTED_VALID:")) for token in entry["judge_classifications"]))
    delta = [entry for entry in classes if entry["case_id"].endswith(("07-delta-fixed", "08-delta-incomplete"))]
    delta_correct = sum(
        1 for entry in delta
        if (
            ("DELTA:clear" in entry["judge_classifications"] and entry["reviewer_verdict"] == "clear")
            or ("DELTA:defects" in entry["judge_classifications"] and entry["reviewer_verdict"] == "defects")
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
            "reviewer_completed": sum(entry["reviewer_status"] == "completed" for entry in group),
            "reviewer_errors": sum(entry["reviewer_status"] in {"incomplete", "provider_error", "harness_error"} for entry in group),
            "judge_errors": sum(entry["judge_status"] == "error" for entry in group),
            "missing": sum(entry["status"] == "unattempted" for entry in group),
            "misses": misses,
        }
    reviewer_completed = sum(entry["reviewer_status"] == "completed" for entry in entries)
    return {
        "attempts": len(entries),
        "eligible": len(classes),
        "reviewer_completed": reviewer_completed,
        "reviewer_completion_rate": reviewer_completed / len(entries) if entries else None,
        "provider_errors": sum(entry["provider_error"] for entry in entries),
        "harness_errors": sum(entry["harness_error"] for entry in entries),
        "judge_errors": sum(entry["judge_status"] == "error" for entry in entries),
        "judge_unavailable": sum(entry["judge_status"] == "unavailable" for entry in entries),
        "unattempted": sum(entry["status"] == "unattempted" for entry in entries),
        "classification": {
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
                row_status = str(row.get("status", "unreported")).upper() if row else "unattempted"
                error_text = str(row.get("error", "") or "")
                provider_error = bool(re.search(r"rate[ -]?limit|quota|too many requests|(?:HTTP|status)[ :=]+429", error_text, re.IGNORECASE))
                harness_error = bool(row) and row_status in {"ERROR", "TIMEOUT", "TIMED_OUT", "CRASHED"}
                result_path = result_text(run_dir, args.variant, case, repeat) if row else None
                text = bounded_text(result_path)
                reviewer_identity, reviewer_verdict = reviewer_result_fields(text)
                reviewer_completed = bool(text) and reviewer_verdict in {"clear", "defects"}
                run_record_attempt = next((v for v in (record or {}).get("attempts", []) if v.get("task_id") == case and v.get("variant_id") == args.variant and v.get("replicate_index") == repeat), {})
                judge = judge_evidence(run_dir, record, args.variant, case, repeat) if row else {"status": "unavailable", "classifications": [], "score": "unavailable"}
                if reviewer_identity != "unreported":
                    observed_identities.append(reviewer_identity)
                    if normalize_model(reviewer_identity) != normalize_model(requested):
                        attribution_mismatches.append({"run_id": run_id, "case_id": case, "repeat": str(repeat), "reported": reviewer_identity, "expected_selector": requested})
                if not row:
                    status = "unattempted"
                elif provider_error:
                    status = "provider_error"
                elif harness_error:
                    status = "harness_error"
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
                entries.append({
                    "case_id": case, "repeat": repeat, "arm": args.arm, "variant_id": args.variant,
                    "run_id": run_id, "status": status,
                    "task_status": row.get("status", "unreported") if row else "unattempted",
                    "reviewer_status": "completed" if reviewer_completed else ("provider_error" if provider_error else ("harness_error" if harness_error else ("unattempted" if not row else "incomplete"))),
                    "provider_error": provider_error,
                    "harness_error": harness_error,
                    "judge_status": judge["status"],
                    "judge_error": judge.get("error", "unavailable"),
                    "score": judge.get("score", "unavailable"),
                    "reviewer_result": text if text is not None else "unavailable",
                    "reviewer_verdict": reviewer_verdict,
                    "judge_classifications": classifications,
                    "reviewer_requested": requested,
                    "reviewer_reported_identity": reviewer_identity,
                    "reviewer_backend_served": "unreported",
                    "identity": reported_identity(record, case, repeat, parent_requested, helper_requested),
                    "latency_reviewer_seconds": "unavailable",
                    "attempt_seconds": attempt_seconds if isinstance(attempt_seconds, (int, float)) else None,
                    "reviewer_usage": "unavailable",
                    "judge_freeze_sha": judge.get("freeze_sha", "unreported"),
                    "artifact_sha256": sha256_file(result_path) if result_path and result_path.is_file() else "unavailable",
                })
    identity_required = sum(entry["reviewer_status"] == "completed" for entry in entries)
    attribution_valid = (
        not attribution_mismatches
        if identity_required > 0 and len(observed_identities) == identity_required
        else None
    )
    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "arm": args.arm,
        "attribution": {
            "expected_reviewer_selector": requested,
            "expected_model_id": normalize_model(requested),
            "reviewer_reported_identities": sorted(set(observed_identities)),
            "reported_model_ids": sorted({normalize_model(value) for value in observed_identities}),
            "valid": attribution_valid,
            "mismatches": attribution_mismatches,
            "basis": "reviewer-reported session identity only; backend-served identity is unreported",
        },
        "analysis_valid": attribution_valid,
        "settings": {
            "experiment_path": args.experiment.as_posix(),
            "experiment_sha256": settings_sha,
            "route_overlay_path": overlay_path.as_posix(),
            "route_overlay_sha256": overlay_sha,
        },
        "planned": {"cases": cases, "repeats_per_case": args.repeats, "attempts": len(cases) * args.repeats * len(args.run_dir)},
        "coverage_complete": all(entry["task_status"] != "unattempted" for entry in entries),
        "cohort_complete": all(str(entry["task_status"]).upper() not in {"UNATTEMPTED", "UNREPORTED", "PENDING", "RUNNING"} for entry in entries),
        "runs": links,
        "summary": summarize(entries, cases),
        "attempts": entries,
        "winner": None,
    }


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
