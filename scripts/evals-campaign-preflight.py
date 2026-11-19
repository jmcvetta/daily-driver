#!/usr/bin/env python3
"""Check a reviewer-quality campaign's inputs before any paid dispatch.

The checks are read-only. The usage probe reads the provider's own balance
report; it never spends. An unavailable balance is a warning, not a pass: the
paid smoke is the probe. A missing judge calibration, a stale prompt version,
an unpriceable route, an unmaterialized task tree, or a route/arm disagreement
is a failure.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
REVIEWER_CASES = (
    "reviewer-quality-01-boundary",
    "reviewer-quality-02-contract",
    "reviewer-quality-03-authorization",
    "reviewer-quality-04-integrity",
    "reviewer-quality-05-clean-boundary",
    "reviewer-quality-06-clean-contract",
    "reviewer-quality-07-delta-fixed",
    "reviewer-quality-08-delta-incomplete",
)
RETRY_FLAGS = ("enabled", "modelFallback", "usageAwareFallback", "waitForUsageReset")


def check(name: str, status: str, detail: str, remedy: str = "") -> dict[str, str]:
    """One named check result; status is ok, warn, or fail."""
    return {"name": name, "status": status, "detail": detail, "remedy": remedy}


def selector_key(value: str) -> str:
    """A selector without its trailing thinking level."""
    return value.rsplit(":", 1)[0] if ":" in value.rsplit("/", 1)[-1] else value


def load_yaml(path: Path) -> dict[str, Any]:
    """Read one mapping from YAML."""
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a mapping")
    return value


def load_judge_module() -> Any:
    """Import scripts/evals-judge.py without copying its calibration contract."""
    path = ROOT / "scripts" / "evals-judge.py"
    spec = importlib.util.spec_from_file_location("evals_judge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["evals_judge"] = module
    spec.loader.exec_module(module)
    return module


def load_pricing_module() -> Any:
    """Import the adapter's price-table reader."""
    src = ROOT / "evals" / "coder-eval-omp" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return importlib.import_module("coder_eval_omp.pricing")


def experiment_arm(path: Path) -> dict[str, Any]:
    """Read one arm's experiment, its resolved overlay, and its fixed routes."""
    data = load_yaml(path)
    agent = (data.get("defaults") or {}).get("agent") or {}
    extra = agent.get("extra_args") or []
    if "--config" not in extra:
        raise ValueError(f"{path}: defaults.agent.extra_args does not name --config")
    route = extra[extra.index("--config") + 1]
    matches = sorted((ROOT / "evals" / "fixtures").glob(f"*/shared/{route}"))
    if len(matches) != 1:
        raise ValueError(f"{path}: expected one route overlay for {route}; found {len(matches)}")
    overlay = load_yaml(matches[0])
    models = overlay.get("modelRoles") or {}
    return {
        "path": path,
        "experiment_id": data.get("experiment_id"),
        "parent": agent.get("model"),
        "helper": models.get("task"),
        "review": models.get("review"),
        "allowed": agent.get("vercel_gateway_only") or {},
        "task": overlay.get("task") or {},
        "retry": overlay.get("retry") or {},
        "record_reviewer_telemetry": agent.get("record_reviewer_telemetry") is True,
        "repeats": (data.get("defaults") or {}).get("repeats"),
        "overlay": matches[0],
    }


def route_reasons(arms: list[dict[str, Any]]) -> list[str]:
    """Every route or arm disagreement that makes the cohort unmatched."""
    reasons: list[str] = []
    ids = [str(arm.get("experiment_id")) for arm in arms]
    if len(set(ids)) != len(ids):
        reasons.append("experiment_id values are not unique")
    parents = {str(arm.get("parent")) for arm in arms}
    helpers = {str(arm.get("helper")) for arm in arms}
    reviews = [str(arm.get("review")) for arm in arms]
    if len(parents) != 1:
        reasons.append(f"parent routes differ: {sorted(parents)}")
    if len(helpers) != 1:
        reasons.append(f"helper routes differ: {sorted(helpers)}")
    if len(set(reviews)) != len(reviews):
        reasons.append("review routes are not unique across arms")
    for arm in arms:
        label = str(arm.get("experiment_id") or arm["path"].name)
        if not arm.get("parent"):
            reasons.append(f"{label}: parent route is missing")
        if not arm.get("helper"):
            reasons.append(f"{label}: helper route is missing")
        if not arm.get("review") or arm.get("review") == "unreported":
            reasons.append(f"{label}: modelRoles.review is missing")
        if (arm.get("task") or {}).get("maxConcurrency") != 1:
            reasons.append(
                f"{label}: task.maxConcurrency is "
                f"{(arm.get('task') or {}).get('maxConcurrency')!r}; expected 1"
            )
        for flag in RETRY_FLAGS:
            value = (arm.get("retry") or {}).get(flag)
            if value not in (False, None):
                reasons.append(f"{label}: retry.{flag} is {value!r}; expected false")
        for model in (arm.get("parent"), arm.get("helper"), arm.get("review")):
            if not isinstance(model, str) or not model.startswith("vercel-ai-gateway/"):
                continue
            upstream = model.split("/", 1)[1].split("/", 1)[0]
            match = next(
                (
                    value
                    for key, value in (arm.get("allowed") or {}).items()
                    if selector_key(str(key)) == selector_key(model)
                ),
                None,
            )
            if match != [upstream]:
                reasons.append(
                    f"{label}: {model} restriction is {match!r}; expected [{upstream!r}]"
                )
        if (
            isinstance(arm.get("review"), str)
            and arm["review"].startswith("vercel-ai-gateway/")
            and not arm.get("record_reviewer_telemetry")
        ):
            reasons.append(f"{label}: record_reviewer_telemetry is not true")
    return reasons


def calibration_documents(path: Path) -> list[dict[str, Any]]:
    """The result records behind one judge calibration.

    A judge names either one standard result or a wrapper whose `sets` list
    names the records for each committed label set. Both forms are checked;
    the wrapper is not trusted as a summary.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} is not a JSON object")
    sets = data.get("sets")
    if sets is None:
        return [data]
    if not isinstance(sets, list) or not sets:
        raise ValueError(f"{path}: sets must be a non-empty list")
    records = []
    for entry in sets:
        if not isinstance(entry, dict) or not entry.get("record"):
            raise ValueError(f"{path}: each set needs a record path")
        record = json.loads((path.parent / str(entry["record"])).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError(f"{path}: set record {entry['record']} is not an object")
        records.append(record)
    return records


def matching_labels(
    record: dict[str, Any], module: Any, candidates: list[Path]
) -> tuple[Path, dict[str, Any]] | tuple[None, None]:
    """Find the committed label set that produced this calibration record."""
    for path in candidates:
        labels = load_yaml(path)
        if module.sha(labels) == record.get("labels_sha"):
            return path, labels
    return None, None


def judge_reasons(
    identity: dict[str, Any],
    record: dict[str, Any],
    labels_sha: str,
    rubric_sha: str,
    current_prompt_version: str,
) -> list[str]:
    """Every way the committed calibration no longer describes this judge."""
    reasons: list[str] = []
    if record.get("met_acceptance_rule") is not True:
        reasons.append("calibration did not meet its acceptance rule")
    recorded = record.get("judge") or {}
    for field in ("judge_id", "route", "model_requested", "settings"):
        if recorded.get(field) != identity.get(field):
            reasons.append(
                f"calibration judge {field} is {recorded.get(field)!r}; "
                f"current {identity.get(field)!r}"
            )
    if record.get("labels_sha") != labels_sha:
        reasons.append("calibration labels_sha does not match the committed labels")
    if record.get("rubric_prompt_sha") != rubric_sha:
        reasons.append("calibration rubric_prompt_sha does not match the current rubric")
    if record.get("prompt_version") != current_prompt_version:
        reasons.append(
            f"calibration prompt_version is {record.get('prompt_version')!r}; "
            f"current {current_prompt_version!r}"
        )
    return reasons


def price_reasons(
    routes: list[tuple[str, str]], cards: dict[str, Any], unpriced: dict[str, Any]
) -> list[tuple[str, str]]:
    """Price-card completeness: a card, or an explicit unpriced declaration."""
    results: list[tuple[str, str]] = []
    for model, role in routes:
        key = selector_key(model)
        if key in cards:
            continue
        declaration = unpriced.get(key)
        if isinstance(declaration, dict) and declaration.get("unpriced_reason"):
            reason = str(declaration["unpriced_reason"]).replace("\n", " ")[:120]
            results.append(
                (
                    "warn" if role == "review" else "ok",
                    f"{model} is unpriced: {reason}",
                )
            )
        else:
            results.append(
                (
                    "fail",
                    f"{model} has no price card and no unpriced_reason",
                )
            )
    return results


def usage_reasons(report: dict[str, Any], provider: str) -> list[tuple[str, str]]:
    """Balance findings from `omp usage --json`; missing data is a warning."""
    if not isinstance(report, dict):
        return [("warn", f"{provider}: usage report unavailable")]
    accounts = {
        entry.get("provider")
        for entry in (report.get("accountsWithoutUsage") or [])
        if isinstance(entry, dict)
    }
    reports = [
        entry
        for entry in (report.get("reports") or [])
        if isinstance(entry, dict) and entry.get("provider") == provider
    ]
    if provider in accounts or not reports:
        return [("warn", f"{provider}: balance unavailable; the paid smoke is the probe")]
    results: list[tuple[str, str]] = []
    for account in reports:
        for limit in account.get("limits") or []:
            amount = limit.get("amount") or {}
            used = amount.get("usedFraction")
            status = limit.get("status")
            window = (limit.get("window") or {}).get("id") or limit.get("id")
            if status == "exhausted" or (
                isinstance(used, (int, float)) and not isinstance(used, bool) and used >= 1.0
            ):
                results.append(
                    ("fail", f"{provider} {window}: used fraction {used!r}, status {status!r}")
                )
            elif isinstance(used, (int, float)) and not isinstance(used, bool) and used >= 0.9:
                results.append(("warn", f"{provider} {window}: used fraction {used:.2f}"))
    if not results:
        results.append(("warn", f"{provider}: usage report has no limits; the paid smoke is the probe"))
    return results


def usage_report(provider: str, binary: str) -> dict[str, Any]:
    """Read one provider's usage report; never spends or changes state."""
    try:
        completed = subprocess.run(
            [binary, "usage", "--provider", provider, "--json", "--redact", "--no-extensions"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"error": str(exc)}
    if completed.returncode != 0:
        return {"error": completed.stderr.strip() or f"exit {completed.returncode}"}
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"error": "usage command returned non-JSON output"}
    return value if isinstance(value, dict) else {"error": "usage report is not an object"}


def task_reasons(tasks_dir: Path) -> list[str]:
    """The materialized judge tree must carry every frozen case."""
    reasons: list[str] = []
    files = sorted((tasks_dir / "reviewer-quality").glob("*.yaml"))
    found = []
    for path in files:
        try:
            found.append(str(load_yaml(path).get("task_id")))
        except (OSError, ValueError) as exc:
            reasons.append(f"{path}: {exc}")
    missing = [case for case in REVIEWER_CASES if case not in found]
    extra = [case for case in found if case not in REVIEWER_CASES]
    if missing:
        reasons.append(f"missing task(s): {', '.join(missing)}")
    if extra:
        reasons.append(f"unexpected task(s): {', '.join(extra)}")
    return reasons


def _selftest() -> None:
    """Exercise the pure checks with synthetic inputs; no binary or network."""
    identity = {
        "judge_id": "omp-test",
        "route": "omp",
        "model_requested": "provider/model",
        "settings": {"thinking": "off"},
        "status": "validated",
    }
    record = {
        "met_acceptance_rule": True,
        "judge": {k: v for k, v in identity.items() if k != "status"},
        "labels_sha": "labels",
        "rubric_prompt_sha": "rubric",
        "prompt_version": "v2",
    }
    assert judge_reasons(identity, record, "labels", "rubric", "v2") == []
    stale = dict(record, prompt_version="v1")
    assert any("prompt_version" in reason for reason in judge_reasons(identity, stale, "labels", "rubric", "v2"))
    assert any("labels_sha" in reason for reason in judge_reasons(identity, record, "changed", "rubric", "v2"))

    module = load_judge_module()
    with tempfile.TemporaryDirectory(prefix="preflight-selftest-") as tmp:
        base = Path(tmp)
        labels = {"set_id": "set", "rubric": {"task": "unused", "criterion": 0}, "examples": []}
        (base / "labels.yaml").write_text(yaml.safe_dump(labels), encoding="utf-8")
        set_record = dict(record, set_id="set", labels_sha=module.sha(labels))
        (base / "record.json").write_text(json.dumps(set_record), encoding="utf-8")
        (base / "wrapper.json").write_text(
            json.dumps({"sets": [{"record": "record.json"}]}), encoding="utf-8"
        )
        documents = calibration_documents(base / "wrapper.json")
        assert documents == [set_record]
        path, found = matching_labels(documents[0], module, [base / "labels.yaml"])
        assert path == base / "labels.yaml" and found == labels
        assert matching_labels(record, module, [base / "labels.yaml"]) == (None, None)

    routes = [("provider/priced", "review"), ("provider/unpriced", "review"), ("provider/missing", "parent")]
    cards = {"provider/priced": object()}
    unpriced = {"provider/unpriced": {"unpriced_reason": "subscription"}}
    priced = price_reasons(routes, cards, unpriced)
    assert ("warn", "provider/unpriced is unpriced: subscription") in priced
    assert any(status == "fail" and "provider/missing" in detail for status, detail in priced)

    arms = [
        {
            "experiment_id": "arm-a",
            "path": Path("a.yaml"),
            "parent": "vercel-ai-gateway/openai/parent:low",
            "helper": "vercel-ai-gateway/openai/helper:low",
            "review": "vercel-ai-gateway/zai/reviewer:high",
            "allowed": {
                "vercel-ai-gateway/openai/parent:low": ["openai"],
                "vercel-ai-gateway/openai/helper:low": ["openai"],
                "vercel-ai-gateway/zai/reviewer:high": ["zai"],
            },
            "task": {"maxConcurrency": 1},
            "retry": {flag: False for flag in RETRY_FLAGS},
            "record_reviewer_telemetry": True,
        }
    ]
    assert route_reasons(arms) == []
    broken = dict(
        arms[0],
        allowed={key: list(value) for key, value in arms[0]["allowed"].items()},
    )
    broken["allowed"]["vercel-ai-gateway/zai/reviewer:high"] = ["openai"]
    assert any("restriction" in reason for reason in route_reasons([broken]))
    broken = dict(arms[0], retry={**arms[0]["retry"], "modelFallback": True})
    assert any("retry.modelFallback" in reason for reason in route_reasons([broken]))
    assert any("not unique" in reason for reason in route_reasons([arms[0], dict(arms[0])]))

    assert usage_reasons(
        {"reports": [{"provider": "p", "limits": [{"window": {"id": "5h"}, "amount": {"usedFraction": 1}, "status": "exhausted"}]}]},
        "p",
    ) == [("fail", "p 5h: used fraction 1, status 'exhausted'")]
    assert usage_reasons({"reports": [], "accountsWithoutUsage": [{"provider": "p"}]}, "p")[0][0] == "warn"
    assert usage_reasons(
        {"reports": [{"provider": "p", "limits": [{"window": {"id": "7d"}, "amount": {"usedFraction": 0.95}, "status": "ok"}]}]},
        "p",
    )[0][0] == "warn"


def parser() -> argparse.ArgumentParser:
    """Build the preflight command-line parser."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument(
        "--experiment",
        type=Path,
        action="append",
        default=[],
        help="reviewer experiment YAML; repeat per arm (default: every omp-reviewer arm)",
    )
    p.add_argument("--judge", help="judge id under evals/judges/")
    p.add_argument("--expect-arms", type=int, help="required number of distinct experiments")
    p.add_argument(
        "--tasks-dir",
        type=Path,
        default=ROOT / "evals" / "tasks-judged",
        help="materialized judge task tree",
    )
    p.add_argument("--no-usage", action="store_true", help="skip the live read-only usage probe")
    p.add_argument("--selftest", action="store_true", help="run the offline self-test and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    """Print one line per check and fail the campaign on any failure."""
    args = parser().parse_args(argv)
    if args.selftest:
        try:
            _selftest()
        except AssertionError as exc:
            print(f"error: preflight self-test failed: {exc}", file=sys.stderr)
            return 2
        print("preflight self-tests: ok")
        return 0

    experiments = args.experiment or sorted(
        (ROOT / "evals" / "experiments").glob("omp-reviewer-*.yaml")
    )
    checks: list[dict[str, str]] = []

    binary = shutil.which("omp")
    if binary is None:
        checks.append(check("omp", "fail", "omp is not on PATH", "install omp and rerun `make evals-setup-omp`"))
    else:
        try:
            version = subprocess.run(
                [binary, "--version"], capture_output=True, text=True, timeout=30, check=False
            )
            checks.append(
                check(
                    "omp",
                    "ok" if version.returncode == 0 else "fail",
                    version.stdout.strip() or version.stderr.strip() or f"exit {version.returncode}",
                )
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            checks.append(check("omp", "fail", str(exc)))

    arms: list[dict[str, Any]] = []
    for path in experiments:
        try:
            arms.append(experiment_arm(path))
        except (OSError, ValueError) as exc:
            checks.append(check("routes", "fail", str(exc), "fix the experiment or its overlay"))
    if not arms:
        checks.append(check("routes", "fail", "no reviewer experiments resolved", "name an --experiment"))
    else:
        if args.expect_arms is not None and len(arms) != args.expect_arms:
            checks.append(
                check(
                    "arms",
                    "fail",
                    f"{len(arms)} experiment(s); expected {args.expect_arms}",
                    "name every arm with --experiment",
                )
            )
        else:
            checks.append(check("arms", "ok", f"{len(arms)} experiment(s)"))
        reasons = route_reasons(arms)
        checks.append(
            check(
                "routes",
                "fail" if reasons else "ok",
                "; ".join(reasons) if reasons else f"{len(arms)} matched arm(s)",
                "make every arm share the parent/helper and keep one fixed route per arm",
            )
        )

    providers = sorted(
        {
            model.split("/", 1)[0]
            for arm in arms
            for model in (arm.get("parent"), arm.get("helper"), arm.get("review"))
            if isinstance(model, str) and "/" in model
        }
    )
    for provider in providers:
        if args.no_usage:
            checks.append(check("usage", "warn", f"{provider}: skipped by --no-usage"))
            continue
        report = usage_report(provider, binary or "omp")
        if "error" in report:
            checks.append(
                check("usage", "warn", f"{provider}: {report['error']}; the paid smoke is the probe")
            )
            continue
        for status, detail in usage_reasons(report, provider):
            checks.append(check("usage", status, detail))

    judge = None
    if args.judge:
        try:
            module = load_judge_module()
            judge = module.resolve_judge(args.judge)
            if judge.status != "validated":
                checks.append(
                    check(
                        "judge",
                        "fail",
                        f"{args.judge} status is {judge.status!r}; expected 'validated'",
                        "recalibrate the judge before the campaign",
                    )
                )
            elif not judge.calibration:
                checks.append(check("judge", "fail", f"{args.judge} names no calibration result"))
            else:
                calibration_path = ROOT / "evals" / "judges" / judge.calibration
                documents = calibration_documents(calibration_path)
                candidates = [
                    ROOT / "evals" / "judges" / "calibration" / "labels.yaml",
                    *sorted(
                        (ROOT / "evals" / "fixtures" / "reviewer-quality").glob(
                            "*/labels.yaml"
                        )
                    ),
                ]
                reasons = []
                for record in documents:
                    _, labels = matching_labels(record, module, candidates)
                    if labels is None:
                        reasons.append(
                            f"{record.get('set_id') or 'calibration'}: "
                            "labels_sha matches no committed label set"
                        )
                        continue
                    criterion = module.calibration_criterion(labels, ROOT)
                    reasons.extend(
                        judge_reasons(
                            judge.identity(),
                            record,
                            module.sha(labels),
                            module.sha(criterion.get("prompt", "")),
                            module.PROMPT_VERSION,
                        )
                    )
                checks.append(
                    check(
                        "judge",
                        "fail" if reasons else "ok",
                        "; ".join(reasons)
                        if reasons
                        else f"{args.judge}: {len(documents)} calibration set(s) current",
                        "recalibrate the judge; do not substitute another judge",
                    )
                )
        except Exception as exc:  # any judge input failure is a campaign gate
            checks.append(check("judge", "fail", f"{args.judge}: {exc}", "recalibrate the judge"))
    else:
        checks.append(check("judge", "warn", "no --judge; calibration freshness not checked"))

    routes: dict[str, str] = {}
    for arm in arms:
        for model, role in (
            (arm.get("parent"), "parent"),
            (arm.get("helper"), "helper"),
            (arm.get("review"), "review"),
        ):
            if not isinstance(model, str):
                continue
            if routes.get(model) != "review":
                routes[model] = role
            if role == "review":
                routes[model] = "review"
    if judge is not None:
        routes[judge.model] = "judge"
    try:
        pricing = load_pricing_module()
        cards = pricing.load_prices(ROOT / "evals" / "coder-eval-omp" / "prices.json")
        manifest = load_yaml(ROOT / "evals" / "prices.yaml").get("models") or {}
        for status, detail in price_reasons(list(routes.items()), cards, manifest):
            checks.append(
                check(
                    "prices",
                    status,
                    detail,
                    "add a sourced card or an explicit unpriced_reason; never guess a rate",
                )
            )
    except (OSError, ValueError) as exc:
        checks.append(check("prices", "fail", str(exc), "fix the price tables"))

    reasons = task_reasons(args.tasks_dir)
    checks.append(
        check(
            "tasks",
            "fail" if reasons else "ok",
            "; ".join(reasons) if reasons else f"{len(REVIEWER_CASES)} cases materialized",
            "run `make evals-judge-preflight JUDGE=<id>` (free)",
        )
    )

    for entry in checks:
        print(f"{entry['status']:<4} {entry['name']}: {entry['detail']}")
        if entry["remedy"] and entry["status"] == "fail":
            print(f"      remedy: {entry['remedy']}")
    failures = sum(entry["status"] == "fail" for entry in checks)
    warnings = sum(entry["status"] == "warn" for entry in checks)
    print(f"verdict: {'FAIL' if failures else 'PASS'} ({failures} fail, {warnings} warn)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
