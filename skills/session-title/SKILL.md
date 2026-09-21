---
name: session-title
description: >-
  This skill should be used whenever the title of the current Claude session
  is being set or revised — including when the user says "/session-title",
  "set the session title", "rename this session", "name this session", or
  "that session title is wrong", and on Claude's own initiative when work on a
  GitHub issue begins, when the session's subject changes materially, or on
  any call to the harness's session-title tool. Supplies the
  character budget a title is written to for the Claude mobile list, and
  the three forms that title may take. Not the title of a pull request —
  that is `pr-title`.
---

# Session title

The name this session carries in the harness's own session list. It is read in
a column of a dozen siblings, at a glance — on a phone in the Claude lists, in
a picker in a terminal elsewhere, and in one harness it is an address as well
as a label. That is the whole design constraint.

**The call that sets the title is per harness, and it lives beside this
file.** [`references/claude.md`](references/claude.md) is the route for
Claude Code, [`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before the first call.


Budget: 40 characters
=====================

Every harness's title tool accepts far more than forty. Forty is this skill's
own cap, chosen rather than measured — short enough to survive the mobile list
at the width it is read on, long enough to say which session this is. A
measurement, when someone takes one, is what may move it. The cap is this
skill's and not the tool's, so it holds on every harness, whatever that
harness's own limit turns out to be.

- **Hard cap, 40 characters**, counting the whole string, `#123 ` prefix
  included. Past that the title is cut where the renderer reaches rather than
  where a writer would have chosen; shortening it here keeps the choice.
- **No ellipsis.** A title trimmed to fit reads as a title. One ending in `…`
  reads as a title that failed.


Working on an issue
===================

    #{number} {shortened issue title}

The number leads because it is the identifier — the half that must survive any
further clipping, and the half a reader matches against a branch name or a
browser tab.

Shortening is deletion, one word or phrase at a time, in this order —
re-checking the fit after each and stopping the moment the whole thing fits.
Capitalise whatever word ends up first. Each cut is named, and the name is how
it is cited below: the numbers order them and nothing else.

1. **Tracker prefix.** Drop a leading prefix written for the tracker rather
   than the reader: a Conventional Commits type (`feat:`, `fix(api):`), or a
   label (`New skill:`, `Bug:`, `RFC:`).
2. **Trailing qualifier.** Drop a parenthesis, or a clause after a dash.
3. **Empty words.** Drop the words carrying no information, wherever they sit,
   least informative first: articles, then auxiliary verbs, then prepositions,
   then the adjectives the title survives without.
4. **Words from the end.** Only then cut whole words from the end, never part
   of one. Where the last word is the noun naming the subject — in an issue
   title it is as often last as first, and where two compete it is the one the
   work is on, the rightmost only failing that — keep it and cut the word
   before it instead.

A title that still overruns at `#{number} {noun}` has nothing left to give.
Stop there and let it overrun: the identifier and the subject are the two
things worth more than the budget.

Issue #40, *"New skill: set the Claude session title"*, needs **Tracker
prefix** alone: `#40 Set the Claude session title` — 32 characters.

Issue #212, *"fix(storage): retry with exponential backoff for the S3 upload
client"*, loses its type prefix to **Tracker prefix**, then `the`, `with`,
`for` and finally the adjective `exponential` to **Empty words**, fitting at
35: `#212 Retry backoff S3 upload client`. **Words from the end** never runs,
and `client` — the noun the title is about — survives because of it.


Orchestrating an epic
=====================

The session a fleet is watched from — the orchestrator `embark` runs an epic
from — takes a form of its own, the fleet notice ahead of the epic's number:

    ⛵ EPIC #{number} {shortened epic title}

The notice is the point: a list of five running sessions is one orchestrator
among the task sessions it opened, and the notice is what tells them apart at
a glance. The budget counts the whole string, notice included. The epic title
is shortened by the same cuts `Working on an issue` defines, over whatever
room the notice leaves.


Not working on an issue
=======================

A short noun phrase naming what the session is actually doing.

- **Nouns, not narration.** `Flaky auth test triage`, not
  `Working on fixing the flaky auth test`.
- **Specific over generic.** `Postgres pool leak`, not `Debugging`.
- **No repository name.** The session records its own source; spending a
  quarter of the budget restating it buys nothing.


Setting it
==========

Setting the title is the harness's own call — each harness names its own
surface, and how many calls that takes differs between them. The reference
file for the harness in use gives the exact path.

Where no such surface exists — a harness that has none, or one whose surface
this session has not been offered — there is no way to set the title from
here: say so and stop, rather than reaching for a substitute. Whether the
harness in use is such a case is the reference file's answer, not a guess made
here.


When to set it
==============

Once, as soon as the subject is known: the turn work actually starts, not the
turn the session opens. Again when the subject genuinely changes — issue #40
closed, issue #41 begun.

Not on every commit, and not to record progress. A title that keeps moving is
one nobody reads twice.
