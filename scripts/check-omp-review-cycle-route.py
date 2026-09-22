#!/usr/bin/env python3
"""Check Omp's documented durable watcher contract.

`github` is optional and disabled by default. The route therefore uses the
essential `hub` process supervisor and `bash` for explicit GitHub API reads.
This credential-free check holds the persistent watcher lifecycle, bounded
cleanup, owner-scoped completion replay, and the boundary between process
durability and agent resumption. It also holds `undertake`'s detached
`keep-current` loop route, which note 0022 moved the `Keep it current` merge
into.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REVIEW_REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "omp.md"
UNDERTAKE_REFERENCE = ROOT / "skills" / "undertake" / "references" / "omp.md"
EMBARK_REFERENCE = ROOT / "skills" / "embark" / "references" / "omp.md"
SKILL = ROOT / "skills" / "review-cycle" / "SKILL.md"
SUPPORTED_TOOLS = frozenset({"bash", "hub"})
TOOL_FOR_COMMAND = {"gh": "bash", "hub": "hub"}
REQUIRED_CALLS = (
    "hub start",
    "hub wait",
    "hub stop",
    "hub describe",
    "gh pr checks --watch",
    "/commits/{sha}/check-runs",
    "/commits/{sha}/status",
)
REQUIRED_REVIEW_RULES = (
    "timeout: 900",
    "registration stop",
    "No `sleep`",
    "set `persist: true`",
    "`detached: true` goes further",
    "Do not use it here",
)
REQUIRED_UNDERTAKE_RULES = (
    "`pr-keep-current.sh`",
    "`hub start`",
    "`hub stop`",
    "`keep-current-<number>`",
    "Thirty consecutive",
)
COMMON_DURABILITY_RULES = (
    "`daily_driver_schedule`",
    "`persist: true`",
    "`detached: true`",
    "owner-scoped",
    "pending",
    "owning session",
    "reconnect",
)
NO_AUTONOMY_RULES = {
    REVIEW_REFERENCE: "does not launch or resume an Omp session",
    UNDERTAKE_REFERENCE: "does not launch or resume the agent",
    EMBARK_REFERENCE: "cannot reopen or resume a terminated orchestrator",
}
FORBIDDEN_CLAIMS = (
    "There is no durable wake",
    "missing durable wake",
    "no durable timer",
)


def documented_wait_tools(text: str) -> frozenset[str]:
    """Map command spans in the wait table to their Omp tool names."""
    section = text.partition("The wait\n========")[2].partition("Process durability is not session resumption")[0]
    table = "\n".join(line for line in section.splitlines() if line.startswith("|"))
    commands = re.findall(r"`([^`]+)`", table)
    if not commands:
        fail("route has no wait call table")
    return frozenset(
        TOOL_FOR_COMMAND.get(command.split(maxsplit=1)[0], command.split(maxsplit=1)[0])
        for command in commands
    )


def normalized(text: str) -> str:
    """Collapse prose whitespace so checks do not depend on line wrapping."""
    return " ".join(text.split())


def require_rules(path: Path, text: str, rules: tuple[str, ...]) -> None:
    """Require each durable watcher rule in one Omp route."""
    prose = normalized(text)
    missing = [rule for rule in rules if normalized(rule) not in prose]
    if missing:
        relative = path.relative_to(ROOT)
        fail(f"{relative} omits required rules: {', '.join(missing)}")


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-review-cycle-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Reject unsupported tools, weak watcher lifecycle, and false autonomy."""
    references = {
        path: path.read_text(encoding="utf-8")
        for path in (REVIEW_REFERENCE, UNDERTAKE_REFERENCE, EMBARK_REFERENCE)
    }
    review_text = references[REVIEW_REFERENCE]
    if "partial watch that cannot observe registration" not in SKILL.read_text(encoding="utf-8"):
        fail("shared review-cycle rule omits the partial-watch exception")
    documented_tools = documented_wait_tools(review_text)
    unsupported = documented_tools - SUPPORTED_TOOLS
    if unsupported:
        fail(f"route names unsupported Omp tools: {', '.join(sorted(unsupported))}")
    if "github.run_watch" in review_text:
        fail("route names optional github.run_watch")

    missing_calls = [call for call in REQUIRED_CALLS if call not in review_text]
    if missing_calls:
        fail(f"route omits required calls: {', '.join(missing_calls)}")
    require_rules(REVIEW_REFERENCE, review_text, REQUIRED_REVIEW_RULES)

    for path, text in references.items():
        require_rules(path, text, COMMON_DURABILITY_RULES)
        require_rules(path, text, (NO_AUTONOMY_RULES[path],))
        stale = [claim for claim in FORBIDDEN_CLAIMS if claim in normalized(text)]
        if stale:
            relative = path.relative_to(ROOT)
            fail(f"{relative} retains false durability claims: {', '.join(stale)}")
    require_rules(
        UNDERTAKE_REFERENCE, references[UNDERTAKE_REFERENCE], REQUIRED_UNDERTAKE_RULES
    )

    print(
        "check-omp-review-cycle-route: Omp routes preserve durable bounded "
        "watchers without claiming autonomous session work"
    )


if __name__ == "__main__":
    main()
