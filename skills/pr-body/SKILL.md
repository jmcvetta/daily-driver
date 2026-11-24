---
name: pr-body
description: >-
  Use whenever a GitHub pull request body is written or revised, including on
  the agent's own initiative while opening or updating one. Supplies the
  required structure: summary, salutation in verse, optional blockers and
  issue-reference sections, executive summary, and reviewer-relevant detail,
  including the Tofu apply-and-state blocker and PR `human` label while that
  requirement is outstanding. Not for the title (`pr-title`).
---

# PR Body

The body of a pull request, whether it is being opened or rewritten. In order:

- **One-Line Summary**: PR should begin with a very concise, single line summary of
  the PR. This summary will be visible in certain Github web UI components;
  there is a strict 85 character limit.
- **Salutation**: A poetic summary. Immediately after the one-line summary,
  separated by a blank line. A brief poem, in classical style, conveying the
  gist of the PR. Formatted in italics.
- **Blockers**: Include only merge prerequisites that belong in durable
  human-facing metadata: human actions, Tofu apply/state requirements, linked
  issue dependencies, and non-obvious external prerequisites. Do not mirror
  live CI/check or review state in the body; GitHub owns that state. Read it
  from GitHub when assessing readiness. Omit the section when there are no
  durable blockers.
- **Issues**: If this pull request closes a Github Issue, the reference to it,
  under heading "Issues". Immediately after "Blockers" when that section
  appears, otherwise immediately after the salutation, and above the prose.
  The section below has the format and the rule that decides whether it appears
  at all.
- **Human-Action Blocker**: A pull request whose diff changes the
  infrastructure Tofu stack — the OpenTofu configuration, not the provider
  lockfile alone — carries its apply-and-state requirement as a `Blockers`
  bullet and the PR `human` label while the action is outstanding. The
  section below has the wording and the rule that decides when it appears.
- **Executive Summary**: Next, under heading "Summary", give a
  concise high level executive summary of the PR.  If you understand the
  importance of the PR for the larger software development or business
  perspectives, include that positioning.
- **Details**: After the summaries, the engineering detail a reviewer needs —
  how the change was made, how it was verified, and the material risk or
  uncertainty — said once. What the opening line and `Summary` already say is
  not repeated here.
  Keep the change, its verification evidence, material risk or uncertainty, and
  outstanding human approvals visible. Do not duplicate live check or review
  state; read it from GitHub instead. Do not publish private source quotes or
  sensitive local details.
  For a specification-backed task, identify the document path, exact delivered
  specification commit and requirement IDs, and distinguish evidence of
  delivery from unverified allocation.
- **Unopinionated**: This is a short description of the branch, NOT a code
  review. Do NOT do opine on code quality or security.
- **Provenance**: The active harness route attaches `provenance`'s block. For
  Omp GitHub writes, the wrapper appends it; keep the authored body free of a
  new block. Other routes place and retain it as `provenance` defines.

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

When the pull request has durable merge prerequisites that belong in its body,
add a `Blockers` section directly below the salutation and above `Issues` or
`Summary`. Use an unordered bullet list, one item per prerequisite:

- Link an issue that blocks the pull request, without making it a closing
  reference unless it belongs in `Issues`.
- Name the concrete human action, Tofu apply-and-state requirement, or
  non-obvious external prerequisite.

CI/check results and review status are live GitHub state, not body blockers.
They can still prevent readiness, but the body must not echo routine failed
checks or unresolved review requirements.
Preserve valid blockers and closing references when revising a body. Update
the section only when a durable prerequisite changes. `undertake` owns
investigation, operational escalation and revalidation on resume; use current
evidence rather than an old body, label, missing tool or infrastructure diff
to decide whether a human contribution is still owed.

A current agent's missing credential, network route, tool or permission is not
by itself evidence that the work is human-only. Where verification remains
blocked by this session's capabilities, state the concrete prerequisite and
the authorized handoff or resumption path without describing a device class as
the requirement. `undertake` decides whether a human contribution is actually
needed and whether the PR is ready; only an outstanding human action earns a
human-action blocker or the PR `human` label.

When current evidence says an existing PR `human` label is no longer
warranted, remove it through the selected harness route. Apply and verify this
label change separately from the body edit; preserve unrelated labels. The
body write does not change labels, so never report a label change from the
body update alone.


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

**The stack is the configuration, not the lockfile.** The stack is what the
OpenTofu configuration declares: the `.tf` files under `infra/` and the
resources they define. A diff that touches only the provider lockfile —
`.terraform.lock.hcl`, wherever it sits — records which provider builds the
next init selects for a configuration it does not change. It applies nothing
and alters no stack resource, so it is not a change to the infrastructure Tofu
stack: it carries no apply-and-state blocker and no PR `human` label. A diff
that changes a `.tf` file under `infra/` is a stack change, and the blocker and
label go on together while the apply remains owed.
