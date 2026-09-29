#!/usr/bin/env python3
"""Every write that carries verse says so, and its verse breaks nothing.

Verse sits on a fixed set of agent writes, each owned by one skill: the epic
body (`epic`), the muster roll and the delivered epic-close comment
(`embark`), the epic's stand-down comment (`stand-down`), and the comment
that closes an issue as not planned (`issue`). Each owner states its form and
points at `HAIKU.md` for the italic line shape. A rule deleted from one of
those files in an unrelated edit raises no error anywhere else, so this check
is what notices.

On the comments, the verse goes last, after `provenance`'s block. That block
is found by a pattern search, and a resumed `embark` reads the roll's rows,
so verse placed after them must not hide either.

WHAT IT ASSERTS

    Each owner's `SKILL.md` names its verse form and links `HAIKU.md`.
    Each comment fixture -- muster roll, epic close, stand-down, not-planned
    close -- still parses with `check-provenance.py`'s block pattern, carries
    its verse after the block, and writes every verse line in italics.

WHAT IT DOES NOT ASSERT

    That a live session writes the verse, or writes it well. This is
    credential-free and offline, about the rules and the shape.

No third-party imports, for the reason `check-manifests.py` gives.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"

# `check-provenance.py` has a hyphen in its name, so it is loaded by path
# rather than imported, and its pattern is reused rather than copied.
_spec = importlib.util.spec_from_file_location(
    "check_provenance", Path(__file__).resolve().parent / "check-provenance.py"
)
check_provenance = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_provenance)

# (owner skill, the form its SKILL.md must name)
OWNERS = (
    ("epic", "ballad quatrain"),
    ("embark", "sailing couplet"),
    ("embark", "homecoming verse"),
    ("stand-down", "envoi"),
    ("issue", "elegy"),
)

COMMENT_FIXTURES = (
    "verse-muster-roll.txt",
    "verse-epic-close.txt",
    "verse-stand-down.txt",
    "verse-not-planned.txt",
)


def verse_errors(name: str, text: str) -> list[str]:
    """Problems with the verse and block in one comment fixture."""
    match = check_provenance.BLOCK_RE.search(text)
    if match is None or check_provenance.parse_block(text) is None:
        return [f"{name}: the provenance block does not parse"]
    verse = [line for line in text[match.end():].splitlines() if line.strip()]
    if not verse:
        return [f"{name}: no verse after the provenance block"]
    return [
        f"{name}: verse line is not italicised: {line!r}"
        for line in verse
        if not (line.startswith("*") and line.endswith("*") and len(line) > 2)
    ]


def main() -> int:
    errors: list[str] = []

    for skill, form in OWNERS:
        text = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
        if form not in text.lower():
            errors.append(f"skills/{skill}/SKILL.md: does not name its {form}")
        if "HAIKU.md" not in text:
            errors.append(f"skills/{skill}/SKILL.md: does not link HAIKU.md")

    for name in COMMENT_FIXTURES:
        errors += verse_errors(name, (FIXTURES / name).read_text(encoding="utf-8"))

    # The negative case: prose after the block is not verse.
    bad = (FIXTURES / "verse-not-italic.txt").read_text(encoding="utf-8")
    if not verse_errors("verse-not-italic.txt", bad):
        errors.append("verse-not-italic.txt: expected to be rejected, and passed")

    for error in errors:
        print(error, file=sys.stderr)
    if errors:
        return 1
    print("verse: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
