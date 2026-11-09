#!/usr/bin/env python3
"""Every top-level directory is either shipped or excluded from releases.

release-please treats this repository as one package, `.`, so a commit
anywhere cuts a plugin version unless `exclude-paths` in
`release-please-config.json` names where it landed. That list is a denylist:
a new top-level directory counts as shipped until somebody remembers to add
it. This check makes the decision explicit -- each tracked top-level
directory must appear in exactly one of SHIPPED below or `exclude-paths`.

It also rejects an `exclude-paths` entry that is not a tracked top-level
directory. release-please matches an entry as a directory prefix
(`file.indexOf(path + "/") === 0` in `util/commit-exclude.js`), so an entry
naming a root file such as `Makefile` matches nothing, and says nothing about
it.

Standard library only, like `check-manifests.py`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# What a session loading the plugin, or a user bootstrapping a repository
# from `template/`, receives. A change under one of these releases a version.
# `scripts/` is mostly check legs, but `scripts/pr-keep-current.sh` is the
# Omp keep-current loop an installed plugin runs, and release-please cannot
# exclude a directory in part.
SHIPPED = frozenset(
    {
        ".claude-plugin",
        ".omp-plugin",
        "agents",
        "extensions",
        "hooks",
        "rules",
        "scripts",
        "skills",
        "template",
    }
)


def top_level_dirs(tracked: list[str]) -> set[str]:
    """top_level_dirs returns the first path component of every tracked file
    that sits in a directory. Root files have none and are left out."""
    return {path.split("/", 1)[0] for path in tracked if "/" in path}


def problems(dirs: set[str], shipped: frozenset[str], excluded: list[str]) -> list[str]:
    """problems lists each way the tracked directories, the shipped set and
    `exclude-paths` disagree. An empty list means they agree."""
    found = []
    for path in sorted({path for path in excluded if excluded.count(path) > 1}):
        found.append(f"{path}: listed more than once in exclude-paths")
    for path in sorted(set(excluded) & shipped):
        found.append(f"{path}: both shipped and in exclude-paths")
    for path in sorted(set(excluded) - dirs):
        found.append(f"{path}: in exclude-paths but not a tracked top-level directory")
    for path in sorted(dirs - shipped - set(excluded)):
        found.append(f"{path}: neither shipped nor in exclude-paths")
    return found


def self_test() -> None:
    """self_test proves each failure mode fails and a consistent tree passes."""
    dirs = {"skills", "evals"}
    shipped = frozenset({"skills"})
    cases = [
        ("consistent", ["evals"], []),
        ("unclassified directory", [], ["evals: neither shipped nor in exclude-paths"]),
        (
            "root file excluded",
            ["evals", "Makefile"],
            ["Makefile: in exclude-paths but not a tracked top-level directory"],
        ),
        ("shipped and excluded", ["evals", "skills"], ["skills: both shipped and in exclude-paths"]),
        ("duplicate entry", ["evals", "evals"], ["evals: listed more than once in exclude-paths"]),
    ]
    for name, excluded, expected in cases:
        actual = problems(dirs, shipped, excluded)
        assert actual == expected, f"self-test {name}: {actual!r}"
    assert top_level_dirs(["Makefile", "skills/a/SKILL.md", ".github/x.yml"]) == {"skills", ".github"}


def main() -> int:
    """main checks the tracked tree against `release-please-config.json` and
    returns the process exit status."""
    self_test()
    config = json.loads((ROOT / "release-please-config.json").read_text())
    excluded = config["packages"]["."].get("exclude-paths", [])
    # `-z` keeps paths unquoted: without it `core.quotePath` escapes a
    # non-ASCII directory name, which then matches no exclude-paths entry.
    tracked = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.split("\0")
    found = problems(top_level_dirs(tracked), SHIPPED, excluded)
    for problem in found:
        print(f"check-release-paths: {problem}", file=sys.stderr)
    if found:
        return 1
    print("check-release-paths: every top-level directory is shipped or excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
