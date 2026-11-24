---
name: pr
description: >-
  Read for `/pr` before validation, proposing or changing CI enforcement, or
  opening or updating a pull request. The policy applies without an issue or
  PR, and reading it starts neither. For the current branch, triggers include
  opening, raising, or updating a PR and any agent-initiated call before
  creating one or updating one beyond its title or body. Supplies the branch
  guard, the existing-PR check, draft state, ongoing base maintenance, and the
  issue-reference call; title is `pr-title` and body is `pr-body`.
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
readiness. Before resuming PR work, take the harness's catch-up look. Answer
direct user questions first under the constitution; a catch-up look is not a
prerequisite for answering from known evidence.

`undertake` invokes this maintenance and retains its review, ready gate, and
first-readiness report. Direct PR work does not inherit those issue-specific
steps. A clean base merge earns no review round; a conflict resolution or
other content change follows `review-cycle`.


Github Issues
-------------

If this PR was created to fix/implement a Github Issue, reference it. Deciding
that there is an issue to reference is this skill's call; the section's format
and placement in the body belong to `pr-body`.


Validation and completion
=========================

This policy applies to ordinary repository work as well as pull requests.
Reading it does not start PR creation.

Completion requires observed success from all remaining applicable project
gates: tests, linters, formatters, and validation. Expected success is not evidence.

Push and read CI. Local project checks require a specific failure being repaired
or an isolated bounded experiment with disposable inputs and a stated concrete
question. Whole-project checks and routine assurance are not experiments.
Experiments grant no production access, dangerous operations, live third-party
fixtures, paid model runs, broader triggers, or recurring checks.

Never bypass or remove validation for cost or effort. Only explicit owner
direction may reduce CI scope or spending: disclose lost coverage; never claim
removed or unrun checks passed, hide failures, weaken security, or skip required
tests. The constitution owns the application-test and script-execution contract.


Recurring CI costs
==================

This policy applies before proposing or changing CI enforcement. Read it at
that action, not only when opening a PR. Reading the policy does not authorize
opening a PR.

New CI checks add recurring execution, review, failure-triage and maintenance
costs. Consider the check's value, runtime, trigger frequency and external
cost. Prefer established validation and regression coverage; avoid duplicate
checks and work that is gratuitously long or runs more often than needed.
Routine tests for approved code, bug-fix regressions, typechecks, necessary
builds and coverage integrated through existing project patterns are part of
delivery, not a separate approval process.

Obtain owner approval before adding a material new paid service or other
clearly significant recurring spend. Ordinary repository validation does not
need separate cost approval. Do not run paid benchmarks merely to estimate a
proposal's cost.

Use existing project patterns and appropriate timeouts and change selection.
Do not create redundant enforcement when existing checks cover the need. Keep
established project gates and required coverage intact: never disable or
weaken checks or security, hide failures, or treat unrun checks as passed.
Tests of testing machinery remain prohibited unless that machinery is the
shipped product.

**CI is the gate** means use established project gates. It does not instruct
you to invent a new gate for each task.
