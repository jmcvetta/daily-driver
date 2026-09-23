#!/usr/bin/env python3
"""Classify changed paths into the CI validation groups that can be affected."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPS = ("plugin", "runtime", "eval", "issue")
OVERLAYS = "omp_configs/"

# Changes to the scope mechanism or its contract must exercise every group.
SHARED = {"Makefile", ".github/workflows/ci.yml", "scripts/ci-scope.py", "pyproject.toml", "uv.lock"}
PLUGIN_PREFIXES = (".claude-plugin/", "skills/", "agents/")
RUNTIME_PREFIXES = ("hooks/", "extensions/")
EVAL_PREFIXES = ("evals/",)
ISSUE_PREFIXES = ("infra/github/",)
ISSUE_SKILL_PREFIXES = ("skills/issue-labels/", "skills/issue-deps/")
PLUGIN_SCRIPTS = {
    "scripts/check-manifests.py", "scripts/check-manifest-fixtures.py",
}
RUNTIME_SCRIPTS = {
    "scripts/check-constitution.py", "scripts/check-ask-in-chat.py",
    "scripts/check-omp-extension.mjs", "scripts/check-omp-guard-differential.mjs",
    "scripts/check-omp-cache-clean.py", "scripts/check-omp-review-cycle-route.py",
    "scripts/check-review-cycle-fix-delta-route.py", "scripts/check-task-worktree-fixture.sh",
}
EVAL_SCRIPTS = {
    "scripts/check-eval-arms.py", "scripts/check-evals-preflight.py",
    "scripts/check-evals-provenance.py", "scripts/check-eval-fixtures.sh",
    "scripts/check-omp-agent.py", "scripts/check-omp-agent-settle.py",
    "scripts/check-codex-agent.py", "scripts/evals-variants.py",
    "scripts/evals-preflight.py", "scripts/evals-record.py",
    "scripts/evals-cases-from-prs.py",
}
ISSUE_SCRIPTS = {
    "scripts/check-labels.py", "scripts/check-labels-fixtures.py",
    "scripts/check-story-fixtures.py",
}


def classify(paths: list[str]) -> set[str]:
    """Return affected groups; unknown paths conservatively select all groups."""
    affected: set[str] = set()
    for raw in paths:
        path = raw.removeprefix("./")
        if path in SHARED:
            return set(GROUPS)
        if path.startswith(OVERLAYS):
            if path == "omp_configs/README.md":
                continue
            if path.endswith(".yml"):
                experiment = ROOT / "evals" / "experiments" / f"classes-{Path(path).stem}.yaml"
                if experiment.is_file():
                    affected.add("eval")
                continue
            return set(GROUPS)
        matched = False
        if path.startswith(PLUGIN_PREFIXES) or path in PLUGIN_SCRIPTS:
            affected.add("plugin")
            matched = True
        if path.startswith(RUNTIME_PREFIXES) or path.startswith(("skills/", "evals/")) or path in RUNTIME_SCRIPTS:
            affected.add("runtime")
            matched = True
        if path.startswith(EVAL_PREFIXES) or path in EVAL_SCRIPTS:
            affected.add("eval")
            matched = True
        if path.startswith(ISSUE_SKILL_PREFIXES) or path.startswith(ISSUE_PREFIXES) or path in ISSUE_SCRIPTS:
            affected.add("issue")
            matched = True
        if path.startswith("scripts/") and path.endswith(".sh"):
            affected.add("plugin")
            matched = True
        if path.startswith("evals/fixtures/") and path.endswith(".sh"):
            affected.add("plugin")
            matched = True
        if not matched:
            return set(GROUPS)
    return affected


def changed_paths(base: str, head: str, use_merge_base: bool) -> list[str]:
    """Read changed paths against a PR merge base or push before-commit."""
    start = base
    if use_merge_base:
        start = subprocess.run(
            ["git", "merge-base", base, head], check=True, capture_output=True, text=True
        ).stdout.strip()
    result = subprocess.run(
        ["git", "diff", "--name-only", start, head],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.splitlines()


def scope_for(base: str, head: str, use_merge_base: bool = True) -> set[str]:
    """Return affected groups, failing open when the diff cannot be read."""
    try:
        if not base or not head or set(base) == {"0"}:
            raise ValueError("missing or unusable diff endpoints")
        return classify(changed_paths(base, head, use_merge_base))
    except (OSError, ValueError, subprocess.SubprocessError):
        return set(GROUPS)


def aggregate(results: list[str]) -> bool:
    """Treat successful and intentionally skipped jobs as a green aggregate."""
    return bool(results) and all(result in {"success", "skipped"} for result in results)


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--aggregate":
        return 0 if aggregate(sys.argv[2:]) else 1
    valid_scope_args = len(sys.argv) == 4 and sys.argv[3] in {"merge-base", "direct"}
    groups = (
        scope_for(sys.argv[1], sys.argv[2], sys.argv[3] == "merge-base")
        if valid_scope_args else set(GROUPS)
    )
    if not valid_scope_args:
        print("::warning::CI diff scope unavailable; running every validation group", file=sys.stderr)
    for name in GROUPS:
        print(f"run_{name}={'true' if name in groups else 'false'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
