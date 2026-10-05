#!/usr/bin/env python3
"""Reject eval tasks that invoke the metered Anthropic API judge.

`llm_judge` calls Anthropic's API directly. This project does not use metered
Anthropic access, even when an API key or another transport is configured.
Claude judging uses `agent_judge` through the subscription-backed Claude Code
SDK and must run from a Claude Code web or CLI session.

This preflight only inspects task YAML. It never reads credentials or probes
the execution environment. See `evals/README.md` for the execution-session
handoff and the supported route.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - `make check` installs it first
    print(
        "error: PyYAML is required to read task YAML -- it is declared in the"
        " root pyproject.toml's dev group; run 'make check', which runs the"
        f" legs under uv (installed into .venv from uv.lock) ({exc})",
        file=sys.stderr,
    )
    sys.exit(1)


def has_enabled_llm_judge(task: object) -> bool:
    """True if `task` (a parsed task YAML) carries a live `llm_judge` row.

    "Live" means `type: llm_judge` and not explicitly `enabled: false` —
    the same gate `LLMJudgeChecker._check_impl_async` applies before it
    would otherwise call a model.
    """
    if not isinstance(task, dict):
        return False
    criteria = task.get("success_criteria")
    if not isinstance(criteria, list):
        return False
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        if criterion.get("type") == "llm_judge" and criterion.get("enabled", True) is not False:
            return True
    return False


def main(argv: list[str]) -> int:
    if not argv:
        print("evals-preflight: no task files given; nothing to check")
        return 0

    offending: list[tuple[str, str]] = []
    read_errors: list[str] = []
    for arg in argv:
        path = Path(arg)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            read_errors.append(f"{arg}: {exc}")
            continue
        try:
            task = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            read_errors.append(f"{arg}: invalid YAML ({exc})")
            continue
        if has_enabled_llm_judge(task):
            task_id = task.get("task_id") if isinstance(task, dict) else None
            offending.append((arg, task_id or arg))

    if read_errors:
        for error in read_errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            "\nevals-preflight could not read every task file given; fix the "
            "above before running.",
            file=sys.stderr,
        )
        return 1

    if not offending:
        print(f"evals-preflight: no enabled llm_judge criteria in {len(argv)} task file(s)")
        return 0

    print(
        f"error: {len(offending)} row(s) use enabled llm_judge criteria, "
        "which call the metered Anthropic API and are not supported:",
        file=sys.stderr,
    )
    for arg, task_id in offending:
        print(f"  - {task_id} ({arg})", file=sys.stderr)
    print(
        "\nReplace each judge with a suitable subscription-backed "
        "`agent_judge`, then run a Claude-judged evaluation from a Claude "
        "Code web or CLI session. Do not configure a metered API key or "
        "change the backend. See evals/README.md.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
