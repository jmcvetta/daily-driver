#!/usr/bin/env python3
"""Check that Omp's documented CI wait uses its supported tool surface.

`github` is optional and disabled by default, so a review-cycle route that
requires `github.run_watch` is not executable in a normal Omp session. The
route instead relies on the essential `hub` process supervisor and `bash` for
its explicit GitHub API reads. This check is offline: it validates that contract
without a GitHub credential, a pull request, or a model.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "omp.md"
SUPPORTED_TOOLS = frozenset({"bash", "hub"})
REQUIRED_CALLS = {
    "hub": ("hub start", "hub wait", "hub stop"),
    "bash": (
        "gh pr checks --watch",
        "/commits/{sha}/check-runs",
        "/commits/{sha}/status",
    ),
}
REQUIRED_RULES = ("timeout: 900", "empty pair is not green", "No `sleep`")


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-review-cycle-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Reject references that need unavailable tools or omit wait invariants."""
    text = REFERENCE.read_text(encoding="utf-8")
    documented_tools = frozenset(REQUIRED_CALLS)
    unsupported = documented_tools - SUPPORTED_TOOLS
    if unsupported:
        fail(f"route names unsupported Omp tools: {', '.join(sorted(unsupported))}")
    if "github.run_watch" in text:
        fail("route names optional github.run_watch")

    missing_calls = [call for calls in REQUIRED_CALLS.values() for call in calls if call not in text]
    if missing_calls:
        fail(f"route omits required calls: {', '.join(missing_calls)}")
    missing_rules = [rule for rule in REQUIRED_RULES if rule not in text]
    if missing_rules:
        fail(f"route omits required wait rules: {', '.join(missing_rules)}")

    print("check-omp-review-cycle-route: Omp CI wait uses supported hub and bash routes")


if __name__ == "__main__":
    main()
