#!/usr/bin/env python3
"""A step is cited by its name, never by its number.

Several files here lay out a numbered sequence -- `undertake`'s twelve steps,
`review-cycle`'s four stages, `session-title`'s four cuts -- and other files
cite them. A number is positional: insert one step and every citation of every
later step is silently wrong, in prose that still reads exactly like prose that
is right. It has already cost once. 8354f33 added a step in the middle of
`undertake` and had to hand-chase two citations in other files; nothing would
have caught the one that got missed.

So the numbers stay for reading -- in the sequence table, and as the `4 — Cut
the branch` prefix on a heading -- and every *reference* names the step
instead. A name survives the insertion that renumbers everything after it.
That is the rule this script enforces, and
`docs/notes/0005-steps-are-cited-by-name.md` is the decision behind it.

WHAT IT FLAGS

    A sequence noun followed by a number, in prose: step 7, stage 2, phases
    2-4, Rules 1 and 2. Nothing else -- a heading written `7 — Open the draft`
    and a table row written `| 7 |` do not match, which is what leaves the
    numbers their reading job.

    Code is not prose, so a code span or a fenced block is skipped. The rule
    itself has to be written down somewhere, and the only way to say what a
    bad citation looks like is to write one; this file, the note and the
    skills that state the convention all quote the bad form in backticks, and
    a quotation is not a citation. A real citation is bare prose -- every one
    of the sixty-eight at the branch point was, measured.

    A *fenced* block, specifically. An indented code block is not recognised,
    because telling one from an ordinary list continuation needs the list
    context, and a parser guessing at that would blind the check in the silent
    direction. Fence an example instead, or write it in backticks -- which is
    what every example here does.

    The scan runs over the whole file rather than line by line, because the
    prose here is hard-wrapped at about 78 columns and both halves of the
    thing being looked for cross that wrap. A citation can be split -- "at
    step" ending one line and "9 of the sequence" starting the next -- and so
    can a code span, whose stray closing backtick would otherwise pair with
    the next opener and blank out the prose between them.

WHAT IT DOES NOT CATCH

    That the name a citation uses still exists. This rule trades a silent
    failure for a loud one; it does not remove every silent failure, and a
    step renamed without its citations is still nobody's error. See the note.

THE ESCAPE HATCH

    A numbering this repository does not own cannot be renamed here. A file
    exempts one noun, with its reason, in a comment at the left margin:

        <!-- step-names: external phase — the phases are issue #35's. -->

    The exemption is per noun, not per file: `docs/notes/0001` cites issue
    #35's phases throughout and still had a stale `stage 2` pointing at
    `review-cycle`, which is exactly the citation a file-wide waiver would have
    hidden. And it counts only at the left margin and outside a fenced block,
    so that a file *documenting* the hatch -- an indented example, a fenced one
    -- does not thereby take it. The note did, until a review caught it.

WHY THE SELF-TEST RUNS EVERY TIME

    This check fails silently in the direction that matters. A detector that
    has stopped matching reports a clean repository, which is
    indistinguishable from a clean repository -- so a suite that could be
    skipped, or left un-run on a laptop, would not be protecting anything.
    `selftest` is therefore not a flag: it runs before the scan on every
    invocation, costs microseconds, and there is no way to reach the scan
    without it. It raises rather than asserting, because `python3 -O` strips
    an assert and would leave that promise false.

No third-party imports: this runs from a Makefile on a laptop and from CI, and
a dependency install between the two is a place for them to differ.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The nouns a numbered sequence is written with here. Each is checked in the
# singular and the plural, so "step 3" and "Steps 3 through 9" both land.
NOUNS = ("step", "stage", "phase", "rule", "item")

# Prose only. Skill and agent bodies are Markdown; eval cases carry their
# prose in YAML `description` blocks, and a stale citation there is a stale
# citation in the thing that documents what the suite measures.
SUFFIXES = (".md", ".yaml", ".yml")

# Generated from commit messages by release-please. Rewriting it would falsify
# the record, and nothing reads it as an instruction.
SKIP = ("CHANGELOG.md",)

# Not a plain `\s+`: the noun and its number are routinely split by the
# 78-column wrap, so the gap must cross a newline -- but not a blank line, or a
# heading ending in `The rule` above a numbered list reads as a citation.
GAP = r"(?:[^\S\n]|\n(?!\s*\n))+"
CITATION = re.compile(rf"\b({'|'.join(NOUNS)})s?{GAP}\d", re.IGNORECASE)

# A code span, which may itself be wrapped. A blank line ends one in Markdown,
# and refusing to cross one is what keeps an unbalanced backtick from
# swallowing the rest of the file.
CODE_SPAN = re.compile(r"`(?:[^`\n]|\n(?!\s*\n))*`")

FENCE = re.compile(r"^\s*(```|~~~)")

# `<!-- step-names: external phase — reason -->`, at the left margin. The noun
# is what the waiver covers; the trailing text is the reason, required so that
# a waiver has to say whose numbering it is deferring to.
WAIVER = re.compile(
    rf"^<!--\s*step-names:\s*external\s+({'|'.join(NOUNS)})s?\b"
    r"[^\S\n]*(?P<reason>[^\n>]*)",
    re.IGNORECASE,
)

# What the patterns above are asserted to do, on every run. The flagged half is
# the register the repository actually writes citations in, wraps included; the
# clean half is everything the numbers are still allowed to do, and is the half
# that would break first if the pattern were widened carelessly.
FLAGGED = (
    "runs this round between its step 7",
    "Steps 3 through 9 shift up by one",
    "starts at stage 2",
    "Phase 1 runs over the `[judgment]` items",
    "Rules 1 and 2 are one rule",
    "needs step 1 alone",
    "the numbers in #35 phases 3-4",
    # Split by the wrap, both ways round.
    "the round is answered at step\n9 of the sequence.",
    "a `Fix, answer, resolve,\npush` that follows step 2 of the round",
)
CLEAN = (
    "| 7 | `Open the draft` | `pr` |",
    "7 — Open the draft",
    "runs this round between its `Open the draft` and `Ready for review` steps",
    "1. **Tracker prefix.** Drop a leading prefix",
    "twelve steps, and this skill is the order they run in",
    "step by step, without stopping",
    # A blank line ends the reach: a heading above a numbered list is not one.
    "## The rule\n\n1. First",
    "the whole of the rule\n\n2. Second",
    # Quotations of the bad form, which the rule has to be able to write down.
    "flags a sequence noun followed by a number -- `step 7`, `stage 2`",
    "carried a `stage 2` aimed at `review-cycle`",
    # A fenced block is code, wherever the fence sits.
    "```\nRuns at step 3 of the sequence.\n```",
)


class SelfTestFailed(Exception):
    """The detector no longer does what this file says it does."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SelfTestFailed(message)


def blanked(match: re.Match[str]) -> str:
    """The match, replaced by spaces, with its line structure kept."""
    return "".join("\n" if char == "\n" else " " for char in match.group(0))


def prose(text: str) -> str:
    """The text with fenced blocks and code spans blanked out.

    Line-for-line with the input, so a match's offset still gives the line the
    citation is on.
    """
    lines = []
    fenced = False
    for line in text.split("\n"):
        if FENCE.match(line):
            fenced = not fenced
            lines.append("")
            continue
        lines.append("" if fenced else line)
    return CODE_SPAN.sub(blanked, "\n".join(lines))


def waived(text: str) -> set[str]:
    """The nouns this file has waived, lowercased and singular.

    Read from the file's prose, so that an example of the hatch -- indented,
    or fenced -- is not one.
    """
    nouns = set()
    for line in prose(text).split("\n"):
        match = WAIVER.match(line)
        if match and match.group("reason").strip(" -—–:"):
            nouns.add(match.group(1).lower().rstrip("s"))
    return nouns


def citations(text: str) -> list[tuple[int, str]]:
    """Every numbered citation in the text, as (line number, what was said)."""
    body = prose(text)
    return [
        (body.count("\n", 0, match.start()) + 1, match.group(0).strip())
        for match in CITATION.finditer(body)
        if match.group(1).lower() not in waived(text)
    ]


def selftest() -> None:
    for text in FLAGGED:
        require(bool(citations(text)), f"not flagged: {text!r}")
    for text in CLEAN:
        require(not citations(text), f"wrongly flagged: {text!r}")

    # The line number survives both the wrap and the blanking.
    require(
        citations("filler\nthe round is answered at step\n9.") == [(2, "step\n9")],
        "wrong line number for a wrapped citation",
    )
    # A wrapped code span does not blank the prose after its closing backtick.
    require(
        bool(citations("a `Fix, answer,\nresolve` and then step 2 of the round")),
        "a wrapped code span swallowed the prose after it",
    )

    require(
        waived("<!-- step-names: external phase — issue #35's. -->") == {"phase"},
        "a well-formed waiver was not read",
    )
    require(
        waived("<!-- step-names: external phases — issue #35's. -->") == {"phase"},
        "a plural waiver was not read",
    )
    # A waiver covers the noun it names and no other.
    require(
        "stage" not in waived("<!-- step-names: external phase — #35's. -->"),
        "a waiver covered a noun it does not name",
    )
    # A waiver with no reason is not a waiver.
    require(
        waived("<!-- step-names: external phase -->") == set(),
        "a waiver with no reason was honoured",
    )
    # An example of the hatch is not the hatch: indented, or fenced.
    require(
        waived("    <!-- step-names: external phase — the reason. -->") == set(),
        "an indented example activated the waiver",
    )
    require(
        waived("```\n<!-- step-names: external phase — the reason. -->\n```") == set(),
        "a fenced example activated the waiver",
    )


def scannable() -> list[Path]:
    """Every file git would carry, tracked or merely not ignored.

    `--others` is not decoration. A file is untracked until it is staged, and
    checking only what is tracked means a new one is invisible on the laptop
    and flagged for the first time by CI, after the push. Measured: it is how
    the note documenting this very rule first went out red.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        {
            ROOT / name
            for name in out.split("\0")
            if name and name.endswith(SUFFIXES) and name not in SKIP
        }
    )


def main() -> int:
    selftest()

    errors: list[str] = []
    # A file can be in the index and gone from the tree -- deleted, or halfway
    # through a rename -- and a traceback is a worse answer than skipping it.
    files = [path for path in scannable() if path.is_file()]
    for path in files:
        where = path.relative_to(ROOT)
        for line, said in citations(path.read_text(encoding="utf-8")):
            said = " ".join(said.split())
            errors.append(
                f"{where}:{line}: {said!r} cites a step by number; name it instead"
            )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        print(
            "\nSteps are cited by name so that inserting one does not "
            "invalidate every\nlater citation. See "
            "docs/notes/0005-steps-are-cited-by-name.md.",
            file=sys.stderr,
        )
        return 1
    print(f"steps are cited by name; {len(files)} file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
