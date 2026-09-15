#!/usr/bin/env python3
"""Check that Omp's documented CI wait uses its supported tool surface.

`github` is optional and disabled by default, so a review-cycle route that
requires `github.run_watch` is not executable in a normal Omp session. The
route instead relies on the essential `hub` process supervisor and `bash` for
its explicit GitHub API reads. This check is offline: it validates that contract
without a GitHub credential, a pull request, or a model.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "omp.md"
SKILL = ROOT / "skills" / "review-cycle" / "SKILL.md"
SUPPORTED_TOOLS = frozenset({"bash", "hub"})
TOOL_FOR_COMMAND = {"gh": "bash", "hub": "hub"}
REQUIRED_CALLS = (
    "hub start",
    "hub wait",
    "hub stop",
    "gh pr checks --watch",
    "/commits/{sha}/check-runs",
    "/commits/{sha}/status",
)
REQUIRED_RULES = ("timeout: 900", "registration stop", "No `sleep`")


def documented_wait_tools(text: str) -> frozenset[str]:
    """Map command spans in the wait table to their Omp tool names."""
    section = text.partition("The wait\n========")[2].partition("There is no durable wake")[0]
    table = "\n".join(line for line in section.splitlines() if line.startswith("|"))
    commands = re.findall(r"`([^`]+)`", table)
    if not commands:
        fail("route has no wait call table")
    return frozenset(
        TOOL_FOR_COMMAND.get(command.split(maxsplit=1)[0], command.split(maxsplit=1)[0])
        for command in commands
    )


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-review-cycle-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Reject references that need unavailable tools or omit wait invariants."""
    text = REFERENCE.read_text(encoding="utf-8")
    if "partial watch that cannot observe registration" not in SKILL.read_text(encoding="utf-8"):
        fail("shared review-cycle rule omits the partial-watch exception")
    documented_tools = documented_wait_tools(text)
    unsupported = documented_tools - SUPPORTED_TOOLS
    if unsupported:
        fail(f"route names unsupported Omp tools: {', '.join(sorted(unsupported))}")
    if "github.run_watch" in text:
        fail("route names optional github.run_watch")

    missing_calls = [call for call in REQUIRED_CALLS if call not in text]
    if missing_calls:
        fail(f"route omits required calls: {', '.join(missing_calls)}")
    missing_rules = [rule for rule in REQUIRED_RULES if rule not in text]
    if missing_rules:
        fail(f"route omits required wait rules: {', '.join(missing_rules)}")

    print("check-omp-review-cycle-route: Omp CI wait uses supported hub and bash routes")


if __name__ == "__main__":
    main()
