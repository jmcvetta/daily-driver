---
name: pr-body
description: >-
  This skill should be used whenever the body of a GitHub pull request is
  being written or revised — including when the user says "rewrite the PR
  description", "update the PR body", "the PR description is thin", or asks
  for more detail in a PR, and including any call Claude makes on its own
  initiative that writes or revises a pull request's body while opening or
  updating one. Supplies the required
  structure: one-line summary, salutation in verse, the issue-reference
  section, executive summary, and concise, reviewer-relevant detail. A pull
  request whose diff changes the Tofu stack also carries the human-action
  notice and the `human` label, below. Not for the PR title —
  that is `pr-title`.
---

# PR Body

The body of a pull request, whether it is being opened or rewritten. In order:

- **One-Line Summary**: PR should begin with a very concise, single line summary of
  the PR. This summary will be visible in certain Github web UI components;
  there is a strict 85 character limit.
- **Salutation**: A poetic summary. Immediately after the one-line summary,
  separated by a blank line. A brief poem, in classical style, conveying the
  gist of the PR. Formatted in italics.
- **Issues**: If this pull request closes a Github Issue, the reference to it,
  under heading "Issues". Immediately after the salutation, separated by a
  blank line, where a reader meets it before the prose. The section below has
  the format and the rule that decides whether it appears at all.
- **Human-Action Notice**: A pull request whose diff changes the
  infrastructure Tofu stack carries a prominent notice that its changes
  must be applied, and the updated state committed, before it merges —
  and the pull request itself the `human` label. The section below has
  the wording, the placement, and the rule that decides when it appears.
- **Executive Summary**: Next, under heading "Summary", give a
  concise high level executive summary of the PR.  If you understand the
  importance of the PR for the larger software development or business
  perspectives, include that positioning.
- **Details**: After the summaries, the engineering detail a reviewer needs —
  how the change was made, how it was verified, and the material risk or
  uncertainty. Concise enough to read once through.
- **Unopinionated**: This is a short description of the branch, NOT a code
  review. Do NOT do opine on code quality or security.

**The body is human-facing, and the constitution's audience rule governs it.**
Edit it silently before it is written: prefer too terse over too verbose,
keep every essential fact — the change, the reason, the verification
evidence, the material risk — and say each one once. Length is not detail;
a reviewer's one read-through is the budget.

**The opening line, `Summary` and `Details` are a ladder, and each rung says
what the rung above it did not.** They are not three chances to describe the
change, which is the failure this body shape invites: an agent writes the
change into the opening line, writes it again as the summary, and writes it a
third time as the first detail bullet. Measured, that restatement is the one
thing a drafted body does wrong most often, so it is worth naming by rung:

- The **opening line** names *what* changed, in one line.
- **`Summary`** gives *why* — the reason it was wanted and what it means for
  the reader. It does not re-describe the change; the line above did that.
- **`Details`** gives *how*, and the evidence: mechanism, verification,
  risk. It does not re-describe the change or restate the reason; the two
  rungs above did those.

The test is mechanical, and it is worth applying before the body is set: take
any one fact in the body and find every place it is stated. More than one
place, and every place but the right rung comes out.

**The call that sets the body is per harness, and it lives beside this
file.** [`references/claude.md`](references/claude.md) is the route for
Claude Code, [`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex. Read the one for
the harness in use before the first call.

Opening a pull request is the `pr` skill's job. When the body is being written
as part of opening one, follow `pr` as well, for the branch guard, the
existing-PR check and draft state.


Issues
------

If the pull request fixes or implements a Github Issue, the body carries an
`Issues` section, immediately after the salutation and above the `Summary`.
It leads because it is the one thing a reader may need before reading any
prose: which issue this closes, answered without scrolling. Use the format
shown below:

```
Issues
------

- Closes #123

```

When revising a body that already carries such a section, carry it across. A
rewrite that drops a `Closes #123` silently stops the merge from closing the
issue.


The human-action notice
-----------------------

A pull request whose diff changes the infrastructure Tofu stack does not
merge on CI green alone: the changes must be applied, and the updated state
committed, before the branch lands — and only a person can run the apply.
The body of such a pull request carries a prominent notice of that —
immediately after the `Issues` section when there is one, otherwise
immediately after the salutation, and in either case above the `Summary`,
where a reader meets it before any prose:

```
> **Waits on a human apply.** This pull request changes the Tofu stack. The
> changes must be applied and the updated state committed before it merges.
```

The same act labels the pull request `human` — the label #219 adds to the
`issue-labels` standard for work only a person can do — so the list view
says what green CI does not: this one waits on a person. Writing the body
and setting the label are one act. A body that carries the notice beside a
pull request that does not carry the label states the wait twice,
differently, and one of the two is wrong.

The test is the diff, not the body. When a body is revised and the branch's
changes touch the Tofu stack, a notice the first write did not know to add
is added then, and the label goes on with it. A notice once earned is not
removed while the pull request is open: it documents what the merge
requires, and the merge has not happened yet.
