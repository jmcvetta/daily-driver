#!/usr/bin/env python3
"""The provenance block is documented once, and has to actually parse.

`skills/provenance/SKILL.md` defines the trailing block every GitHub write and
commit carries -- `Model:`, `Harness:` and lowercase `session:`, each on its
own line below a `---` rule -- and names the skills that cite it rather than
restate its shape: `pr-body`, `issue-body`, `epic`, `undertake`,
`review-cycle`, `embark`, `stand-down`. Nothing else proves either half: a
skill's prose can say "provenance" without the block it describes ever having
a shape a reader can actually parse, and a citation can silently go missing
from a skill whose body changes for an unrelated reason.

WHAT IT ASSERTS

    A well-formed block parses: `Model:`, `Harness:`, and `session:`, each
    with an actual value, on their own lines under a leading `---`.
    A block missing a line, carrying an empty value, or carrying an unfilled
    template placeholder in place of a value, is rejected rather than
    silently accepted.
    A claim-comment fixture -- the block surrounded by the branch link and
    haiku the way `undertake`'s `Claim the issue` writes it -- is still found
    by the `Model:`/`session:` substring lookup that skill's harness
    references describe, so the shared shape does not break that lookup.
    Every skill `provenance`'s own `SKILL.md` names as a citer names
    `provenance` somewhere in its own `SKILL.md`.

WHAT IT DOES NOT ASSERT

    That any live session actually attaches the block correctly to a real
    GitHub write or commit. This is credential-free, offline, and about the
    shape and the citations, not the behaviour of an agent following them.

No third-party imports, for the reason `check-manifests.py` gives: a
dependency install between a laptop and CI is a place for them to differ.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# The block `skills/provenance/SKILL.md` defines. `search`, not `match`, so it
# is found wherever it falls in a longer comment -- the claim comment's branch
# link comes before it and its haiku after. The space after each colon is
# optional in the pattern (`.*`, not `.+`) so a field left blank -- `session:`
# with nothing after it -- still matches, with an empty capture the `not
# value.strip()` check below rejects explicitly, rather than the whole block
# silently failing to match for an unrelated reason.
BLOCK_RE = re.compile(
    r"^---\nModel: ?(?P<model>.*)\nHarness: ?(?P<harness>.*)\nsession: ?(?P<session>.*)$",
    re.MULTILINE,
)

# A value still carrying the block's own placeholder syntax was copied from
# the template rather than read from anything.
PLACEHOLDER = re.compile(r"[<>]")

# `skills/provenance/SKILL.md`'s own citation list -- design item 6 of #414.
CITING_SKILLS = (
    "pr-body",
    "issue-body",
    "epic",
    "undertake",
    "review-cycle",
    "embark",
    "stand-down",
)


def parse_block(text: str) -> dict[str, str] | None:
    """Return the block's three fields, or None if none is well-formed."""
    match = BLOCK_RE.search(text)
    if not match:
        return None
    fields = match.groupdict()
    if any(not value.strip() or PLACEHOLDER.search(value) for value in fields.values()):
        return None
    return fields


def shape_fixtures() -> list[tuple[str, str, bool]]:
    """(name, text, should_parse) -- one fixture file per acceptance case."""
    return [
        ("well-formed block", "provenance-block-good.txt", True),
        ("block missing a line", "provenance-block-missing-harness.txt", False),
        ("block with a guessed placeholder", "provenance-block-placeholder.txt", False),
        ("block with an empty value", "provenance-block-empty-session.txt", False),
    ]


def main() -> int:
    errors: list[str] = []

    for name, filename, should_parse in shape_fixtures():
        text = (FIXTURES / filename).read_text(encoding="utf-8")
        parsed = parse_block(text)
        if should_parse and parsed is None:
            errors.append(f"{name}: expected to parse, and did not")
        elif not should_parse and parsed is not None:
            errors.append(f"{name}: expected to be rejected, and parsed instead")

    claim_text = (FIXTURES / "provenance-claim-comment.txt").read_text(encoding="utf-8")
    if "Model:" not in claim_text or "session:" not in claim_text:
        errors.append("claim-comment fixture: carries no Model:/session: lines to find")
    else:
        claim = parse_block(claim_text)
        if claim is None:
            errors.append(
                "claim-comment fixture: the block did not parse from inside "
                "the branch link and haiku that surround it"
            )
        elif claim["session"] != "https://claude.ai/code/session_01ABC":
            errors.append(
                f"claim-comment fixture: session parsed as {claim['session']!r}, "
                "not the fixture's own value"
            )

    for name in CITING_SKILLS:
        skill = ROOT / "skills" / name / "SKILL.md"
        if not skill.exists():
            errors.append(f"skills/{name}/SKILL.md: does not exist")
            continue
        if "`provenance`" not in skill.read_text(encoding="utf-8"):
            errors.append(
                f"skills/{name}/SKILL.md: does not cite `provenance`, and "
                "provenance's own SKILL.md names it as a citer"
            )

    if errors:
        print("provenance check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(
        f"provenance block: {len(shape_fixtures())} shape fixtures, "
        f"1 claim-comment fixture, and {len(CITING_SKILLS)} citing skills "
        "all check out"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
