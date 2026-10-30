---
name: pr
description: >-
  This skill should be used whenever a GitHub pull request is being opened for
  the current branch, or an existing one is being brought up to date as a
  whole — including when the user says "/pr", "open a PR", "create a PR",
  "raise a pull request", or "update the PR", and including any call the agent
  makes on its own initiative before creating a pull request, or updating an
  existing pull request beyond its title or body alone. Supplies the branch
  guard, the existing-PR check, draft state, ongoing base-branch maintenance,
  and the call on whether there is an issue to reference; the title comes
  from `pr-title` and the body, issue reference included, from `pr-body`.
---

# PR Workflow

Open the GitHub PR for the current feature branch, or update the one that is
already open.

This skill is the orchestrator. The title convention lives in `pr-title` and
the body structure in `pr-body`; invoke each rather than restating it, so that
a later edit to a title or a body follows the same rules whether or not it
arrived through here.

The GitHub calls behind each step below differ by harness.
[`references/claude.md`](references/claude.md),
[`references/omp.md`](references/omp.md) and
[`references/codex.md`](references/codex.md) name them, operation by
operation, in the order this file raises them.


Branch
------

- If the current branch is `master`:
  1. Stop working
  2. Emit an error
  3. Await input


Already Existing PR
-------------------

First check whether a PR already exists for the current remote push head — see
the reference files for the lookup. For ordinary and resume work, that is the
current task branch. For the verified primary-held designation mapping, it is
the designated branch resolved from the local execution branch's upstream.
If a PR exists, update that PR rather than creating another.

- Update both title and body of existing PR — the title under `pr-title`,
  which does not rewrite a type this session did not write


Title
-----

Follow `pr-title`.


Body
----

Follow `pr-body`.


Initial State
-------------

- Open the PR as a draft

Keep it current
---------------

**Every PR the agent opens gets ongoing base-branch maintenance**, including
drafts and direct PR work outside `undertake`. Start after opening the PR,
before ending this workflow. Updating an existing PR reuses its watch or
starts a missing one; reaching ready never starts a second watch. No issue,
claim, or undertaking milestone is required.

Use the active harness reference's currency checkpoint and continuation route.
Read the PR's actual base rather than assuming `master`. Merge that base into
the head with the harness's server-side update-branch call, never a rebase or
force-push. The call also settles draft-masked or indeterminate currency.

Check every two minutes where the harness supports durable continuation.
Reuse one pending wake or running watch per PR. A run in flight on the current
head defers the merge, so currency maintenance does not keep restarting CI.
A clean merge needs current-head CI, not another review of an unchanged diff.

Stop automatic updates on a conflict. Resolve only a plain mechanical
conflict; ask when resolution requires a behavior decision. After resolution
is pushed, resume maintenance and use `review-cycle` for the changed content.
Never merge the PR itself or change its readiness just because currency is
settled.

The watch ends on merge, close, or the user's instruction to stop. Cancel its
actor before any stop-time push and do not restart it on a stale wake. A new
user instruction may resume it. Report a failed watch or unavailable durable
route and the actual owner-resume requirement; do not claim unattended
maintenance on a harness that cannot provide it.

After the merge
---------------

Read CI for the resulting head through `review-cycle`'s wait rules. A head
change invalidates earlier CI evidence. Fix failed checks; report unavailable
logs as an evidence blocker, never green. Pending checks use its bounded wait.
A process can merge without an agent turn but cannot assess review or
readiness. Every owner turn returning to the PR takes the harness's catch-up
look first.

`undertake` invokes this maintenance and retains its review, ready gate, and
first-readiness report. Direct PR work does not inherit those issue-specific
steps. A clean base merge earns no review round; a conflict resolution or
other content change follows `review-cycle`.


Github Issues
-------------

If this PR was created to fix/implement a Github Issue, reference it. Deciding
that there is an issue to reference is this skill's call; the section's format
and placement in the body belong to `pr-body`.
