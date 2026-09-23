#!/usr/bin/env python3
"""Assert CI scope classification and required-check aggregation offline."""
from __future__ import annotations

import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("ci-scope.py")
spec = importlib.util.spec_from_file_location("ci_scope", SCRIPT)
assert spec and spec.loader
ci_scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_scope)


def require(condition: bool, message: str) -> None:
    """Fail loudly when an offline CI contract does not hold."""
    if not condition:
        raise AssertionError(message)


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    experiments = root / "evals" / "experiments"
    experiments.mkdir(parents=True)
    with patch.object(ci_scope, "ROOT", root):
        require(ci_scope.classify(["omp_configs/personal.yml"]) == set(), "personal overlay without an experiment stays skipped")
        (experiments / "classes-personal.yaml").touch()
        require(ci_scope.classify(["omp_configs/personal.yml"]) == {"eval"}, "overlay with a suite selects eval validation")
require(ci_scope.classify([".claude-plugin/plugin.json"]) == {"plugin"}, "manifest changes must select plugin validation")
require(ci_scope.classify(["skills/pr/SKILL.md"]) == {"plugin", "runtime"}, "skill changes must select manifest and route validation")
require(ci_scope.classify(["evals/tasks/example.yaml"]) == {"eval", "runtime"}, "eval changes must run eval and shared runtime validators")
require(ci_scope.classify(["infra/github/labels.tf"]) == {"issue"}, "infrastructure changes must select issue validation")
require(ci_scope.classify(["unknown/new-file.dat"]) == set(ci_scope.GROUPS), "unknown files must fail open")
with patch.object(ci_scope, "changed_paths", side_effect=OSError("missing base")):
    require(
        ci_scope.scope_for("missing", "head") == set(ci_scope.GROUPS),
        "unavailable diff base must fail open",
    )
with patch.object(ci_scope, "changed_paths", return_value=["evals/tasks/example.yaml"]) as diff:
    require(ci_scope.scope_for("before", "head", False) == {"eval", "runtime"}, "pushes must classify before/after changes")
    diff.assert_called_once_with("before", "head", False)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    overlays = root / "omp_configs"
    overlays.mkdir()
    (overlays / "old.yml").write_text("modelRoles:\n  task: example/model\n")
    subprocess.run(["git", "-C", str(root), "add", "omp_configs/old.yml"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
         "commit", "-qm", "initial overlay"],
        check=True,
    )
    before = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    subprocess.run(["git", "-C", str(root), "mv", "omp_configs/old.yml", "omp_configs/new.yml"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=CI", "-c", "user.email=ci@example.invalid",
         "commit", "-qm", "rename overlay"],
        check=True,
    )
    after = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    previous = Path.cwd()
    try:
        os.chdir(root)
        paths = ci_scope.changed_paths(before, after, False)
    finally:
        os.chdir(previous)
    experiments = root / "evals" / "experiments"
    experiments.mkdir(parents=True)
    (experiments / "classes-old.yaml").touch()
    with patch.object(ci_scope, "ROOT", root):
        require(ci_scope.classify(paths) == {"eval"}, "renaming an overlay must detect its stale experiment")
    require(set(paths) == {"omp_configs/old.yml", "omp_configs/new.yml"}, "renames must retain both changed input paths")

# Exercise the exact shell block CI runs, not a second aggregate implementation.
workflow = (SCRIPT.parent.parent / ".github/workflows/ci.yml").read_text()
aggregate_step = workflow.split("      - name: Verify every job succeeded\n", 1)[1]
run_block = aggregate_step.split("        run: |\n", 1)[1]
commands = []
for line in run_block.splitlines():
    if not line.startswith("          "):
        break
    commands.append(line[10:])
require(bool(commands), "CI Success must contain an executable aggregation step")
for results, expected in (("success success", True), ("success failure", False),
                          ("success cancelled", False), ("", False)):
    completed = subprocess.run(
        ["bash", "-c", "\n".join(commands)], env={"RESULTS": results},
        capture_output=True, text=True,
    )
    require((completed.returncode == 0) == expected, f"CI Success aggregation mishandles {results!r}")
print("check-ci-scope: classification and required-status assertions passed")
