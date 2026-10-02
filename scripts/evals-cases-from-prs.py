#!/usr/bin/env python3
"""Build `model-classes` eval cases from a repository's own merged pull requests.

A pull request that closed a task issue and shipped tests for its own change
is a fixture nobody has to author: the base SHA is the "before", the merge SHA
is the "after", and the PR's own diff to its test files is the answer key. This
script walks a repository's merged pull requests, keeps the ones that qualify
(see `qualifying_reason`), and for the ones selected into the suite emits a
reference directory under `evals/fixtures/model-classes/cases/<repo>-<pr>/`
(a `tests.patch` restricted to the PR's test files, and the two manifests the
deletion and skip checks read) plus a task YAML under
`evals/tasks/model-classes/`. The task's prompt carries the closed issue's
title and body, so the agent has no reason to look the work up on GitHub.
Every qualifying pull request the builder saw, selected or not, is recorded in
`evals/fixtures/model-classes/candidates.json`.

USAGE

    Scan a repository and append its qualifying pull requests to the
    candidates file (run once per source; the file accumulates):

        python3 scripts/evals-cases-from-prs.py jmcvetta/career
        python3 scripts/evals-cases-from-prs.py Green-Pagoda/pagoda \\
            --path-prefix apps/usd2oz-web

    Then build the suite -- run the build-time answer-key check on the
    smallest qualifying candidates of each class and emit fixtures + task
    YAMLs for the ones that pass it, up to `--per-class` each:

        python3 scripts/evals-cases-from-prs.py --select

    Rewrite every selected case's task YAML from `candidates.json` -- after a
    change to the template or the prompt -- without re-running the build-time
    check:

        python3 scripts/evals-cases-from-prs.py --rewrite-tasks

    An `unlabelled` candidate (no `Model class` on the issue it closed) needs
    a class before it can be selected:

        python3 scripts/evals-cases-from-prs.py --select \\
            --class-override jmcvetta/career#511=implementation

    Historical issue metadata uses `standard` and `advanced`; explicitly map
    those to `implementation` and `reasoning` with `--class-override` when
    mining old pull requests. Overrides accept only buildable `mechanical` or
    `implementation`; old names are not canonical input.

Needs `GITHUB_TOKEN` or `GH_TOKEN` for the REST API, `git`, and whatever the
resolved test command needs (`uv`, `pnpm`) already on PATH. No third-party
import: the REST client is `urllib`, and the task YAML is written as a string
template rather than through PyYAML, so nothing here needs the dev venv.

SELF-TESTS

    Every invocation runs `_run_self_tests()` first, offline, against inline
    JSON-shaped fixtures modelled on the GitHub REST responses this script
    reads: the qualifying filter, the test-file split, the class token read,
    the elapsed read, `task_timeout` derivation, and rejection reasons. See
    `check-eval-arms.py` for the precedent -- a check that cannot fail is a
    check that passes for ever, silently, so each assertion here pairs with a
    case that must fail it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = ROOT / "evals" / "fixtures" / "model-classes"
CASES_DIR = FIXTURES_DIR / "cases"
TASKS_DIR = ROOT / "evals" / "tasks" / "model-classes"
# The grader every case runs, and the one the build-time answer-key check runs.
_GRADER = FIXTURES_DIR / "shared" / "apply-tests.sh"
DEFAULT_CANDIDATES_FILE = FIXTURES_DIR / "candidates.json"

API_ROOT = "https://api.github.com"

# Classes this suite ever builds a case for. `reasoning` is out of scope by
# design -- the class is decided by the production table and public benchmarks,
# not by a fixture small enough to grade in two minutes.
BUILDABLE_CLASSES = ("mechanical", "implementation")


class BuildError(Exception):
    """Something the builder cannot recover from -- a bad CLI argument, a
    missing credential, a GitHub API call that never succeeded."""


# ---------------------------------------------------------------------------
# Pure functions: the qualifying filter, the test-file split, the class and
# elapsed reads, and the timeout derivation. Every one of these is exercised
# offline by `_run_self_tests()`.
# ---------------------------------------------------------------------------


def is_test_path(path: str) -> bool:
    """Whether `path` is a test file, by this repository's own conventions:
    anything under a `tests/` directory, `test_*`, `*_test.*`, or `*.test.*`.
    """
    parts = path.split("/")
    if "tests" in parts[:-1]:
        return True
    basename = parts[-1]
    if basename.startswith("test_"):
        return True
    stem, dot, ext = basename.rpartition(".")
    if dot and stem.endswith("_test"):
        return True
    if ".test." in basename:
        return True
    return False


def split_test_files(files: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Split a PR's changed files into (test_files, non_test_files), by path."""
    test_files: list[str] = []
    non_test_files: list[str] = []
    for entry in files:
        name = str(entry["filename"])
        (test_files if is_test_path(name) else non_test_files).append(name)
    return test_files, non_test_files


def kept_test_files(files: list[dict[str, Any]]) -> list[str]:
    """The changed test files that still exist after the diff -- excludes a
    test file the PR deleted, which is not an answer key to apply, it is one
    fewer file for `tests.patch` to find at the merge SHA.
    """
    test_files, _ = split_test_files(files)
    test_file_set = set(test_files)
    return [
        str(f["filename"])
        for f in files
        if str(f["filename"]) in test_file_set and f.get("status") != "removed"
    ]


_CLOSES_RE = re.compile(
    r"\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s*:?\s*#(\d+)",
    re.IGNORECASE,
)


def closed_issue_number(pr_body: str | None) -> int | None:
    """The issue number a `Closes #N` / `Fixes #N` / `Resolves #N` line in the
    pull request body names, or None. First match wins; a PR closing more than
    one issue names the one whose `Model class` this builder reads.
    """
    if not pr_body:
        return None
    match = _CLOSES_RE.search(pr_body)
    return int(match.group(1)) if match else None


def qualifying_reason(
    pr: dict[str, Any],
    files: list[dict[str, Any]],
    default_branch: str,
    path_prefix: str | None,
) -> str | None:
    """None when `pr` qualifies for the suite; otherwise the reason it does not.

    Qualification: merged, based on the repository's default branch, every
    changed file inside `path_prefix` where one is given, at least one non-test
    source file changed, at least one test file changed, and the body closes
    an issue.
    """
    if not pr.get("merged_at"):
        return "not merged"

    base_ref = (pr.get("base") or {}).get("ref")
    if base_ref != default_branch:
        return f"base is {base_ref!r}, not the default branch {default_branch!r}"

    if path_prefix:
        prefix = path_prefix.rstrip("/") + "/"
        outside = [f["filename"] for f in files if not str(f["filename"]).startswith(prefix)]
        if outside:
            return f"touches {len(outside)} file(s) outside path prefix {path_prefix!r}"

    test_files, non_test_files = split_test_files(files)
    if not non_test_files:
        return "touches only test files, no source change"
    if not test_files:
        return "touches no test file"

    if not kept_test_files(files):
        return "every test file the diff touches was removed, so there is no answer key to apply"

    if closed_issue_number(pr.get("body")) is None:
        return "body names no `Closes #N` / `Fixes #N` / `Resolves #N` issue"

    return None


_MODEL_CLASS_RE = re.compile(
    r"^##\s*Model class\s*$\s*`?(mechanical|implementation|reasoning)`?(?![\w-])",
    re.IGNORECASE | re.MULTILINE,
)


def read_model_class(issue_body: str | None) -> str:
    """The `## Model class` token from a task issue's body, or `unlabelled`."""
    if not issue_body:
        return "unlabelled"
    match = _MODEL_CLASS_RE.search(issue_body)
    return match.group(1).lower() if match else "unlabelled"


_READINESS_MARKER = "First-readiness report"
_HOUR_MINUTE_RE = re.compile(r"(\d+)\s*hours?\D{0,12}?(\d+)\s*minutes?", re.IGNORECASE)
_MINUTE_ONLY_RE = re.compile(r"(\d+)\s*minutes?", re.IGNORECASE)


def read_elapsed_minutes(comments: list[dict[str, Any]]) -> int | None:
    """The elapsed minutes from the PR's `First-readiness report` comment, or
    None where there is no such comment or it names no readable duration.
    Two formats are in the wild (`elapsed wall time: H hours M minutes` and
    `Timing: ... (H hour and M minutes)`); the first match of either wins.

    Scoped to lines containing "elapsed" or "timing" rather than searched
    against the whole comment body: an unrelated duration mentioned earlier
    in the same comment (a flaky-CI aside, a retry count) would otherwise be
    the first hour/minute match `re.search` finds.
    """
    for comment in comments:
        body = str(comment.get("body") or "")
        if not body.lstrip().startswith(_READINESS_MARKER):
            continue
        for line in body.splitlines():
            lowered = line.lower()
            if "elapsed" not in lowered and "timing" not in lowered:
                continue
            hour_minute = _HOUR_MINUTE_RE.search(line)
            if hour_minute:
                return int(hour_minute.group(1)) * 60 + int(hour_minute.group(2))
            minute_only = _MINUTE_ONLY_RE.search(line)
            if minute_only:
                return int(minute_only.group(1))
        return None
    return None


def derive_task_timeout(elapsed_minutes: int | None) -> int:
    """Twice the recorded human elapsed minutes, floored at 300s and capped at
    780s; 780s where there is no recorded elapsed time.
    """
    if elapsed_minutes is None:
        return 780
    seconds = elapsed_minutes * 60 * 2
    return max(300, min(780, seconds))


def parse_class_override(raw: str) -> tuple[str, str]:
    """Parse a `--class-override owner/repo#N=token` argument."""
    slug, sep, token = raw.partition("=")
    if not sep or token.lower() not in BUILDABLE_CLASSES:
        raise BuildError(
            f"--class-override {raw!r} must be 'owner/repo#N=mechanical' or "
            "'owner/repo#N=implementation'"
        )
    return slug, token.lower()


def resolve_test_command(
    repo_slug: str, test_files: list[str], package: tuple[str, str] | None
) -> str | None:
    """The repository's own test command for the packages `test_files` touch,
    or None where this builder does not know one.

    `.test.ts`/`.test.tsx` files run through `pnpm --filter <package_name>
    exec vitest run`, the same in any repository on a pnpm workspace --
    `package_name` is read from the touched package's `package.json` at
    build time, and its absence is what makes this branch repo-agnostic
    rather than a guess. A shallow single-commit checkout has no
    `node_modules`, so the command installs first, scoped to the touched
    package and its dependencies (`--filter '<name>...'`) rather than the
    whole workspace -- measured against a real pagoda checkout, that is the
    difference between a 3s install and a 70s one that also chases an
    unrelated package's external asset fetch.

    `jmcvetta/career` additionally knows plain pytest for `.py` files, in the
    two shapes its own Makefile actually runs them: `kokoro/`-scoped tests run
    from `kokoro/` (`test-python-kokoro-pytest`), and every other Python test
    at the repository root has no root `pyproject.toml` to run against, so it
    borrows the `viewer/` package's venv the same way `test-python-infra` and
    `test-python-boundary` do (`cd viewer && uv run pytest ../<path>`).

    A repository this builder has not been taught, or a case whose test
    files mix kinds it cannot run with one command, resolves to None -- a
    rejection reason for the caller, not a guess.
    """
    if not test_files:
        return None

    if package and all(f.endswith((".test.ts", ".test.tsx")) for f in test_files):
        package_name, package_dir = package
        prefix = f"{package_dir}/" if package_dir else ""
        if not all(f.startswith(prefix) for f in test_files):
            return None
        relative = [f[len(prefix) :] for f in test_files]
        quoted = " ".join(shlex.quote(r) for r in relative)
        install = f"pnpm install --frozen-lockfile --filter {shlex.quote(package_name + '...')}"
        run = f"pnpm --filter {shlex.quote(package_name)} exec vitest run {quoted}"
        return f"{install} && {run}"

    if repo_slug == "jmcvetta/career" and all(f.endswith(".py") for f in test_files):
        if all(f.startswith("kokoro/") for f in test_files):
            rel = [f[len("kokoro/") :] for f in test_files]
            quoted = " ".join(shlex.quote(r) for r in rel)
            return f"cd kokoro && uv run pytest {quoted}"
        if not any(f.startswith("kokoro/") for f in test_files):
            quoted = " ".join(shlex.quote(f"../{f}") for f in test_files)
            return f"cd viewer && uv run pytest {quoted}"
        return None

    return None


# ---------------------------------------------------------------------------
# GitHub REST client -- urllib only.
# ---------------------------------------------------------------------------


def _request(url: str, token: str, accept: str = "application/vnd.github+json") -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - github REST API
            body = response.read()
            link_header = response.headers.get("Link", "")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise BuildError(f"GET {url} -> {exc.code}: {detail[:300]}") from exc
    if accept == "application/vnd.github+json":
        return json.loads(body), link_header
    return body.decode("utf-8"), link_header


def _paginated(url_template: str, token: str, max_pages: int = 50) -> list[Any]:
    """GET every page of `url_template` (which must already carry `per_page`
    and end with a query string, e.g. `...?per_page=100`), by appending
    `&page=N` ourselves rather than following the response's `Link` header.

    GitHub's `Link` header sometimes names the `repositories/{id}/...` path
    form instead of `repos/{owner}/{repo}/...`, and this environment's proxy
    refuses the numeric form outright -- so trusting it breaks pagination
    entirely on some repositories. Every page we ask for is built from the
    same owner/repo URL that worked for page one.
    """
    items: list[Any] = []
    for page_number in range(1, max_pages + 1):
        page, _ = _request(f"{url_template}&page={page_number}", token)
        if not isinstance(page, list):
            raise BuildError(f"expected a list from {url_template}, got {type(page).__name__}")
        items.extend(page)
        if len(page) < 100:
            break
    return items


def get_default_branch(owner: str, repo: str, token: str) -> str:
    document, _ = _request(f"{API_ROOT}/repos/{owner}/{repo}", token)
    branch = document.get("default_branch")
    if not isinstance(branch, str) or not branch:
        raise BuildError(f"{owner}/{repo} reports no default_branch")
    return branch


def list_merged_pulls(owner: str, repo: str, token: str, max_pulls: int) -> list[dict[str, Any]]:
    url = f"{API_ROOT}/repos/{owner}/{repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc"
    max_pages = (max_pulls + 99) // 100
    pulls = _paginated(url, token, max_pages=max_pages)
    return pulls[:max_pulls]


def get_pr_files(owner: str, repo: str, number: int, token: str) -> list[dict[str, Any]]:
    return _paginated(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{number}/files?per_page=100", token)


def get_pr_diff(owner: str, repo: str, number: int, token: str) -> str:
    text, _ = _request(
        f"{API_ROOT}/repos/{owner}/{repo}/pulls/{number}",
        token,
        accept="application/vnd.github.v3.diff",
    )
    return text


def get_issue_comments(owner: str, repo: str, number: int, token: str) -> list[dict[str, Any]]:
    return _paginated(f"{API_ROOT}/repos/{owner}/{repo}/issues/{number}/comments?per_page=100", token)


def get_issue(owner: str, repo: str, number: int, token: str) -> dict[str, Any] | None:
    try:
        document, _ = _request(f"{API_ROOT}/repos/{owner}/{repo}/issues/{number}", token)
    except BuildError as exc:
        if "-> 404" in str(exc):
            return None
        raise
    return document


def get_file_contents(owner: str, repo: str, path: str, ref: str, token: str) -> str | None:
    """Decoded UTF-8 content of a file at `ref`, or None on a 404."""
    import base64

    url = f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    try:
        document, _ = _request(url, token)
    except BuildError as exc:
        if "-> 404" in str(exc):
            return None
        raise
    content = document.get("content")
    if not isinstance(content, str):
        return None
    return base64.b64decode(content).decode("utf-8", "replace")


def package_for_path(owner: str, repo: str, file_path: str, ref: str, token: str) -> tuple[str, str] | None:
    """The (name, directory) of the nearest `package.json` above `file_path`,
    or None. `directory` is repo-root-relative ("" for the workspace root)
    and is what a test file's path must be made relative to before handing it
    to `pnpm --filter <name> exec vitest run`: vitest resolves its arguments
    against the filtered package's own directory, not the repo root, so a
    root-relative path under a nested package silently matches nothing.

    Walks up from `file_path`'s directory rather than trusting a
    character-wise common prefix over several file paths, which can stop
    mid-component.
    """
    directory = file_path.rsplit("/", 1)[0] if "/" in file_path else ""
    for _ in range(6):
        text = get_file_contents(owner, repo, f"{directory}/package.json" if directory else "package.json", ref, token)
        if text is not None:
            try:
                document = json.loads(text)
            except json.JSONDecodeError:
                return None
            name = document.get("name")
            return (name, directory) if isinstance(name, str) else None
        if not directory:
            return None
        directory = directory.rsplit("/", 1)[0] if "/" in directory else ""
    return None


# ---------------------------------------------------------------------------
# Diff filtering -- keep only the hunks for test-file paths, from the PR's
# own unified diff, so `tests.patch` is `git apply`-able as-is.
# ---------------------------------------------------------------------------

_DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")


def filter_diff_to_paths(diff_text: str, paths: set[str]) -> str:
    """Keep only the per-file blocks of `diff_text` whose new-side path is in
    `paths`. Blocks are delimited by `diff --git a/... b/...` header lines.
    """
    lines = diff_text.splitlines(keepends=True)
    kept: list[str] = []
    keep_block = False
    for line in lines:
        header = _DIFF_HEADER_RE.match(line)
        if header:
            keep_block = header.group(2) in paths
        if keep_block:
            kept.append(line)
    return "".join(kept)


def paths_present_at_base(tests_patch: str) -> list[str]:
    """The new-side paths of `tests_patch` that existed at the base SHA: every
    block except the ones git marks `new file mode`. A test file the pull
    request creates is not one the agent can delete, so it never belongs in
    `base-test-files.txt`.
    """
    present: list[str] = []
    path: str | None = None
    for line in tests_patch.splitlines():
        header = _DIFF_HEADER_RE.match(line)
        if header:
            if path is not None and path not in present:
                present.append(path)
            path = header.group(2)
        elif path is not None and line.startswith("new file mode"):
            path = None
    if path is not None and path not in present:
        present.append(path)
    return present


# ---------------------------------------------------------------------------
# Candidate records and the candidates.json store.
# ---------------------------------------------------------------------------


def candidate_id(repo_slug: str, number: int) -> str:
    return f"{repo_slug}#{number}"


def load_candidates(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise BuildError(f"{path} does not hold a JSON object keyed by candidate id")
    return document


def save_candidates(path: Path, candidates: dict[str, dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(candidates.items()))
    path.write_text(json.dumps(ordered, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scan_repository(
    owner: str,
    repo: str,
    token: str,
    path_prefix: str | None,
    max_pulls: int,
) -> dict[str, dict[str, Any]]:
    """Every merged pull request the repository's history offers, qualifying
    or not, keyed by `candidate_id`.
    """
    repo_slug = f"{owner}/{repo}"
    default_branch = get_default_branch(owner, repo, token)
    pulls = list_merged_pulls(owner, repo, token, max_pulls)

    records: dict[str, dict[str, Any]] = {}
    for pr in pulls:
        number = pr["number"]
        files = get_pr_files(owner, repo, number, token)
        reason = qualifying_reason(pr, files, default_branch, path_prefix)
        # Excludes a test file the PR deleted -- see `kept_test_files` -- so
        # every recorded test file is one `tests.patch` can actually apply.
        test_files = kept_test_files(files)
        _, non_test_files = split_test_files(files)

        # The `GET .../pulls` list endpoint carries no additions/deletions/
        # changed_files -- those three appear only on the single-PR endpoint.
        # Summing the per-file counts `GET .../pulls/{n}/files` already
        # returns is one fewer API call than fetching each PR a second time.
        additions = sum(int(f.get("additions") or 0) for f in files)
        deletions = sum(int(f.get("deletions") or 0) for f in files)

        record: dict[str, Any] = {
            "repo": repo_slug,
            "number": number,
            "title": pr.get("title"),
            "base_sha": (pr.get("base") or {}).get("sha"),
            "merge_sha": pr.get("merge_commit_sha"),
            "additions": additions,
            "deletions": deletions,
            "changed_files": len(files),
            "test_files": test_files,
            "non_test_files": non_test_files,
            "qualifies": reason is None,
            "rejection_reason": reason,
            "selected": False,
        }

        if reason is None:
            closed_issue = closed_issue_number(pr.get("body"))
            issue = get_issue(owner, repo, closed_issue, token) if closed_issue else None
            comments = get_issue_comments(owner, repo, number, token)
            record["closed_issue"] = closed_issue
            record["issue_title"] = issue.get("title") if issue else None
            record["issue_body"] = issue.get("body") if issue else None
            record["class"] = read_model_class(issue.get("body") if issue else None)
            record["class_source"] = "issue" if record["class"] != "unlabelled" else "unlabelled"
            record["elapsed_minutes"] = read_elapsed_minutes(comments)
            record["task_timeout"] = derive_task_timeout(record["elapsed_minutes"])

        records[candidate_id(repo_slug, number)] = record

    return records


# ---------------------------------------------------------------------------
# Build-time answer-key check and fixture emission.
# ---------------------------------------------------------------------------

_MAX_TEST_SECONDS = 120


def run_in(cwd: Path, command: str, timeout: int) -> tuple[int, str, str]:
    result = subprocess.run(  # noqa: S602 - the resolved test command is trusted, same as `run_command`
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def shallow_clone(repo_slug: str, sha: str, token: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    run = lambda *args: subprocess.run(  # noqa: E731
        args, cwd=dest, check=True, capture_output=True, text=True, timeout=120
    )
    run("git", "init", "-q", ".")
    run(
        "git",
        "remote",
        "add",
        "origin",
        f"https://x-access-token:{token}@github.com/{repo_slug}.git",
    )
    run("git", "fetch", "-q", "--depth", "1", "origin", sha)
    run("git", "checkout", "-q", "FETCH_HEAD")


_SKIP_PATTERN = re.compile(
    # `\.skip\(` alone already matches `pytest.skip(`, `it.skip(` and
    # `describe.skip(` as substrings, so those three forms are not named
    # again -- kept in step with the shell twin in
    # evals/fixtures/model-classes/shared/check-no-skip.sh.
    r"@pytest\.mark\.(?:skip|xfail)|\.skip\(|\bxfail\s*=",
    re.IGNORECASE,
)


def count_skip_markers(base_path: Path, test_files: list[str]) -> list[str]:
    """`<count><TAB><path>` per test file, read from `base_path`.

    Must be called before any patch is applied to `base_path`: a count taken
    after `tests.patch` describes the patch's own content, not the base SHA
    the resulting `check-no-skip.sh` run is meant to compare the agent's tree
    against.
    """
    lines = []
    for path in test_files:
        target = base_path / path
        count = 0
        if target.exists():
            count = len(_SKIP_PATTERN.findall(target.read_text(encoding="utf-8", errors="replace")))
        lines.append(f"{count}\t{path}")
    return lines


def apply_answer_key(checkout: Path, base_sha: str, tests_patch: str) -> subprocess.CompletedProcess[str]:
    """Apply `tests.patch` to `checkout` through the grader a run uses.

    The layout is a run's: scaffolding under `.fixture`, the base SHA in
    `.fixture/base-sha`, the answer key in a reference directory outside the
    checkout. So the answer key is validated by the code that will apply it.
    `checkout` must hold `base_sha`, because the grader restores the key's
    paths from it.
    """
    fixture = checkout / ".fixture"
    fixture.mkdir(exist_ok=True)
    (fixture / "base-sha").write_text(base_sha + "\n", encoding="utf-8")
    shutil.copy(_GRADER, fixture / "apply-tests.sh")
    with tempfile.TemporaryDirectory(prefix="model-classes-reference-") as reference_dir:
        (Path(reference_dir) / "tests.patch").write_text(tests_patch, encoding="utf-8")
        return subprocess.run(
            ["bash", ".fixture/apply-tests.sh"],
            cwd=checkout,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "REFERENCE_DIR": reference_dir},
        )


def verify_answer_key(
    repo_slug: str,
    record: dict[str, Any],
    tests_patch: str,
    test_command: str,
    token: str,
) -> tuple[bool, str, float, list[str]]:
    """Apply `tests.patch` to the base SHA and require the test command to
    FAIL; apply it to the merge SHA and require it to PASS, under
    `_MAX_TEST_SECONDS`. Returns (accepted, reason, merge_sha_seconds,
    base_skip_counts).

    Both sides apply the key through `apply_answer_key`, the grader path. On
    the merge SHA that is a no-op for a key taken whole from the pull request,
    and it is what lets a trimmed key be checked at all: the merge SHA carries
    the assertions the trim removed, and the grader puts the key's paths back
    to the base before it applies the trimmed patch.

    The base SHA is cloned once, here, and read for `base_skip_counts` before
    `tests.patch` is applied to that same checkout -- not cloned a second
    time later just to take that reading.
    """
    with tempfile.TemporaryDirectory(prefix="model-classes-base-") as base_dir:
        base_path = Path(base_dir)
        shallow_clone(repo_slug, record["base_sha"], token, base_path)
        skip_counts = count_skip_markers(base_path, record["test_files"])
        apply = apply_answer_key(base_path, record["base_sha"], tests_patch)
        if apply.returncode != 0:
            return False, f"tests.patch does not apply to the base SHA: {apply.stderr[:300]}", 0.0, skip_counts
        try:
            code, _, _ = run_in(base_path, test_command, _MAX_TEST_SECONDS)
        except subprocess.TimeoutExpired:
            return (
                False,
                "test command on the base SHA did not finish within the build-time bound",
                0.0,
                skip_counts,
            )
        if code == 0:
            return False, "tests.patch passes on the base SHA; it is not an answer key", 0.0, skip_counts

    with tempfile.TemporaryDirectory(prefix="model-classes-merge-") as merge_dir:
        merge_path = Path(merge_dir)
        shallow_clone(repo_slug, record["merge_sha"], token, merge_path)
        subprocess.run(
            ["git", "fetch", "-q", "--depth", "1", "origin", record["base_sha"]],
            cwd=merge_path,
            check=True,
            capture_output=True,
            timeout=120,
        )
        apply = apply_answer_key(merge_path, record["base_sha"], tests_patch)
        if apply.returncode != 0:
            return False, f"tests.patch does not apply over the merge SHA: {apply.stderr[:300]}", 0.0, skip_counts
        started = time.monotonic()
        try:
            code, out, err = run_in(merge_path, test_command, _MAX_TEST_SECONDS)
        except subprocess.TimeoutExpired:
            return False, f"test command exceeded {_MAX_TEST_SECONDS}s on the merge SHA", 0.0, skip_counts
        elapsed = time.monotonic() - started
        if code != 0:
            return False, f"tests.patch fails on the merge SHA: {(out + err)[:300]}", elapsed, skip_counts

    return True, "", elapsed, skip_counts


def write_case_fixture(
    case_name: str,
    tests_patch: str,
    base_skip_counts: list[str],
) -> None:
    """The reference directory for one selected case: `tests.patch`,
    `base-test-files.txt` (the patch's paths the base SHA already had), and
    `base-skip-counts.txt` (from `base_skip_counts`
    -- `verify_answer_key`'s reading of the base SHA it already cloned, taken
    before it applied `tests.patch` to that checkout). The task mounts none of
    it into the sandbox: coder_eval stages it outside, for criteria only.
    """
    case_dir = CASES_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    (case_dir / "tests.patch").write_text(tests_patch, encoding="utf-8")

    base_test_files = "\n".join(paths_present_at_base(tests_patch)) + "\n"
    (case_dir / "base-test-files.txt").write_text(base_test_files, encoding="utf-8")
    (case_dir / "base-skip-counts.txt").write_text("\n".join(base_skip_counts) + "\n", encoding="utf-8")


_TASK_TEMPLATE = """\
task_id: model-classes-{case_name}
description: >-
  {description}
tags: [model-classes, {class_tag}{smoke_tag}]

sandbox:
  template_sources:
    - type: template_dir
      path: ../../fixtures/model-classes/shared
      mount_point: .fixture

# The answer key. coder_eval stages it outside the sandbox and names it in
# REFERENCE_DIR for the criteria alone, so the agent cannot find it in its tree.
reference:
  directory: ../../fixtures/model-classes/cases/{case_name}

pre_run:
  - command: bash .fixture/clone-base.sh {repo_slug} {base_sha}
    timeout: 120

agent:
  allowed_tools: [Bash, Read, Write, Edit, Grep, Glob]

run_limits:
  max_turns: 30
  task_timeout: {task_timeout}
  turn_timeout: {turn_timeout}

initial_prompt: {initial_prompt}

success_criteria:
  - type: run_command
    description: No test file present at the base SHA was deleted
    command: bash .fixture/check-no-deleted.sh
    timeout: 30
    weight: 1

  - type: run_command
    description: No skip or xfail marker was added to a test file
    command: bash .fixture/check-no-skip.sh
    timeout: 30
    weight: 1

  - type: run_command
    description: The pull request's own tests pass after applying tests.patch
    command: {grading_command}
    timeout: {grading_timeout}
    weight: 3
"""


def _yaml_escape_block(text: str) -> str:
    """Fold `text` into a YAML `>-` block's continuation-line indentation."""
    return text.replace("\n", "\n  ")


def yaml_quoted(text: str) -> str:
    """`text` as a YAML double-quoted scalar.

    A JSON string is a valid YAML double-quoted scalar, escapes and all, so
    an issue body's newlines, quotes, backticks and leading `#`s survive
    verbatim -- which no hand-folded block scalar guarantees.
    """
    return json.dumps(text, ensure_ascii=False)


def task_prompt(repo_slug: str, record: dict[str, Any]) -> str:
    """The agent's instructions: the closed issue's own title and body.

    Neither the pull request's number nor the issue's is given. Either one is
    a lookup key for the merged change, and the issue text is the whole
    specification, so the agent has nothing to fetch.
    """
    title = record.get("issue_title")
    body = (record.get("issue_body") or "").strip()
    if not title:
        raise BuildError(f"{repo_slug}#{record['number']}: no issue title recorded; rescan the repository")
    return (
        f"This is {repo_slug}, checked out at a past commit. Implement the change "
        "the issue below describes. Work from this checkout and the issue text "
        f"alone: do not fetch from {repo_slug}, and do not look it up on GitHub.\n\n"
        f"# {title}\n\n{body}\n"
    )


def write_task_yaml(case_name: str, repo_slug: str, record: dict[str, Any], test_command: str, smoke: bool) -> None:
    """Write the task YAML for one selected case from its candidate record."""
    task_timeout = record["task_timeout"]
    turn_timeout = max(180, task_timeout - 120)
    grading_command = f"bash .fixture/apply-tests.sh && {test_command}"
    description = f"{repo_slug}#{record['number']}: {record['title']}"
    content = _TASK_TEMPLATE.format(
        case_name=case_name,
        description=_yaml_escape_block(description),
        class_tag=f"class:{record['class']}",
        smoke_tag=", smoke" if smoke else "",
        repo_slug=repo_slug,
        base_sha=record["base_sha"],
        task_timeout=task_timeout,
        turn_timeout=turn_timeout,
        initial_prompt=yaml_quoted(task_prompt(repo_slug, record)),
        grading_command=grading_command,
        grading_timeout=max(60, task_timeout - 60),
    )
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    (TASKS_DIR / f"{case_name}.yaml").write_text(content, encoding="utf-8")


def candidate_pool(candidates: dict[str, dict[str, Any]], klass: str) -> list[str]:
    """Every qualifying candidate of `klass`, smallest changed-line total first.

    Every one of them, not just the top `per_class` -- `build_selected` walks
    this list until enough are ACCEPTED, because a candidate can still fail
    the build-time answer-key check or resolve to no known test command, and
    a pre-sliced top-N would strand the suite short with no way to reach past
    the failure for the next-smallest candidate.
    """
    pool = [
        (candidate_id, record)
        for candidate_id, record in candidates.items()
        if record.get("qualifies") and record.get("class") == klass and not record.get("excluded")
    ]
    pool.sort(key=lambda item: (item[1].get("additions") or 0) + (item[1].get("deletions") or 0))
    return [candidate_id for candidate_id, _ in pool]


def exclude_candidate(candidates: dict[str, dict[str, Any]], candidate_id: str, reason: str) -> None:
    """Take `candidate_id` out of the suite for good, recording `reason`, and
    delete the fixture and task YAML it was built into.

    For a case the build-time check cannot catch: one whose answer key passes
    on the merge SHA but asserts what its issue leaves open or contradicts, so
    a model that does exactly what the issue asks still fails it.
    """
    if candidate_id not in candidates:
        raise BuildError(f"--exclude names {candidate_id!r}, which is not a known candidate")
    if not reason.strip():
        raise BuildError(f"--exclude {candidate_id} needs a reason after '='")
    record = candidates[candidate_id]
    record["excluded"] = reason.strip()
    record["selected"] = False
    case_name = case_name_for(candidate_id)
    shutil.rmtree(CASES_DIR / case_name, ignore_errors=True)
    (TASKS_DIR / f"{case_name}.yaml").unlink(missing_ok=True)


def record_key_trim(candidates: dict[str, dict[str, Any]], candidate_id: str, reason: str) -> None:
    """Record on a selected case that its committed `tests.patch` is trimmed.

    A trim removes only assertions the case's issue does not decide, never
    adds one. The record is what stops `--select` from rebuilding the key
    whole from the pull request's diff, and what tells a reader the key and
    the merged pull request differ on purpose.
    """
    if candidate_id not in candidates:
        raise BuildError(f"--trim-key names {candidate_id!r}, which is not a known candidate")
    if not reason.strip():
        raise BuildError(f"--trim-key {candidate_id} needs a reason after '='")
    record = candidates[candidate_id]
    if not record.get("selected"):
        raise BuildError(f"--trim-key {candidate_id}: only a selected case has a key to trim")
    record["key_trim"] = reason.strip()


def manifest_mismatches(case_dir: Path, tests_patch: str, base_skip_counts: list[str]) -> list[str]:
    """The committed manifests in `case_dir` that disagree with the ones
    `write_case_fixture` would write for `tests.patch` and `base_skip_counts`.

    A trimmed key is edited by hand after the fixture is written, so its
    manifests can drift from it; the deletion and skip checks read them.
    """
    expected = {
        "base-test-files.txt": "\n".join(paths_present_at_base(tests_patch)) + "\n",
        "base-skip-counts.txt": "\n".join(base_skip_counts) + "\n",
    }
    mismatches = []
    for name, content in expected.items():
        path = case_dir / name
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            mismatches.append(name)
    return mismatches


def verify_case(candidates: dict[str, dict[str, Any]], candidate_id: str, token: str) -> bool:
    """Run the build-time answer-key check on a selected case's committed
    `tests.patch`, trimmed or not, and check its manifests against it.
    """
    record = candidates.get(candidate_id)
    if record is None:
        raise BuildError(f"--verify-case names {candidate_id!r}, which is not a known candidate")
    if not record.get("selected") or not record.get("test_command"):
        raise BuildError(f"--verify-case {candidate_id}: not a selected case")
    case_dir = CASES_DIR / case_name_for(candidate_id)
    tests_patch = (case_dir / "tests.patch").read_text(encoding="utf-8")

    print(f"verifying {candidate_id}...", file=sys.stderr)
    accepted, reason, _, skip_counts = verify_answer_key(
        record["repo"], record, tests_patch, record["test_command"], token
    )
    if accepted:
        stale = manifest_mismatches(case_dir, tests_patch, skip_counts)
        if stale:
            accepted, reason = False, f"manifests disagree with tests.patch: {', '.join(stale)}"
    print(f"  {'passed' if accepted else 'failed: ' + reason}", file=sys.stderr)
    return accepted


def case_name_for(candidate_id: str) -> str:
    """`owner/repo#N` -> `repo-N`, the fixture directory and task_id stem."""
    repo_part, _, number = candidate_id.partition("#")
    repo_name = repo_part.rsplit("/", 1)[-1]
    return f"{repo_name}-{number}"


def try_build_one(candidate_id: str, record: dict[str, Any], token: str, smoke: bool) -> bool:
    """Attempt the build-time answer-key check and fixture emission for one
    candidate. Returns whether it was accepted; either way the record is
    updated in place with the outcome.
    """
    if record.get("key_trim"):
        raise BuildError(f"{candidate_id} has a trimmed key; check it with --verify-case, not a rebuild")
    repo_slug = record["repo"]
    owner, _, repo = repo_slug.partition("/")
    number = record["number"]

    diff_text = get_pr_diff(owner, repo, number, token)
    tests_patch = filter_diff_to_paths(diff_text, set(record["test_files"]))
    if not tests_patch.strip():
        record["selected"] = False
        record["rejection_reason"] = "no diff hunks matched the recorded test files"
        return False

    package = None
    if record["test_files"] and record["test_files"][0].endswith((".test.ts", ".test.tsx")):
        package = package_for_path(owner, repo, record["test_files"][0], record["merge_sha"], token)
    test_command = resolve_test_command(repo_slug, record["test_files"], package)
    if test_command is None:
        record["selected"] = False
        record["rejection_reason"] = "no known test command for this case's test files"
        return False

    print(f"verifying {candidate_id}...", file=sys.stderr)
    accepted, reason, merge_seconds, skip_counts = verify_answer_key(
        repo_slug, record, tests_patch, test_command, token
    )
    if not accepted:
        record["selected"] = False
        record["rejection_reason"] = reason
        print(f"  rejected: {reason}", file=sys.stderr)
        return False

    case_name = case_name_for(candidate_id)
    ensure_issue_text(record, token)
    write_case_fixture(case_name, tests_patch, skip_counts)
    write_task_yaml(case_name, repo_slug, record, test_command, smoke=smoke)

    record["selected"] = True
    record["rejection_reason"] = None
    record["merge_test_seconds"] = round(merge_seconds, 1)
    record["test_command"] = test_command
    print(f"  accepted -> evals/tasks/model-classes/{case_name}.yaml", file=sys.stderr)
    return True


def build_selected(
    candidates: dict[str, dict[str, Any]],
    per_class: int,
    token: str,
) -> None:
    """Walk each buildable class's candidate pool, smallest first, attempting
    the build-time check until `per_class` are accepted or the pool runs out.
    The first accepted candidate of each class carries `smoke`.
    """
    for klass in BUILDABLE_CLASSES:
        accepted_count = 0
        for candidate_id in candidate_pool(candidates, klass):
            if accepted_count >= per_class:
                break
            record = candidates[candidate_id]
            if record.get("selected"):
                accepted_count += 1
                continue
            if try_build_one(candidate_id, record, token, smoke=(accepted_count == 0)):
                accepted_count += 1
        if accepted_count < per_class:
            print(
                f"build_selected: only {accepted_count}/{per_class} {klass} case(s) accepted; "
                "widen the scan (more --max-pulls, another source) or add a --class-override",
                file=sys.stderr,
            )


def ensure_issue_text(record: dict[str, Any], token: str) -> None:
    """Read the closed issue's title and body into `record` where a scan from
    before the prompt carried them left it without.
    """
    if record.get("issue_title"):
        return
    owner, _, repo = record["repo"].partition("/")
    issue = get_issue(owner, repo, record["closed_issue"], token)
    if issue is None:
        raise BuildError(f"{record['repo']}#{record['number']}: issue #{record['closed_issue']} could not be read")
    record["issue_title"] = issue.get("title")
    record["issue_body"] = issue.get("body")


def rewrite_selected_tasks(candidates: dict[str, dict[str, Any]], token: str) -> None:
    """Rewrite the task YAML of every selected case from its record, reading
    the closed issue's text first where the record predates keeping it.

    `smoke` goes to the first selected case of each class in pool order, the
    same case `build_selected` gave it to.
    """
    for klass in BUILDABLE_CLASSES:
        selected = [cid for cid in candidate_pool(candidates, klass) if candidates[cid].get("selected")]
        for index, candidate_id in enumerate(selected):
            record = candidates[candidate_id]
            repo_slug = record["repo"]
            ensure_issue_text(record, token)
            write_task_yaml(case_name_for(candidate_id), repo_slug, record, record["test_command"], smoke=index == 0)
            print(f"rewrote evals/tasks/model-classes/{case_name_for(candidate_id)}.yaml", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    _run_self_tests()

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("repo", nargs="?", help="owner/repo to scan for qualifying merged pull requests")
    parser.add_argument("--path-prefix", default=None, help="restrict qualifying PRs to this path")
    parser.add_argument("--max-pulls", type=int, default=200, help="most recently updated merged PRs to scan")
    parser.add_argument("--candidates-file", type=Path, default=DEFAULT_CANDIDATES_FILE)
    parser.add_argument(
        "--class-override",
        action="append",
        default=[],
        metavar="owner/repo#N=token",
        help="classify an `unlabelled` candidate as mechanical or implementation (repeatable)",
    )
    parser.add_argument("--select", action="store_true", help="build fixtures + task YAMLs from candidates.json")
    parser.add_argument("--per-class", type=int, default=3, help="cases to select per buildable class")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="owner/repo#N=reason",
        help="take a candidate out of the suite for good, and delete its fixture (repeatable)",
    )
    parser.add_argument(
        "--rewrite-tasks",
        action="store_true",
        help="rewrite every selected case's task YAML from candidates.json",
    )
    parser.add_argument(
        "--trim-key",
        action="append",
        default=[],
        metavar="owner/repo#N=reason",
        help="record that a selected case's committed tests.patch is trimmed, and why (repeatable)",
    )
    parser.add_argument(
        "--verify-case",
        action="append",
        default=[],
        metavar="owner/repo#N",
        help="run the build-time check on a selected case's committed tests.patch (repeatable)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run the offline self-tests and nothing else; needs no token",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return 0

    if not (args.repo or args.select or args.rewrite_tasks or args.exclude or args.trim_key or args.verify_case):
        parser.error(
            "a repo is required unless --select, --rewrite-tasks, --exclude, --trim-key or --verify-case is given"
        )

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise BuildError("GITHUB_TOKEN or GH_TOKEN must be set")

    candidates = load_candidates(args.candidates_file)

    if args.repo:
        owner, _, repo = args.repo.partition("/")
        if not repo:
            parser.error("repo must be 'owner/repo'")
        found = scan_repository(owner, repo, token, args.path_prefix, args.max_pulls)
        candidates.update(found)
        qualifying = sum(1 for record in found.values() if record["qualifies"])
        print(f"{args.repo}: {len(found)} merged PR(s) scanned, {qualifying} qualify")

    for raw in args.class_override:
        slug, token_class = parse_class_override(raw)
        if slug not in candidates:
            raise BuildError(f"--class-override names {slug!r}, which is not a known candidate")
        candidates[slug]["class"] = token_class
        candidates[slug]["class_source"] = "override"

    for raw in args.exclude:
        slug, _, reason = raw.partition("=")
        exclude_candidate(candidates, slug, reason)

    for raw in args.trim_key:
        slug, _, reason = raw.partition("=")
        record_key_trim(candidates, slug, reason)

    save_candidates(args.candidates_file, candidates)

    if args.select:
        build_selected(candidates, args.per_class, token)
        save_candidates(args.candidates_file, candidates)

    if args.rewrite_tasks:
        rewrite_selected_tasks(candidates, token)
        save_candidates(args.candidates_file, candidates)

    failed = [slug for slug in args.verify_case if not verify_case(candidates, slug, token)]
    if failed:
        raise BuildError(f"--verify-case failed for {', '.join(failed)}")

    return 0


# ---------------------------------------------------------------------------
# Self-tests -- see the module docstring. Inline dicts shaped like the GitHub
# REST payloads this script actually reads.
# ---------------------------------------------------------------------------


def _run_self_tests() -> None:
    _test_is_test_path()
    _test_split_test_files()
    _test_kept_test_files()
    _test_closed_issue_number()
    _test_qualifying_reason()
    _test_read_model_class()
    _test_read_elapsed_minutes()
    _test_derive_task_timeout()
    _test_filter_diff_to_paths()
    _test_paths_present_at_base()
    _test_count_skip_markers()
    _test_resolve_test_command()
    _test_task_prompt()
    _test_candidate_pool()
    _test_yaml_quoted()
    _test_record_key_trim()
    _test_manifest_mismatches()
    _test_apply_answer_key_over_merge()


def _test_is_test_path() -> None:
    assert is_test_path("tests/test_foo.py")
    assert is_test_path("kokoro/tests/test_bar.py")
    assert is_test_path("src/foo_test.py")
    assert is_test_path("src/foo.test.ts")
    assert is_test_path("test_toplevel.py")
    assert not is_test_path("src/foo.py")
    assert not is_test_path("docs/testing-guide.md")  # "testing", not "test_" or "tests/"
    assert not is_test_path("kokoro/pyproject.toml")


def _test_split_test_files() -> None:
    files = [
        {"filename": "kokoro/core/policy.py"},
        {"filename": "kokoro/tests/test_policy.py"},
        {"filename": "README.md"},
    ]
    test_files, non_test_files = split_test_files(files)
    assert test_files == ["kokoro/tests/test_policy.py"]
    assert non_test_files == ["kokoro/core/policy.py", "README.md"]


def _test_kept_test_files() -> None:
    files = [
        {"filename": "src/foo.py", "status": "modified"},
        {"filename": "tests/test_foo.py", "status": "added"},
        {"filename": "tests/test_old.py", "status": "removed"},
    ]
    assert kept_test_files(files) == ["tests/test_foo.py"]

    all_removed = [
        {"filename": "src/foo.py", "status": "modified"},
        {"filename": "tests/test_old.py", "status": "removed"},
    ]
    assert kept_test_files(all_removed) == []


def _test_closed_issue_number() -> None:
    assert closed_issue_number("Fixes #328\n\nDetails.") == 328
    assert closed_issue_number("Closes: #12") == 12
    assert closed_issue_number("resolved #7 already") == 7
    assert closed_issue_number("See #99 for background.") is None
    assert closed_issue_number(None) is None


_SAMPLE_FILES = [
    {"filename": "kokoro/core/policy.py"},
    {"filename": "kokoro/tests/test_policy.py"},
]


def _test_qualifying_reason() -> None:
    merged_pr = {
        "merged_at": "2026-09-15T00:00:00Z",
        "base": {"ref": "master"},
        "body": "Fixes #328",
    }
    assert qualifying_reason(merged_pr, _SAMPLE_FILES, "master", None) is None

    unmerged = {**merged_pr, "merged_at": None}
    assert qualifying_reason(unmerged, _SAMPLE_FILES, "master", None) == "not merged"

    wrong_base = {**merged_pr, "base": {"ref": "release-please--branches--master"}}
    reason = qualifying_reason(wrong_base, _SAMPLE_FILES, "master", None)
    assert reason is not None and "base is" in reason

    only_source = [{"filename": "kokoro/core/policy.py"}]
    reason = qualifying_reason(merged_pr, only_source, "master", None)
    assert reason == "touches no test file"

    only_tests = [{"filename": "kokoro/tests/test_policy.py"}]
    reason = qualifying_reason(merged_pr, only_tests, "master", None)
    assert reason == "touches only test files, no source change"

    no_issue = {**merged_pr, "body": "See #99 for background."}
    reason = qualifying_reason(no_issue, _SAMPLE_FILES, "master", None)
    assert reason is not None and "Closes #N" in reason

    removed_test_file = [
        {"filename": "kokoro/core/policy.py"},
        {"filename": "kokoro/tests/test_policy.py", "status": "removed"},
    ]
    reason = qualifying_reason(merged_pr, removed_test_file, "master", None)
    assert reason is not None and "was removed" in reason

    outside_prefix = qualifying_reason(merged_pr, _SAMPLE_FILES, "master", "apps/usd2oz-web")
    assert outside_prefix is not None and "path prefix" in outside_prefix

    inside_prefix_files = [
        {"filename": "apps/usd2oz-web/src/convert.ts"},
        {"filename": "apps/usd2oz-web/src/convert.test.ts"},
    ]
    assert qualifying_reason(merged_pr, inside_prefix_files, "master", "apps/usd2oz-web") is None


def _test_read_model_class() -> None:
    for token in ("mechanical", "implementation", "reasoning"):
        assert read_model_class(f"## Model class\n`{token}`\n") == token
    for token in ("standard", "advanced", "implementation-suffix", "reasoning_suffix"):
        assert read_model_class(f"## Model class\n`{token}`\n") == "unlabelled"
    assert read_model_class("## Model class\nmechanical-extra\n") == "unlabelled"
    assert read_model_class("no such section here") == "unlabelled"
    assert read_model_class(None) == "unlabelled"

    assert parse_class_override("jmcvetta/career#511=mechanical") == (
        "jmcvetta/career#511",
        "mechanical",
    )
    assert parse_class_override("jmcvetta/career#511=implementation") == (
        "jmcvetta/career#511",
        "implementation",
    )
    for token in ("reasoning", "standard", "advanced", "implementation-extra"):
        try:
            parse_class_override(f"jmcvetta/career#511={token}")
        except BuildError:
            pass
        else:
            raise AssertionError(f"accepted invalid buildable class override: {token}")


def _test_read_elapsed_minutes() -> None:
    bullet_form = [
        {
            "body": (
                "First-readiness report\n\n"
                "- claim: 2026-09-22T13:40:40Z\n"
                "- first merge readiness: 2026-09-22T14:12:36Z\n"
                "- elapsed wall time: 31 minutes 56 seconds\n"
            )
        }
    ]
    assert read_elapsed_minutes(bullet_form) == 31

    timing_form = [
        {
            "body": (
                "First-readiness report\n\n"
                "Timing: 2026-09-22T13:01:45Z → 2026-09-22T14:10:04Z (1 hour and 8 minutes)\n"
            )
        }
    ]
    assert read_elapsed_minutes(timing_form) == 68

    no_marker = [{"body": "just a regular comment mentioning 5 minutes of downtime"}]
    assert read_elapsed_minutes(no_marker) is None

    # A duration mentioned before the real elapsed-time line must not win.
    distractor_first = [
        {
            "body": (
                "First-readiness report\n\n"
                "CI flaked and took 3 hours 40 minutes to stabilize before the "
                "real run finished.\n"
                "- elapsed wall time: 22 minutes\n"
            )
        }
    ]
    assert read_elapsed_minutes(distractor_first) == 22

    assert read_elapsed_minutes([]) is None


def _test_derive_task_timeout() -> None:
    assert derive_task_timeout(None) == 780
    assert derive_task_timeout(1) == 300  # 2*1*60=120s, floored at 300
    assert derive_task_timeout(100) == 780  # 2*100*60=12000s, capped at 780
    assert derive_task_timeout(4) == 480  # 2*4*60=480s, between the bounds


def _test_filter_diff_to_paths() -> None:
    diff_text = (
        "diff --git a/src/foo.py b/src/foo.py\n"
        "index 111..222 100644\n"
        "--- a/src/foo.py\n"
        "+++ b/src/foo.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
        "diff --git a/tests/test_foo.py b/tests/test_foo.py\n"
        "index 333..444 100644\n"
        "--- a/tests/test_foo.py\n"
        "+++ b/tests/test_foo.py\n"
        "@@ -1 +1,2 @@\n"
        " def test_x(): ...\n"
        "+def test_y(): ...\n"
    )
    filtered = filter_diff_to_paths(diff_text, {"tests/test_foo.py"})
    assert "src/foo.py" not in filtered
    assert "tests/test_foo.py" in filtered
    assert "+def test_y" in filtered


def _test_paths_present_at_base() -> None:
    patch = (
        "diff --git a/tests/test_old.py b/tests/test_old.py\n"
        "index 111..222 100644\n"
        "--- a/tests/test_old.py\n"
        "+++ b/tests/test_old.py\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "+b\n"
        "diff --git a/tests/test_new.py b/tests/test_new.py\n"
        "new file mode 100644\n"
        "index 000..333\n"
        "--- /dev/null\n"
        "+++ b/tests/test_new.py\n"
        "@@ -0,0 +1 @@\n"
        "+new file mode is text here, not a header\n"
        "diff --git a/tests/test_last.py b/tests/test_last.py\n"
        "index 444..555 100644\n"
    )
    assert paths_present_at_base(patch) == ["tests/test_old.py", "tests/test_last.py"]
    assert paths_present_at_base("") == []


def _test_count_skip_markers() -> None:
    with tempfile.TemporaryDirectory(prefix="model-classes-selftest-") as tmp:
        base = Path(tmp)
        (base / "tests").mkdir()
        (base / "tests" / "test_a.py").write_text(
            "@pytest.mark.skip(reason='wip')\ndef test_a(): ...\n"
            "@pytest.mark.xfail\ndef test_b(): ...\n",
            encoding="utf-8",
        )
        (base / "tests" / "test_b.py").write_text(
            "def test_c(): ...\n",  # no markers
            encoding="utf-8",
        )
        counts = count_skip_markers(base, ["tests/test_a.py", "tests/test_b.py", "tests/missing.py"])
        assert counts == [
            "2\ttests/test_a.py",
            "0\ttests/test_b.py",
            "0\ttests/missing.py",
        ]


def _test_resolve_test_command() -> None:
    kokoro_only = resolve_test_command("jmcvetta/career", ["kokoro/tests/test_policy.py"], None)
    assert kokoro_only is not None and kokoro_only.startswith("cd kokoro &&")

    root_only = resolve_test_command("jmcvetta/career", ["tests/test_infra.py"], None)
    assert root_only is not None and root_only.startswith("cd viewer &&")
    assert "../tests/test_infra.py" in root_only

    mixed = resolve_test_command(
        "jmcvetta/career", ["kokoro/tests/test_policy.py", "tests/test_infra.py"], None
    )
    assert mixed is None

    pagoda_ts = resolve_test_command(
        "Green-Pagoda/pagoda",
        ["apps/usd2oz-web/src/convert.test.ts"],
        ("@pagoda/usd2oz-web", "apps/usd2oz-web"),
    )
    assert pagoda_ts is not None
    assert "pnpm install --frozen-lockfile --filter @pagoda/usd2oz-web..." in pagoda_ts
    # Relative to the package directory, not the repo root -- vitest resolves
    # its arguments against the filtered package's own cwd.
    assert "pnpm --filter @pagoda/usd2oz-web exec vitest run src/convert.test.ts" in pagoda_ts
    assert pagoda_ts.index("install") < pagoda_ts.index("vitest run")

    pagoda_no_package = resolve_test_command(
        "Green-Pagoda/pagoda", ["apps/usd2oz-web/src/convert.test.ts"], None
    )
    assert pagoda_no_package is None

    pagoda_outside_package = resolve_test_command(
        "Green-Pagoda/pagoda",
        ["apps/usd2oz-web/src/convert.test.ts", "packages/gold-prices/index.test.ts"],
        ("@pagoda/usd2oz-web", "apps/usd2oz-web"),
    )
    assert pagoda_outside_package is None

    unknown_repo = resolve_test_command("someone/else", ["tests/test_x.py"], None)
    assert unknown_repo is None


def _test_task_prompt() -> None:
    record = {
        "number": 338,
        "closed_issue": 337,
        "title": 'fix(usd2oz-web): say "calculator"',
        "issue_title": "Methodology page footer link should say \"back to calculator\"",
        "issue_body": "The footer link reads \"Back to the converter\".\n\n**Definition of done:** it says so.\n",
    }
    prompt = task_prompt("Green-Pagoda/pagoda", record)
    assert "# Methodology page footer link" in prompt, prompt
    assert "**Definition of done:** it says so." in prompt, prompt
    # Either number is a lookup key for the merged change.
    assert "338" not in prompt and "337" not in prompt, prompt
    assert "do not fetch from Green-Pagoda/pagoda" in prompt, prompt
    # The pull request's title is not the specification; the issue's is.
    assert 'say "calculator"' not in prompt, prompt
    try:
        task_prompt("Green-Pagoda/pagoda", {**record, "issue_title": None})
    except BuildError:
        pass
    else:
        raise AssertionError("task_prompt accepted a record with no issue title")


def _test_yaml_quoted() -> None:
    text = 'A "quoted" line\n\n# not a comment\n  - not a list: `x`\n\\ and \u2190 arrow\n'
    quoted = yaml_quoted(text)
    assert "\n" not in quoted, quoted
    assert quoted.startswith('"') and quoted.endswith('"'), quoted
    assert json.loads(quoted) == text
    try:
        import yaml  # noqa: PLC0415 - the dev venv has it; the builder itself never needs it
    except ImportError:
        return
    assert yaml.safe_load(f"initial_prompt: {quoted}\n") == {"initial_prompt": text}



def _test_candidate_pool() -> None:
    candidates = {
        "o/r#3": {"qualifies": True, "class": "mechanical", "additions": 30, "deletions": 0},
        "o/r#1": {"qualifies": True, "class": "mechanical", "additions": 5, "deletions": 5},
        "o/r#2": {"qualifies": True, "class": "mechanical", "additions": 1, "deletions": 0, "excluded": "key asserts an open name"},
        "o/r#4": {"qualifies": False, "class": "mechanical", "additions": 1, "deletions": 0},
        "o/r#5": {"qualifies": True, "class": "implementation", "additions": 1, "deletions": 0},
    }
    # Smallest first; an excluded candidate never returns, however small.
    assert candidate_pool(candidates, "mechanical") == ["o/r#1", "o/r#3"], candidate_pool(candidates, "mechanical")
    try:
        exclude_candidate(candidates, "o/r#1", "  ")
    except BuildError:
        pass
    else:
        raise AssertionError("exclude_candidate accepted an empty reason")


def _test_record_key_trim() -> None:
    candidates = {
        "o/r#1": {"selected": True},
        "o/r#2": {"selected": False},
    }
    record_key_trim(candidates, "o/r#1", "  drops an assertion the issue leaves open ")
    assert candidates["o/r#1"]["key_trim"] == "drops an assertion the issue leaves open"
    for candidate_id, reason in (("o/r#1", " "), ("o/r#2", "reason"), ("o/r#9", "reason")):
        try:
            record_key_trim(candidates, candidate_id, reason)
        except BuildError:
            pass
        else:
            raise AssertionError(f"record_key_trim accepted {candidate_id}={reason!r}")
    assert "key_trim" not in candidates["o/r#2"]

    try:
        try_build_one("o/r#1", candidates["o/r#1"], "no-token", smoke=False)
    except BuildError:
        pass
    else:
        raise AssertionError("try_build_one rebuilt a trimmed key")


def _test_manifest_mismatches() -> None:
    patch = (
        "diff --git a/tests/test_old.py b/tests/test_old.py\n"
        "index 111..222 100644\n"
        "diff --git a/tests/test_new.py b/tests/test_new.py\n"
        "new file mode 100644\n"
    )
    counts = ["1\ttests/test_old.py", "0\ttests/test_new.py"]
    with tempfile.TemporaryDirectory(prefix="model-classes-selftest-") as tmp:
        case_dir = Path(tmp)
        assert manifest_mismatches(case_dir, patch, counts) == ["base-test-files.txt", "base-skip-counts.txt"]
        (case_dir / "base-test-files.txt").write_text("tests/test_old.py\n", encoding="utf-8")
        (case_dir / "base-skip-counts.txt").write_text("\n".join(counts) + "\n", encoding="utf-8")
        assert manifest_mismatches(case_dir, patch, counts) == []
        assert manifest_mismatches(case_dir, patch, ["0\ttests/test_old.py", counts[1]]) == ["base-skip-counts.txt"]


def _test_apply_answer_key_over_merge() -> None:
    """A trimmed key applied over the merge SHA leaves the trimmed file, not
    the merged one; a key that does not match the base fails to apply."""
    with tempfile.TemporaryDirectory(prefix="model-classes-selftest-") as tmp:
        repo = Path(tmp)

        def git(*args: str) -> str:
            return subprocess.run(
                ["git", *args], cwd=repo, check=True, capture_output=True, text=True
            ).stdout.strip()

        git("init", "-q", ".")
        git("config", "user.email", "selftest@example.invalid")
        git("config", "user.name", "Self Test")
        git("config", "commit.gpgsign", "false")
        test_file = repo / "tests" / "test_x.py"
        test_file.parent.mkdir()
        test_file.write_text("def test_a(): assert 'old'\n", encoding="utf-8")
        git("add", "tests")
        git("commit", "-q", "-m", "base")
        base_sha = git("rev-parse", "HEAD")

        trimmed = "def test_a(): assert 'new'\n"
        test_file.write_text(trimmed, encoding="utf-8")
        trimmed_patch = git("diff") + "\n"
        test_file.write_text(trimmed + "def test_b(): assert 'undecided'\n", encoding="utf-8")
        git("commit", "-q", "-am", "merge")

        result = apply_answer_key(repo, base_sha, trimmed_patch)
        assert result.returncode == 0, result.stderr
        assert test_file.read_text(encoding="utf-8") == trimmed

        git("checkout", "-q", "--", "tests")
        wrong_base = trimmed_patch.replace("-def test_a(): assert 'old'", "-def test_a(): assert 'other'")
        assert apply_answer_key(repo, base_sha, wrong_base).returncode != 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except BuildError as exc:
        print(f"evals-cases-from-prs: {exc}", file=sys.stderr)
        sys.exit(1)
