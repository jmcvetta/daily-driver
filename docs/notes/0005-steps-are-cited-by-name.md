# A step is cited by its name, never by its number

**Status:** decided, 2026-09-07.
**Provenance:** chosen by an agent in
[#86](https://github.com/jmcvetta/daily-driver/pull/86) — the same pull
request as the change it justifies — and ratified by that merge, not by a
separate call from the author.
**Resolves:** [#83](https://github.com/jmcvetta/daily-driver/issues/83).

Three skills lay out a numbered sequence — `undertake`'s eleven steps,
`review-cycle`'s three stages, `session-title`'s four cuts — and files across
the repository cited them by number. Sixty-eight such citations, across eleven
files, twelve of them crossing a file boundary.

A number is positional. Insert a step and every citation of every later step is
wrong, in prose that goes on reading exactly like prose that is right: a stale
`step 7` has no tell. Nothing in `make check` looked at them, and nothing could
have, because there was nothing stable to check them against.

This had already cost. 8354f33 added `Claim the issue` in the middle of
`undertake` and shifted six steps under it; its own commit message records
hand-chasing the two citations that lived in other files. Two were found
because the author went looking. The next insertion had no reason to be as
lucky, and `docs/notes/0001` was already carrying a `stage 2` that nobody had
noticed pointed into `review-cycle`.

## Decided

**Every step in a numbered sequence has a name, and the name is what gets
cited.** `undertake` runs the round between `Open the draft` and
`Ready for review`; `review-cycle`'s round starts at `Review the head`;
`session-title`'s worked examples cut at **Tracker prefix** and **Empty
words**.

**The numbers stay, and do only what they are good at** — ordering. They live
in the sequence table and in the `4 — Cut the branch` prefix on a heading, and
nowhere else. Neither form is a citation, so neither is affected by the rule,
and both go on giving a reader the shape of the sequence at a glance.

**`undertake`'s `Review the head` and `Fix, answer, resolve, push` carry
`review-cycle`'s first two stage names.** They are the same work seen from two
skills. One name for it is what lets either cite it without reaching into the
other's numbering — which is what the two stale citations in 8354f33 were
doing. `undertake`'s `Ready for review` is not part of that overlap: the ready
gate is the caller's, and `review-cycle` disclaims it.

**`scripts/check-step-names.py` enforces it**, as a leg of `make check`. It
flags a sequence noun followed by a number — `step 7`, `stage 2`, `phases 2–4`,
`Rules 1 and 2` — over every Markdown and YAML file git would carry, tracked or
merely not ignored. Its own self-test runs before the scan on every invocation
rather than behind a flag: this check fails silently in the direction that
matters, and a detector that has stopped matching reports a clean repository.

**The scan reads the whole file, not a line at a time.** The prose here is
hard-wrapped at about 78 columns and both halves of what is being looked for
cross that wrap: a citation splits as `at step` / `9 of the sequence`, and so
does a code span, whose stray closing backtick would otherwise pair with the
next opener and blank the prose between them. Not hypothetical either way:
sixty-two lines in the scanned files carry an odd backtick count, and one of
the sixty-eight citations — `review-cycle`'s *"against what stage / 1
reviewed"* — is split by the wrap and is invisible to a line-at-a-time scan.

**A code span is a quotation, not a citation**, and is skipped — as is a
fenced block. The rule has to be written down, and the only way to say what a
bad citation looks like is to write one; this note is the file that does it
most. Backticks are enough of a marker because a citation somebody wrote to be
*followed* is bare prose: all sixty-eight of the ones this check was written
for were, measured by running it over the branch point.

## The escape hatch, and why it is per noun

A numbering this repository does not own cannot be renamed here. `docs/notes/`
0001 and 0002 both cite the phases of
[#35](https://github.com/jmcvetta/daily-driver/issues/35), which are
named in that issue and not in this repository. Those files waive the noun:

```
<!-- step-names: external phase — the phases are issue #35's. -->
```

**Per noun, not per file**, and the reason is the case that made the rule.
`0001` cites #35's phases nine times *and* carried one stale `stage 2` aimed at
`review-cycle`. A file-wide waiver would have covered both and hidden the only
one that was actually broken.

## What was considered and not done

**Renaming without a check.** A convention nothing enforces is a convention
that drifts back one pull request at a time, and this one drifts back
invisibly — which is the entire complaint. The rename alone would have fixed
forty-six citations and prevented none.

**Excluding `docs/` from the check.** Tempting, because the notes are dated
records rather than live instructions. It was the wrong line: `0001`'s stale
`stage 2` was in `docs/notes/`, and an exclusion drawn there would have kept
the one real cross-file bug the check found on its first run.

**Checking that the cited name still exists.** This rule trades a silent
failure for a loud one; it does not remove every silent failure. A step renamed
without its citations leaves them dangling, and nothing here catches that — a
citation is an inline code span, indistinguishable from every other one, so
resolving it against the sequence tables would mean guessing at which spans
are citations. What the rule buys is that the failure now needs someone to
rename a step, rather than merely to insert one anywhere above it.
