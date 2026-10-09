#!/usr/bin/env python3
"""Mine per-model rework from `undertake`'s claim and readiness comments.

`undertake` posts a claim comment on a task issue with a `Model:`/`session:`
provenance line pair, and a `First-readiness report` comment on the pull
request that closes it, carrying elapsed time and `provenance`'s
`Model:`/`Harness:`/`session:` block. `review-cycle` posts `Review
verification` comments on the same pull request with `pass:`, `findings:`
and `outcome:` lines. Together these are the only production evidence of how
a model performed on real work -- not a benchmark score, but what it actually
cost to land.

This script walks a repository's merged pull requests, keeps the ones that
closed a task issue or bug issue (`Closes #N` in the body, `task` or `bug`
label on #N), parses the comments above plus the check-runs list on the pull
request's head SHA, and writes one JSON record per pull request under
`evals/provenance/production/<owner>/<repo>/<pr>.json`. `render_table` then folds
every repository's records into the per-model table in
`evals/provenance/production/README.md`.

USAGE

    python3 scripts/model-telemetry.py jmcvetta/daily-driver
    python3 scripts/model-telemetry.py jmcvetta/career --since 2026-08-01
    python3 scripts/model-telemetry.py jmcvetta/daily-driver --refresh

Needs `GITHUB_TOKEN` or `GH_TOKEN` for the REST API. No third-party import --
the REST client is `urllib`, the same choice `scripts/evals-cases-from-prs.py`
makes and for the same reason: nothing here needs the dev venv.

WHY PULL REQUESTS ARE THE WALK, NOT ISSUES

The task as described walks "closed issues labelled task or bug" and follows
each to its closing pull request. REST v3 exposes no such link -- only
GraphQL returns an issue's closing pull requests, and this script is
REST-only by design (see above). `scripts/evals-cases-from-prs.py` already
solved the same problem in the other direction: walk merged pull requests,
and read `Closes #N` out of each one's own body (a line `undertake`'s `pr`
step always writes). This script reuses that direction and that regex.

FIXTURE GROUNDING

The comment shapes below are read from real, current comments on this
repository -- issue #414's claim comment (pre-`provenance`-skill shape) and
pull request #418's claim, `Review verification`, and `First-readiness
report` comments (post-`provenance`-skill shape) -- rather than from the
task issue's own prose, which predates pull request #418 and describes an
older readiness-report shape (`Claimed`/`Ready`/`Elapsed`/`Model`/`Harness`/
`Session`/`Head` as separate lines) that no longer matches what `undertake`
actually posts. Both the old claim shape (`Model:`/`session:` with no
`Harness:` line or leading `---`) and the new one parse, because a repository
walked with `--since` unset sees both eras.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PRODUCTION_DIR = ROOT / "evals" / "provenance" / "production"
README_PATH = PRODUCTION_DIR / "README.md"

API_ROOT = "https://api.github.com"


class TelemetryError(Exception):
    """A GitHub call that never succeeded, or a bad CLI argument."""


# ---------------------------------------------------------------------------
# Comment grammars -- pure functions, each exercised offline by
# `scripts/check-model-telemetry.py` against fixture text.
# ---------------------------------------------------------------------------

# `Model: ...` then optionally `Harness: ...` then `session: ...`, each on its
# own line. The `Harness:` line is optional so this one pattern parses both
# the pre-`provenance`-skill claim shape (`Model:`/`session:` only) and the
# current one (`provenance`'s block, with `Harness:` between them and a
# leading `---` this pattern does not require -- it is found wherever it
# falls, the way `skills/provenance/SKILL.md` says the claim lookup must).
_PROVENANCE_RE = re.compile(
    r"^Model: ?(?P<model>\S.*)$\n(?:^Harness: ?(?P<harness>\S.*)$\n)?^session: ?(?P<session>\S.*)$",
    re.MULTILINE,
)
# A standalone fallback for `harness:` lines that fall outside the `Model:`/
# `Harness:`/`session:` sequence above -- the oldest readiness-report shape
# (PR #405's own, pre-dating even the pre-`provenance`-skill claim shape)
# writes `Model:`, then `session:`, then a trailing lowercase `harness:` line.
_HARNESS_LINE_RE = re.compile(r"^harness: ?(?P<harness>\S.*)$", re.MULTILINE | re.IGNORECASE)


def parse_provenance_block(body: str) -> dict[str, str | None] | None:
    """The `model`, `harness` (or None) and `session` a `Model:`/`session:`
    pair names, or None where the text carries no such pair.
    """
    match = _PROVENANCE_RE.search(body)
    if not match:
        return None
    fields = match.groupdict()
    harness = fields["harness"].strip() if fields["harness"] else None
    if harness is None:
        stray = _HARNESS_LINE_RE.search(body)
        harness = stray.group("harness").strip() if stray else None
    return {
        "model": fields["model"].strip(),
        "harness": harness,
        "session": fields["session"].strip(),
    }


def find_claim_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The earliest issue comment shaped like `undertake`'s claim: a `Branch:`
    line and a parseable provenance pair. Earliest, not first-found, because
    a claim collision (`SKILL.md`'s `Claim the issue`) leaves more than one
    and the earliest is the one whose clock is running.
    """
    candidates = [
        c
        for c in comments
        if "Branch:" in str(c.get("body") or "")
        and parse_provenance_block(str(c.get("body") or ""))
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: str(c.get("created_at") or ""))


_READINESS_MARKER = "First-readiness report"
# Current shape: "Elapsed: ..., from claim (T1) to first merge readiness (T2)."
_READINESS_TIMES_RE = re.compile(
    r"from claim \((?P<claimed>[^)]+)\) to first merge readiness \((?P<ready>[^)]+)\)"
)
# Pre-`provenance`-skill shape: separate "start: T1" / "ready: T2" lines
# (PR #405's own First-readiness report reads this way).
_START_READY_RE = re.compile(
    r"^start: ?(?P<claimed>\S.*)$\n^ready: ?(?P<ready>\S.*)$",
    re.MULTILINE | re.IGNORECASE,
)
# Case-insensitive: the current shape writes "Head:", the older one "head:".
_HEAD_RE = re.compile(r"^head: ?(?P<sha>[0-9a-f]{7,40})$", re.MULTILINE | re.IGNORECASE)


def _parse_iso(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def find_readiness_report(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The pull request's `First-readiness report` comment, or None."""
    for comment in comments:
        body = str(comment.get("body") or "")
        if body.lstrip().startswith(_READINESS_MARKER):
            return comment
    return None


def parse_readiness_report(body: str) -> dict[str, Any]:
    """Elapsed minutes (from the two ISO timestamps the report names -- more
    exact than parsing the prose duration between them), the claimed and
    ready timestamps, the head SHA, and the provenance pair.

    `elapsed_minutes`, `claimed_at` and `ready_at` are None where the report
    names no recoverable start -- `SKILL.md`'s "reports the timing as
    unavailable rather than inventing one".
    """
    elapsed_minutes: float | None = None
    claimed_at: str | None = None
    ready_at: str | None = None
    times = _READINESS_TIMES_RE.search(body) or _START_READY_RE.search(body)
    if times:
        claimed_dt = _parse_iso(times.group("claimed"))
        ready_dt = _parse_iso(times.group("ready"))
        if claimed_dt and ready_dt:
            claimed_at = times.group("claimed")
            ready_at = times.group("ready")
            elapsed_minutes = round((ready_dt - claimed_dt).total_seconds() / 60, 2)

    head_match = _HEAD_RE.search(body)
    provenance = parse_provenance_block(body) or {"model": None, "harness": None, "session": None}

    return {
        "model": provenance["model"],
        "harness": provenance["harness"],
        "session": provenance["session"],
        "claimed_at": claimed_at,
        "ready_at": ready_at,
        "elapsed_minutes": elapsed_minutes,
        "head_sha": head_match.group("sha") if head_match else None,
    }


_REVIEW_VERIFICATION_MARKER = "Review verification"
_PASS_RE = re.compile(r"^pass: (?P<n>\d+)$", re.MULTILINE)
_FINDINGS_LINE_RE = re.compile(r"^findings: (?P<value>.+)$", re.MULTILINE)
_OUTCOME_RE = re.compile(r"^outcome: (?P<value>.+)$", re.MULTILINE)


def parse_review_verification(body: str) -> dict[str, Any] | None:
    """One `Review verification` comment's `pass` number, `outcome`, and the
    count of its `findings:` lines -- a comment carrying `findings: none`
    counts zero, since that line records the absence of a finding rather than
    one named `none`.
    """
    if not body.lstrip().startswith(_REVIEW_VERIFICATION_MARKER):
        return None
    pass_match = _PASS_RE.search(body)
    outcome_match = _OUTCOME_RE.search(body)
    findings = [
        m.group("value").strip()
        for m in _FINDINGS_LINE_RE.finditer(body)
        if m.group("value").strip().lower() != "none"
    ]
    return {
        "pass": int(pass_match.group("n")) if pass_match else None,
        "outcome": outcome_match.group("value").strip() if outcome_match else None,
        "findings_count": len(findings),
    }


def parse_review_verifications(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every `Review verification` comment on the pull request, in order."""
    parsed = []
    for comment in comments:
        record = parse_review_verification(str(comment.get("body") or ""))
        if record is not None:
            parsed.append(record)
    return parsed


def count_check_reruns(check_runs: list[dict[str, Any]]) -> int:
    """Reruns on the head SHA: for each check-run name that appears more than
    once, every extra occurrence past the first is a rerun.
    """
    counts: dict[str, int] = {}
    for run in check_runs:
        name = str(run.get("name") or "")
        counts[name] = counts.get(name, 0) + 1
    return sum(count - 1 for count in counts.values() if count > 1)


_MODEL_CLASS_RE = re.compile(
    r"^##\s*Model class\s*$\s*`?(mechanical|implementation|reasoning|frontier)`?(?![\w-])",
    re.IGNORECASE | re.MULTILINE,
)


def read_model_class(issue_body: str | None) -> str:
    """The `## Model class` token from an issue body, or `unlabelled`.
    Same grammar `scripts/evals-cases-from-prs.py` reads, duplicated rather
    than imported -- every `check-*.py` and mining script in this repository
    is standalone, and the regex stays local.
    """
    if not issue_body:
        return "unlabelled"
    match = _MODEL_CLASS_RE.search(issue_body)
    return match.group(1).lower() if match else "unlabelled"


_CLOSES_RE = re.compile(
    r"\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s*:?\s*#(\d+)",
    re.IGNORECASE,
)


def closed_issue_number(pr_body: str | None) -> int | None:
    """The issue number a `Closes #N` / `Fixes #N` / `Resolves #N` line in the
    pull request body names, or None. Same grammar
    `scripts/evals-cases-from-prs.py` reads.
    """
    if not pr_body:
        return None
    match = _CLOSES_RE.search(pr_body)
    return int(match.group(1)) if match else None


def is_model_mismatch(claim_model: str | None, report_model: str | None) -> bool:
    """Whether the claim comment and the readiness report name two different,
    actually-reported models. A pull request with a claim but no readiness
    report has nothing for the claim to disagree with -- `report_model` is
    None there, never the `"unreported"` placeholder `build_record` displays.
    """
    return bool(claim_model and report_model and claim_model != report_model)


# ---------------------------------------------------------------------------
# GitHub REST client -- urllib only, the same shape as
# `scripts/evals-cases-from-prs.py`'s.
# ---------------------------------------------------------------------------


def _request(url: str, token: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - github REST API
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise TelemetryError(f"GET {url} -> {exc.code}: {detail[:300]}") from exc


def _paginated(url_template: str, token: str, max_pages: int = 50) -> list[Any]:
    items: list[Any] = []
    for page_number in range(1, max_pages + 1):
        page = _request(f"{url_template}&page={page_number}", token)
        if not isinstance(page, list):
            raise TelemetryError(f"expected a list from {url_template}, got {type(page).__name__}")
        items.extend(page)
        if len(page) < 100:
            break
    return items


def list_merged_pulls(owner: str, repo: str, token: str, max_pulls: int) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{owner}/{repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc"
    max_pages = (max_pulls + 99) // 100
    return _paginated(url, token, max_pages=max_pages)[:max_pulls]


def get_pr_files(owner: str, repo: str, number: int, token: str) -> list[dict[str, Any]]:
    return _paginated(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{number}/files?per_page=100", token)


def get_issue(owner: str, repo: str, number: int, token: str) -> dict[str, Any] | None:
    try:
        return _request(f"{API_ROOT}/repos/{owner}/{repo}/issues/{number}", token)
    except TelemetryError as exc:
        if "-> 404" in str(exc):
            return None
        raise


def get_issue_comments(owner: str, repo: str, number: int, token: str) -> list[dict[str, Any]]:
    return _paginated(f"{API_ROOT}/repos/{owner}/{repo}/issues/{number}/comments?per_page=100", token)


def get_check_runs(owner: str, repo: str, sha: str, token: str) -> list[dict[str, Any]]:
    document = _request(f"{API_ROOT}/repos/{owner}/{repo}/commits/{sha}/check-runs?per_page=100", token)
    runs = document.get("check_runs", []) if isinstance(document, dict) else []
    return runs


# ---------------------------------------------------------------------------
# The walk.
# ---------------------------------------------------------------------------


def build_record(
    owner: str,
    repo: str,
    token: str,
    pr: dict[str, Any],
    issue: dict[str, Any],
) -> dict[str, Any]:
    """One pull request's telemetry record. `pr` and `issue` are the raw
    REST documents for the pull request (from the merged-pulls list -- it
    already carries `merged_at`, `head`, `base` and `body`) and the task or
    bug issue it closes.
    """
    number = pr["number"]
    files = get_pr_files(owner, repo, number, token)
    additions = sum(int(f.get("additions") or 0) for f in files)
    deletions = sum(int(f.get("deletions") or 0) for f in files)

    pr_comments = get_issue_comments(owner, repo, number, token)
    issue_comments = get_issue_comments(owner, repo, issue["number"], token)

    claim = find_claim_comment(issue_comments)
    claim_provenance = parse_provenance_block(str(claim.get("body") or "")) if claim else None

    readiness_comment = find_readiness_report(pr_comments)
    readiness = parse_readiness_report(str(readiness_comment.get("body") or "")) if readiness_comment else None

    verifications = parse_review_verifications(pr_comments)

    head_sha = str((pr.get("head") or {}).get("sha") or "")
    check_runs = get_check_runs(owner, repo, head_sha, token) if head_sha else []

    report_model = readiness["model"] if readiness else None
    model = report_model or "unreported"
    claim_model = claim_provenance["model"] if claim_provenance else None

    return {
        "repo": f"{owner}/{repo}",
        "issue": issue["number"],
        "pull_request": number,
        "model": model,
        "claim_model": claim_model,
        "model_mismatch": is_model_mismatch(claim_model, report_model),
        "harness": readiness["harness"] if readiness else None,
        "session": readiness["session"] if readiness else None,
        "claimed_at": readiness["claimed_at"] if readiness else None,
        "ready_at": readiness["ready_at"] if readiness else None,
        "elapsed_minutes": readiness["elapsed_minutes"] if readiness else None,
        "review_passes": len(verifications),
        "findings_count": sum(v["findings_count"] for v in verifications),
        "check_reruns": count_check_reruns(check_runs),
        "merged_at": pr.get("merged_at"),
        "additions": additions,
        "deletions": deletions,
        "changed_files": len(files),
        "model_class": read_model_class(issue.get("body")),
    }


def scan_repository(
    owner: str,
    repo: str,
    token: str,
    since: datetime | None,
    max_pulls: int,
    refresh: bool,
) -> list[Path]:
    """Write a record for every merged pull request that closed a `task` or
    `bug` issue, since `since` if given. Idempotent: a record already on disk
    for a merged pull request is left alone unless `refresh` is set. Returns
    the paths written.
    """
    repo_dir = PRODUCTION_DIR / owner / repo
    written: list[Path] = []

    for pr in list_merged_pulls(owner, repo, token, max_pulls):
        merged_at = pr.get("merged_at")
        if not merged_at:
            continue
        if since is not None:
            merged_dt = _parse_iso(merged_at)
            if merged_dt is None or merged_dt < since:
                continue

        out_path = repo_dir / f"{pr['number']}.json"
        if out_path.exists() and not refresh:
            continue

        issue_number = closed_issue_number(pr.get("body"))
        if issue_number is None:
            continue
        issue = get_issue(owner, repo, issue_number, token)
        if issue is None:
            continue
        labels = {label.get("name") for label in issue.get("labels", []) if isinstance(label, dict)}
        if not labels & {"task", "bug"}:
            continue

        record = build_record(owner, repo, token, pr, issue)
        repo_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(out_path)

    return written


# ---------------------------------------------------------------------------
# The renderer.
# ---------------------------------------------------------------------------


def load_all_records() -> list[dict[str, Any]]:
    """Every pull-request record on disk, across every repository directory
    under `evals/provenance/production/`, in path order.
    """
    if not PRODUCTION_DIR.exists():
        return []
    records = []
    for path in sorted(PRODUCTION_DIR.glob("*/*/*.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    return records


def render_table(records: list[dict[str, Any]]) -> str:
    """Markdown table, one row per model: count, median elapsed minutes,
    median review passes, findings per pull request, and rerun rate. Medians,
    not means -- a single very long undertaking should not move every other
    model's row.
    """
    by_model: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_model.setdefault(record["model"], []).append(record)

    lines = [
        "| Model | PRs | Median elapsed | Median review passes | Findings/PR | Rerun rate |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for model in sorted(by_model):
        rows = by_model[model]
        elapsed = [r["elapsed_minutes"] for r in rows if r["elapsed_minutes"] is not None]
        median_elapsed = f"{statistics.median(elapsed):.0f} min" if elapsed else "n/a"
        median_passes = statistics.median(r["review_passes"] for r in rows)
        findings_per_pr = sum(r["findings_count"] for r in rows) / len(rows)
        rerun_rate = sum(1 for r in rows if r["check_reruns"] > 0) / len(rows)
        lines.append(
            f"| {model} | {len(rows)} | {median_elapsed} | {median_passes:g} | "
            f"{findings_per_pr:.1f} | {rerun_rate:.0%} |"
        )
    return "\n".join(lines) + "\n"


def write_readme(records: list[dict[str, Any]]) -> None:
    """Render `evals/provenance/production/README.md` from `records`."""
    table = render_table(records)
    repos = sorted({r["repo"] for r in records})
    body = (
        "# Production provenance\n\n"
        "Per-model rework mined from `undertake`'s claim and first-readiness "
        "comments and `review-cycle`'s `Review verification` comments, by "
        "`scripts/model-telemetry.py`. Each pull request under a repository "
        "directory here is one JSON record; this table is `render_table` over "
        "every record present.\n\n"
        "Refresh a repository with `make model-telemetry REPO=owner/repo`, or "
        "`python3 scripts/model-telemetry.py owner/repo --refresh` to re-fetch "
        "records already on disk.\n\n"
        f"Sources: {', '.join(repos) if repos else 'none yet'}.\n\n"
        f"{table}"
    )
    PRODUCTION_DIR.mkdir(parents=True, exist_ok=True)
    README_PATH.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", help="owner/repo to scan for merged pull requests")
    parser.add_argument("--since", default=None, help="only pull requests merged on or after this ISO date")
    parser.add_argument("--refresh", action="store_true", help="re-fetch records already on disk")
    parser.add_argument("--max-pulls", type=int, default=200, help="most recently updated merged PRs to scan")
    args = parser.parse_args(argv)

    owner, _, repo = args.repo.partition("/")
    if not repo:
        parser.error("repo must be 'owner/repo'")

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise TelemetryError("GITHUB_TOKEN or GH_TOKEN must be set")

    since = None
    if args.since:
        since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    written = scan_repository(owner, repo, token, since, args.max_pulls, args.refresh)
    print(f"{args.repo}: {len(written)} record(s) written")

    write_readme(load_all_records())
    print(f"wrote {README_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except TelemetryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
