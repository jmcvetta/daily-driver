# The guard refuses what it cannot read

**Status:** decided, 2026-09-18.

**Observed.** The Omp worktree guard's shell recognizer was reviewed four
times. Each round found fail-open holes, and each round's fix opened more:

| Round | Fixed | Introduced |
| --- | --- | --- |
| `949df5b` | 3 | 4 |
| `c0ce600` | 8 | 2, plus one inconsistency |
| `e548cd3` | 5 | 2 |

Every one was the same defect. A character scanner decided that a construct was
inert when bash would execute it: here-documents, `cd` in a subshell, an
arithmetic `<<`, function bodies, a stale function-body flag, a command
substitution nested in arithmetic. Six holes, one shape.

## Why it kept happening

The direction of proof. The recognizer asked whether a command **was**
dangerous. Answering that question requires understanding all of bash, and
every construct the scanner had not met yet resolved to "allow". So each new
piece of syntax was a silent hole, and the only way to find one was for a
reviewer to think of it.

A fifth round would have fixed the two holes then known and introduced more. The
bug list was not the problem; the question was.

## Decided

**The recognizer either enumerates every command a shell call will run, or says
it could not, and what it cannot enumerate is refused.**

Three consequences, and the first is the one that matters:

- **A construct nobody anticipated now denies rather than allows.** The class
  of defect does not disappear — it becomes a visible false positive with an
  obvious repair instead of a silent hole nobody sees.

- **Opacity is where commands hide, so nothing is opaque.** Command
  substitution, arithmetic, process substitution and subshells are all
  parenthesized, so they are tokenized like any other command and emitted as
  groups: a `cd` inside one is seen, and stops applying where the group closes.
  This is *less* code than making them opaque was, which is the usual sign that
  a design was fighting itself.

- **Unknown beats stale.** A `cd` form the walker does not recognize leaves the
  working directory unknown, not unchanged. A branch move whose directory is
  unknown cannot be placed, and an unplaceable mutation was already refused.

**The cost is accepted, not minimised.** `eval "$script"`, `"$PYTHON" -m
pytest`, an unterminated quote — all refused, wherever they run. The primary
checkout is meant to be read-only for agents, so a false positive there costs
the model one rewritten command; a false negative costs the user their
checkout. Where the two are not symmetric, the guard leans the cheap way.

## What it does not claim

The guard reads shell commands. It does not audit programs. A `make`, a
`python3 script.py`, a shell script — any of them can reach the primary
checkout, and nothing in the recognizer would see it. Only the `task-worktree`
rule stops that, and the guard is the execution-time backstop for the cases it
*can* read, not a sandbox.

Stating the boundary is part of the decision. A guard that overstates itself is
how six holes stayed open while four reviews reported the code correct.

## Proved, not asserted

`scripts/check-omp-guard-differential.mjs` is the evidence. It runs each command
shape for real under bash in a throwaway repository and compares the guard's
verdict against whether the primary checkout actually moved, asserting one
direction only:

    the guard allowed it  =>  the primary checkout did not change

The pre-inversion guard allows 28 of the 56 shapes to move the primary. The
inverted one allows none. Every one of the six historical holes is among them,
which is the point: that harness would have caught all six at once, and it is
now a leg of `make check`.

A recognizer asserted correct by the person who wrote it is how this file came
to be needed. This one is measured against bash.
