#!/usr/bin/env python3
"""Keep every `agent_judge` in `evals/tasks/` from wandering off the transcript.

An `agent_judge` grades the transcript pasted into its prompt. It needs no tool
but the `submit_verdict` tool `coder_eval` adds itself. `allowed_tools: []` does
not take tools away: it only says which tools run without a permission prompt.
Every built-in tool stays visible, so a judge can try to `Read` or `cat` the
sandbox, be refused, run out of turns, and never call `submit_verdict`. The
criterion then scores 0.0 with an error, and the replicate reads as a policy
failure. Measured on #279's comparison: three of five candidate replicates of
`answer-selects-from-findings` failed that way.

`disallowed_tools` is what removes a tool from the judge's context. Removing
all built-in tools with the SDK's `tools: []` would be stronger, but
`coder_eval` 0.11.6 refuses `tools` in `sdk_options`, so this list is the
narrowest route it allows. See docs/notes/0014 for the other two settings.

WHAT IT ASSERTS

    No criterion under `evals/tasks/` has `type: llm_judge`: it calls the
    metered Anthropic API, which this repository does not use (docs/notes/0014).

    Every `agent_judge` criterion, in `success_criteria` and
    `post_failure_criteria`, carries an `agent` block with
    `allowed_tools: []`, `permission_mode: default`, and a `disallowed_tools`
    list that contains every name in `DENIED`.

    Every judge route in `evals/judges/` stays transcript-only (issue #542). The
    Claude route is the denylist above. The Omp route has no denylist to read, so
    this builds its real command line and asserts it runs `--no-tools` with every
    discovery switch off, and that its judge prompt tells the judge to treat the
    transcript as untrusted. Each definition must load, exactly one may be the
    `default`, and a `validated` judge must carry a committed calibration result
    that met its declared rule against the current labels.

A synthetic case runs first, to show that the check fails on a judge without
the list. Credential-free; reads YAML only.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - `make check` installs it first
    print(f"error: PyYAML is required; run 'make check' ({exc})", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "evals" / "tasks"

# The built-in tools a judge could use to read, run, fetch, edit or delegate.
DENIED = frozenset(
    {
        "Bash",
        "Read",
        "Glob",
        "Grep",
        "Write",
        "Edit",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "Task",
        "Agent",
        "Skill",
        "Monitor",
    }
)


def problems(path: Path) -> list[str]:
    """Each way a judge in the task file at `path` can reach past its transcript."""
    data = yaml.safe_load(path.read_text()) or {}
    found = []
    criteria = (data.get("success_criteria") or []) + (data.get("post_failure_criteria") or [])
    for index, criterion in enumerate(criteria):
        where = f"{path.relative_to(path.parents[1])}: criterion {index}"
        if criterion.get("type") == "llm_judge":
            found.append(f"{where}: llm_judge is refused; use agent_judge")
        if criterion.get("type") != "agent_judge":
            continue
        agent = criterion.get("agent") or {}
        if agent.get("allowed_tools") != []:
            found.append(f"{where}: allowed_tools is not []")
        if agent.get("permission_mode") != "default":
            found.append(f"{where}: permission_mode is not default")
        missing = DENIED - set(agent.get("disallowed_tools") or [])
        if missing:
            found.append(f"{where}: disallowed_tools lacks {', '.join(sorted(missing))}")
    return found


def self_test() -> None:
    """A judge with no denylist, or an `llm_judge`, must be reported, or the check proves nothing."""
    bare = {
        "success_criteria": [
            {"type": "agent_judge", "agent": {"allowed_tools": [], "permission_mode": "default"}}
        ]
    }
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "suite" / "row.yaml"
        path.parent.mkdir()
        path.write_text(yaml.safe_dump(bare))
        if not problems(path):
            sys.exit("check-agent-judges: self-test failed: a judge without disallowed_tools passed")
        path.write_text(yaml.safe_dump({"success_criteria": [{"type": "llm_judge"}]}))
        if not problems(path):
            sys.exit("check-agent-judges: self-test failed: an llm_judge row passed")


OMP_ISOLATION_FLAGS = (
    "--no-tools",
    "--no-extensions",
    "--no-skills",
    "--no-rules",
    "--no-lsp",
    "--no-pty",
    "--no-session",
)


def load_evals_judge():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("evals_judge", ROOT / "scripts" / "evals-judge.py")
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.modules["evals_judge"] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def judge_route_problems() -> list[str]:
    """Each way a selectable judge in `evals/judges/` can fail to stay transcript-only or honest."""
    ej = load_evals_judge()
    found: list[str] = []
    judges = []
    for path in sorted((ROOT / "evals" / "judges").glob("*.yaml")):
        try:
            judges.append(ej.load_judge(path))
        except ej.JudgeError as err:
            found.append(err.message)
    if sum(1 for j in judges if j.status == "default") != 1:
        found.append("evals/judges: exactly one judge must have status: default")
    omp_judges = [j for j in judges if j.route == "omp"]
    if not omp_judges:
        found.append("evals/judges: no omp judge defines the non-Claude route")
    for judge in omp_judges:
        argv = ej.omp_argv("omp", judge, ej.JUDGE_SYSTEM_PROMPT, "u")
        missing = [flag for flag in OMP_ISOLATION_FLAGS if flag not in argv]
        if missing:
            found.append(f"{judge.judge_id}: omp command line lacks {', '.join(missing)}")
        if any(a.startswith("--tools") for a in argv):
            found.append(f"{judge.judge_id}: omp command line grants a tool list")
        if judge.status == "validated":
            if not judge.calibration:
                found.append(f"{judge.judge_id}: validated without a calibration result")
                continue
            result_path = ROOT / "evals" / "judges" / judge.calibration
            if not result_path.is_file():
                found.append(f"{judge.judge_id}: calibration result {judge.calibration} is missing")
                continue
            result = json.loads(result_path.read_text())
            labels = yaml.safe_load((ROOT / "evals" / "judges" / "calibration" / "labels.yaml").read_text())
            if not result.get("met_acceptance_rule"):
                found.append(f"{judge.judge_id}: validated but its calibration did not meet the acceptance rule")
            if result.get("labels_sha") != ej.sha(labels):
                found.append(f"{judge.judge_id}: calibration was measured against different labels than are committed")
            if result.get("judge", {}).get("model_requested") != judge.model:
                found.append(f"{judge.judge_id}: calibration was measured on a different model")
    if "UNTRUSTED" not in ej.JUDGE_SYSTEM_PROMPT:
        found.append("omp judge system prompt does not mark the transcript untrusted")
    return found


def main() -> int:
    """Report every judge that can wander, and exit nonzero if there is one."""
    self_test()
    found = [p for path in sorted(TASKS.glob("*/*.yaml")) for p in problems(path)]
    found += judge_route_problems()
    for line in found:
        print(f"check-agent-judges: {line}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
