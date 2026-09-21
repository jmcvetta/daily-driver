---
name: pr-body
description: >-
  This skill should be used whenever the body of a GitHub pull request is
  being written or revised — including when the user says "rewrite the PR
  description", "update the PR body", "the PR description is thin", or asks
  for more detail in a PR, and including any call Claude makes on its own
  initiative that writes or revises a pull request's body while opening or
  updating one. Supplies the required
  structure: one-line summary, salutation in verse, optional blockers and
  issue-reference sections, executive summary, and engineering detail. A pull
  request whose diff changes the Tofu stack also carries a human-action blocker
  and the `human` label, below. Not for the PR title —
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
- **Blockers**: If the pull request has known merge blockers, list them under
  heading "Blockers" immediately after the salutation. Use one unordered bullet
  per blocker. Link blocking issues; name the concrete action or condition
  required for other blockers. Include human actions, failed required checks,
  unresolved review requirements, and other known conditions. Omit the section
  when there are no blockers.
- **Issues**: If this pull request closes a Github Issue, the reference to it,
  under heading "Issues". Immediately after "Blockers" when that section
  appears, otherwise immediately after the salutation, and above the prose.
  The section below has the format and the rule that decides whether it appears
  at all.
- **Human-Action Blocker**: A pull request whose diff changes the
  infrastructure Tofu stack carries its human-action requirement as a bullet
  in "Blockers", and the pull request itself the `human` label. The section
  below has the wording and the rule that decides when it appears.
- **Executive Summary**: Next, under heading "Summary", give a
  concise high level executive summary of the PR.  If you understand the
  importance of the PR for the larger software development or business
  perspectives, include that positioning.
- **Details**: After the summaries, include as much engineering detail as seems
  fitting.
- **Unopinionated**: This is a short description of the branch, NOT a code
  review. Do NOT do opine on code quality or security.

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
`Issues` section, immediately after `Blockers` when that section appears,
otherwise immediately after the salutation, and above the `Summary`. It leads
because it is the one thing a reader may need before reading the prose: which
issue this closes, answered without scrolling. Use the format shown below:

```
Issues
------

- Closes #123

```

When revising a body that already carries such a section, carry it across. A
rewrite that drops a `Closes #123` silently stops the merge from closing the
issue. A blocking issue listed in `Blockers` is not a closing reference unless
it is also listed here.


Blockers
--------

When a pull request is blocked from merging, add a `Blockers` section directly
below the salutation and above `Issues` or `Summary`. Use an unordered bullet
list with one item per known blocker:

- Link an issue that blocks the pull request, without making it a closing
  reference unless it belongs in `Issues`.
- Name the concrete action or condition required for a human action, failed
  required check, unresolved review requirement, or other merge blocker.

Omit `Blockers` when there are no blockers to report. Do not emit an empty
heading. Preserve valid blockers and closing references when revising a body,
and update the list when the known blocking conditions change.


The human-action blocker
------------------------

A pull request whose diff changes the infrastructure Tofu stack does not
merge on CI green alone: the changes must be applied, and the updated state
committed, before the branch lands — and only a person can run the apply.
Its `Blockers` section carries this bullet:

```
- **Waits on a human apply.** This pull request changes the Tofu stack. The
  changes must be applied and the updated state committed before it merges.
```

The same act labels the pull request `human` — the label #219 adds to the
`issue-labels` standard for work only a person can do — so the list view
says what green CI does not: this one waits on a person. Writing the body
and setting the label are one act. A body that carries the blocker beside a pull request that does not carry
the label states the wait twice, differently, and
one of the two is wrong.

The test is the diff, not the body. When a body is revised and the branch's
changes touch the Tofu stack, a blocker the first write did not know to add is
added then, and the label goes on with it. A blocker once earned is not
removed while the pull request is open: it documents what the merge requires,
and the merge has not happened yet.
