#!/usr/bin/env python3
"""Assert CI scope classification and required-check aggregation offline."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("ci-scope.py")
spec = importlib.util.spec_from_file_location("ci_scope", SCRIPT)
assert spec and spec.loader
ci_scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci_scope)


def require(condition: bool, message: str) -> None:
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
require(ci_scope.aggregate(["success", "success"]), "successful jobs must report green")
require(not ci_scope.aggregate([]), "a missing upstream result must fail")
require(ci_scope.aggregate(["success", "skipped"]), "intentional group skips must stay green")
require(not ci_scope.aggregate(["failure", "success"]), "a failed applicable group must report red")
print("check-ci-scope: classification and aggregation assertions passed")
