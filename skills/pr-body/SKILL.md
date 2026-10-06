---
name: pr-body
description: >-
  This skill should be used whenever the body of a GitHub pull request is
  being written or revised — including when the user says "rewrite the PR
  description", "update the PR body", "the PR description is thin", or asks
  for more detail in a PR, and including any call the agent makes on its own
  initiative that writes or revises a pull request's body while opening or
  updating one. Supplies the required
  structure: one-line summary, salutation in verse, optional blockers and
  issue-reference sections, executive summary, and reviewer-relevant detail.
  A pull request whose diff changes the Tofu stack carries an apply-and-state
  blocker and the PR `human` label only while that requirement is outstanding.
  `undertake` owns operational escalation and its evidence; this skill
  publishes that decision and maintains its visible PR state. Not for the PR
  title — that is `pr-title`.
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
  infrastructure Tofu stack carries its apply-and-state requirement as a
  `Blockers` bullet and the PR `human` label while the action is outstanding.
  The section below has the wording and the rule that decides when it appears.
- **Executive Summary**: Next, under heading "Summary", give a
  concise high level executive summary of the PR.  If you understand the
  importance of the PR for the larger software development or business
  perspectives, include that positioning.
- **Details**: After the summaries, the engineering detail a reviewer needs —
  how the change was made, how it was verified, and the material risk or
  uncertainty — said once. What the opening line and `Summary` already say is
  not repeated here.
- **Unopinionated**: This is a short description of the branch, NOT a code
  review. Do NOT do opine on code quality or security.
- **Provenance**: Last, below all of the above, `provenance`'s block — the
  model, harness and session that wrote the body — placed and read the way
  that skill defines. A rewrite of a body someone else wrote adds a second
  block beneath the first rather than replacing it, per `provenance`'s own
  rule.

**The body is human-facing, and the constitution's audience rule governs
it.** Keep every essential fact — the change, the reason, the verification
evidence, the material risk — and say each one once. Length is not detail.

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

heading. Preserve valid blockers and closing references when revising a body,
and update the list when the known blocking conditions change. `undertake`
owns investigation, operational escalation, and revalidation on resume;
publish its current evidence rather than infer inability from an old body,
label, missing tool, or infrastructure diff.

A current agent's missing credential, network route, tool or permission is not
by itself evidence that the work is human-only. Where verification remains
blocked by this session's capabilities, state the concrete prerequisite and
the authorized handoff or resumption path without describing a device class as
the requirement. `undertake` decides whether a human contribution is actually
needed and whether the PR is ready; only an outstanding human action earns a
human-action blocker or the PR `human` label.

Changing body text does not change PR labels. Apply the matching label
operation through the selected harness route and verify it succeeds. On Omp,
remove a cleared human blocker with `gh pr edit <N> --remove-label human`.
This is a separate write from editing the body. Preserve unrelated labels.
Never report a label change based on body content alone.


The human-action blocker
------------------------

A pull request whose diff changes the infrastructure Tofu stack must have the
changes applied and the updated state committed before the branch lands. Only
a person can run the apply. While that requirement is outstanding, its
`Blockers` section carries this bullet:

```
- **Waits on a human apply.** This pull request changes the Tofu stack. The
  changes must be applied and the updated state committed before it merges.
```

The PR `human` label accompanies that blocker while the apply-and-state
requirement is outstanding; it is a temporary PR state, not the issue
`human` kind from `issue-labels`. Add the blocker and label together. On
resume, `undertake` revalidates the actual dependency against current evidence.
When the apply and updated-state commit are present, remove this blocker and
the PR `human` label; keep any other valid blocker and unrelated label. The
fact that the diff still contains Tofu changes does not make a satisfied
requirement outstanding again.

The test is the diff plus the current evidence of whether the action remains
owed. When a body is revised, add a missing apply blocker if its requirement
is still outstanding. Do not retain a blocker solely because it was present
before: a stale blocker misstates the merge condition just as a missing one
does.
