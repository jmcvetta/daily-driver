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

A synthetic case runs first, to show that the check fails on a judge without
the list. Credential-free; reads YAML only.
"""

from __future__ import annotations

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


def main() -> int:
    """Report every judge that can wander, and exit nonzero if there is one."""
    self_test()
    found = [p for path in sorted(TASKS.glob("*/*.yaml")) for p in problems(path)]
    for line in found:
        print(f"check-agent-judges: {line}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
