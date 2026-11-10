#!/usr/bin/env python3
"""Build a deterministic local Git repository from one mounted case source."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def run(*args: str, date: str | None = None) -> str:
    """Run one Git or system command and return its trimmed text output."""
    env = os.environ.copy()
    env["TZ"] = "UTC"
    if date is not None:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    return subprocess.check_output(args, text=True, env=env).strip()


def write_files(root: Path, files: dict[str, str]) -> None:
    """Write the selected case's source files into the worktree."""
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def commit(files: dict[str, str], message: str, date: str) -> None:
    """Stage only the case files and create one fixed-date commit."""
    run("git", "add", "--", *files.keys())
    run("git", "commit", "-qm", message, date=date)


def main() -> None:
    """Create base, review, and current commits from the mounted case."""
    case_id, case_file = sys.argv[1:3]
    case = json.loads(Path(case_file).read_text())
    if case["id"] != case_id:
        raise ValueError(f"case id mismatch: {case['id']} != {case_id}")
    root = Path.cwd()
    run("git", "init", "-q", "-b", "main")
    run("git", "config", "user.name", "Eval Fixture")
    run("git", "config", "user.email", "eval@example.invalid")
    run("git", "config", "commit.gpgsign", "false")
    (root / ".git/info/exclude").open("a").write("\n/.fixture/\n/.case/\n")

    write_files(root, case["base"])
    commit(case["base"], "baseline", "2020-01-01T00:00:00+00:00")
    base = run("git", "rev-parse", "HEAD")

    run("git", "switch", "-q", "-c", "review")
    write_files(root, case["review"])
    commit(case["review"], "review change", "2020-01-02T00:00:00+00:00")
    review = run("git", "rev-parse", "HEAD")

    run("git", "switch", "-q", "-c", "current")
    current_files = case.get("current")
    if current_files is not None:
        write_files(root, current_files)
        commit(current_files, "current revision", "2020-01-03T00:00:00+00:00")
    current = run("git", "rev-parse", "HEAD")

    brief = case["brief"]
    (root / ".review-brief").write_text(
        f"{brief}\n\nBase commit: {base}\nOriginal review commit: {review}\nCurrent commit: {current}\n"
        "Review surfaces: `base...review`, `base...current`, and `review...current`.\n"
    )
    (root / ".review-commits").write_text(f"base={base}\nreview={review}\ncurrent={current}\n")
    print(f"Review brief: {brief}\nBase commit: {base}\nReview commit: {review}\nCurrent commit: {current}")


if __name__ == "__main__":
    main()
