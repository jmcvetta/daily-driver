---
name: readme
description: >-
  This skill should be used whenever a README is being written or revised —
  including when the user says "/readme", "write a README", "update the
  README", "document this directory", "the README is stale", or asks what
  belongs in one, and on the agent's own initiative before creating or editing
  any `README.md`, at the root of a repository or inside a directory within
  one. Supplies the two questions a README answers, the shape that answers
  them, the rule that decides how long one runs, and the list of what must
  never appear in one —
  work log, project history, specifications, test numbers, rejected ideas —
  with the place each of those belongs instead. Not for a pull request body,
  which is `pr-body`, and not for a design note, a planning document or
  anything else under `docs/`.
---

# README

A README is read by someone who has just arrived, does not know what this is,
and wants to use it. It answers two questions and then stops:

- **What is this?**
- **How do I use it?**

Everything else in the repository is written for someone who already stayed.
A README that makes the reader work for those two answers has failed, however
good the prose in the way is.


The shape
=========

```markdown
# name

One or two sentences: what this is, and what it is for.

## Install        <- only where getting it takes a command

## Usage          <- the shortest thing that does the job, and its output

## Configuration  <- only where the thing will not run without it

## Links          <- one line each, into the docs that carry the detail

## Licence        <- one line, and the file it points at
```

Heading names can follow the language's convention — `Getting started`,
`Quick start`, `Options`. The order is what matters: what it is, then how to
get it, then how to use it. A section with nothing to say is deleted, not
filled.

Show, do not describe. One command a reader can paste beats a paragraph
explaining what the command would do.


The test
========

Every sentence earns its place by one question:

> Does a reader who wants to **use** this thing need this sentence in order to
> use it?

Where the answer is no, cut the sentence. Not shorten it, not move it lower —
cut it. The question is asked of the draft you have just written, before it is
saved.

**Legal text is outside the test.** A licence, a warranty disclaimer, a terms
notice, an attribution a licence obliges: a reader does not need any of them in
order to use the thing, and every one of them stays. They are in the README
because it is where a reader looks for them.


Never in a README
=================

Each of these has somewhere it belongs, and none of those places is here.

| Not in the README | Where it goes |
| ----------------- | ------------- |
| The work log — what was done today, in what order | The commit messages |
| Project history, what this replaced, how it was built | The changelog, and git |
| Why it was built this way; options weighed and rejected | A design note under `docs/` |
| Specifications, requirements, acceptance criteria | The issue, or `docs/` |
| Test results, coverage figures, benchmark numbers | CI, where they are re-measured |
| Ideas had and then dropped | Nowhere. They are gone |
| Train of thought, arguing with yourself, digressions on arcana found on the way | Nowhere |
| Roadmap, plans, "coming soon" | The issue tracker |
| A wall of badges | Keep the build status, drop the rest |

Two of these are worth naming twice, because they are the ones that read as
helpful while they are being written. **Provenance** — how this came to exist,
what it used to be — is interesting to the author and to nobody else.
**Hedging** — "note that", "it is worth mentioning", an apology for a rough
edge — is a paragraph that says nothing a reader can act on.


Length
======

A README is as long as its two answers need, and not a line longer. There is
no line count to hit, and no line count to stay under: a tool with one command
is finished in six lines, and a library with four entry points is not padded
to match nor squeezed to fit.

So length is a **symptom**, read rather than budgeted. A README that feels long
is long because of one of these, and each has its own fix:

- **A section that answers neither question.** Cut it, and check the table
  above for where it belongs.
- **Detail a reader needs later, not now** — every flag, every configuration
  key, the API surface. It moves into `docs/` or the reference, and the README
  links to it in one line.
- **Prose doing a code block's work.** Replace the paragraph with the command.
- **The same thing said twice** in the summary and again under a heading. Keep
  the one that is closer to where the reader acts.

Where none of those applies, the length is the subject's, and it stays.


A README that is not an arrival README
======================================

This skill is written for the README a reader arrives at. A directory inside a
repository sometimes carries one that is deliberately something else — an
attic saying what is kept and why, a test suite explaining the harness it
chose, an infrastructure directory recording what its state file is for. That
is rationale, and the table above sends rationale to `docs/`.

**Where the repository has made that choice on purpose, it wins.** Say what
the README is carrying and leave it, rather than cutting a record somebody
put there. The table decides what goes into a README nobody has decided about;
it does not overturn a decision already made.


Revising one that already exists
================================

- **Cut before you add.** A stale README is nearly always too long, and the
  request to update it is nearly always an invitation to make it longer.
- **Keep the author's voice.** Where a heading and its content still work,
  leave them alone. A README rewritten to say the same thing differently is a
  diff nobody can review.
- **Check the commands, and do not run the dangerous ones.** A command that no
  longer works is worse than no README, because the reader trusts it. Run the
  ones that are read-only or confined to the checkout. A command that installs,
  deploys, publishes, or changes anything outside it is checked by reading —
  the flag still exists, the target still resolves, the path is still there —
  because the constitution decides that one, and it says a dangerous command
  runs in a sandbox or not at all. Where only running it would settle the
  question, say so and leave it to the user.
