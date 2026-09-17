#!/usr/bin/env python3
"""Every harness names a concrete `Verify the fix delta` route.

`Verify the fix delta` asks for one reviewer given the reviewed SHA, the
current SHA, the findings and their dispositions. Omp supplies that natively.
Claude Code and Codex used to declare the pass unavailable "on the measured
surface" and stop there, because `/code-review` and `codex exec review` take
a diff target and nothing else — which meant `undertake` could not reach
`Ready for review` unattended on either harness after any review that found
something. #283 replaced the blanket notice with a briefed-subagent route on
both: the `Agent` tool on Claude Code, the `multi_agent_v1` dispatch on Codex.

This credential-free check holds that route in place. It fails if either
harness reference reverts to a blanket unavailability notice, if the brief
loses a required element, or if `outcome: unavailable` stops being a
reachable result of a dispatch that genuinely fails — the fix-delta pass is
not required to always succeed, only to have a concrete route to attempt.

It also holds the restated `SKILL.md` rule and its citations: a briefed
subagent is a legitimate reviewer, so the "never a bare subagent" phrasing
this issue retired must not come back.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "review-cycle" / "SKILL.md"
CLAUDE_REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "claude.md"
CODEX_REFERENCE = ROOT / "skills" / "review-cycle" / "references" / "codex.md"
UNDERTAKE_SKILL = ROOT / "skills" / "undertake" / "SKILL.md"
EMBARK_CODEX_REFERENCE = ROOT / "skills" / "embark" / "references" / "codex.md"

# The brief `Verify the fix delta` requires, restated in each harness route
# that dispatches a subagent for it. Every element must survive, worded or
# not, because a route missing one is the unbriefed dispatch the rule forbids.
REQUIRED_BRIEF_ELEMENTS = (
    "pull request",
    "base branch",
    "full-review SHA",
    "current SHA",
    "original findings",
    "dispositions",
    "pass number",
    "three-dot content",
    "must not perform a full-PR audit",
)

REQUIRED_DISPATCH_CALLS = {
    CLAUDE_REFERENCE: ("`Agent` tool",),
    CODEX_REFERENCE: ("`multi_agent_v1` dispatch",),
}

# The unavailability notice this issue retired. Its return means someone
# reintroduced a blanket "cannot verify on this harness" stop instead of the
# briefed-subagent route.
FORBIDDEN_BLANKET_NOTICES = (
    "Unavailable on the measured surface.",
)

# The rule phrasing #283 retired, and where it must not reappear. A subagent
# is not disqualified for being a subagent; only an unbriefed one is.
FORBIDDEN_RULE_PHRASINGS = {
    SKILL: ("never a bare subagent",),
    UNDERTAKE_SKILL: ("a reviewer, not a subagent",),
    CODEX_REFERENCE: ("the bare subagent `SKILL.md` refuses",),
    EMBARK_CODEX_REFERENCE: ("a named surface rather than a bare subagent",),
}


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-review-cycle-fix-delta-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_all(path: Path, text: str, phrases: tuple[str, ...]) -> None:
    """Fail naming every phrase from `phrases` missing from `text`."""
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        relative = path.relative_to(ROOT)
        fail(f"{relative} is missing required text: {', '.join(missing)}")


def require_none(path: Path, text: str, phrases: tuple[str, ...]) -> None:
    """Fail naming every phrase from `phrases` still present in `text`."""
    present = [phrase for phrase in phrases if phrase in text]
    if present:
        relative = path.relative_to(ROOT)
        fail(f"{relative} retains retired phrasing: {', '.join(present)}")


def main() -> None:
    """Assert the fix-delta route and its brief on Claude Code and Codex."""
    texts = {
        path: path.read_text(encoding="utf-8")
        for path in (
            SKILL,
            CLAUDE_REFERENCE,
            CODEX_REFERENCE,
            UNDERTAKE_SKILL,
            EMBARK_CODEX_REFERENCE,
        )
    }

    for reference in (CLAUDE_REFERENCE, CODEX_REFERENCE):
        text = texts[reference]
        require_none(reference, text, FORBIDDEN_BLANKET_NOTICES)
        require_all(reference, text, REQUIRED_BRIEF_ELEMENTS)
        require_all(reference, text, REQUIRED_DISPATCH_CALLS[reference])
        if "outcome: unavailable" not in text:
            fail(
                f"{reference.relative_to(ROOT)} drops the reachable "
                "`outcome: unavailable` result"
            )
        if "outcome: <clear|defects|incomplete|unavailable>" not in text:
            fail(
                f"{reference.relative_to(ROOT)} no longer lets the pass "
                "record a real outcome"
            )

    for path, phrasings in FORBIDDEN_RULE_PHRASINGS.items():
        require_none(path, texts[path], phrasings)

    print(
        "check-review-cycle-fix-delta-route: Claude Code and Codex both name "
        "a briefed-subagent fix-delta route"
    )


if __name__ == "__main__":
    main()
