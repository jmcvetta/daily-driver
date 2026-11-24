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

Prefer the narrowest relevant local check that answers the current engineering
question. Use focused tests or checks during iteration, and avoid repeated
full-project runs after small changes when focused evidence covers the change.
Run broader local validation at meaningful checkpoints when its cost is
justified. A failure reproduction or experiment is not required. Read
[`docs/testing-standards.md`](../../docs/testing-standards.md) when writing,
changing, or reviewing tests.

Push and read CI. Never bypass or remove validation for cost or effort. Only
explicit owner direction may reduce CI scope or spending: disclose lost
coverage; never claim removed or unrun checks passed, hide failures, weaken
security, or skip required tests.


Recurring CI costs
==================

This policy applies before proposing or changing CI enforcement. Read it at
that action, not only when opening a PR. Reading the policy does not authorize
opening a PR.

New CI checks add recurring execution, review, failure-triage and maintenance
costs. More checks are not inherently better. Prefer established checks and
necessary regression coverage. Routine CI integration for approved code is
part of delivery, not an additional enforcement proposal.

Before classifying a command as routine integration, inspect its effective
execution chain: wrapper targets, prerequisite targets, and invoked scripts,
including their material operations. A target named `check` or `test`, path-
filtered execution, or placement in an existing job does not establish that
its contents are ordinary validation. Use repository source and documented
commands; do not run a build, smoke environment, or paid benchmark merely to
discover its cost.

Select new features, apps, or packages for the repository's established test,
typecheck, build, and coverage commands; add them to existing path or package
selection; and follow established per-component job patterns without separate
approval. This remains routine integration when it adds recurring runner time
or instantiates a package-specific job required by the repository's convention.
Adding package membership to an existing package matrix does not add a matrix
dimension; a new dimension adds a factor such as an operating system, runtime
version, or browser. Ordinary tests, regression coverage, typechecks, necessary
builds, and coverage remain routine integration.

An umbrella command must not silently bring newly introduced image packaging
or builds, or runtime smoke environments, into recurring CI under this
exemption. When that work is not already authorized or required by the
established validation contract, surface it as the named expansion and obtain
approval before adding it. Approval of a feature, trial, or green CI alone
does not authorize that expansion. Existing explicitly authorized container
validation proceeds without renewed approval. Docker alone is not grounds to
stop.

For the expansion, use the existing **Failure caught**, **Existing coverage
gap**, and **Recurring cost** fields. Name the effective build and smoke
operations, selected trigger frequency, runner/matrix footprint, expected
runtime, external charges, and replacement where applicable. Distinguish
estimates from measurements and state unknowns. Never treat combined
build-and-smoke timing as build-only time or infer charges from runtime.

Do not add a job, workflow, tool, standalone check, or matrix dimension when
existing tooling can catch the defect; placing a standalone check inside an
existing job does not change this. Before proposing additional enforcement,
name the concrete failure it catches and the gap in existing coverage. Extra
confidence, best practice, or completeness alone is not a reason. Keep
enforcement proportional to the task; do not make a task-local problem
repository-wide or keep a one-time migration check permanently without a
recurring need.

Paid services, broader triggers, additional matrix dimensions, new kinds of
enforcement, and redundant or standalone checks beyond normal implementation
validation need user approval for the named expansion, not general feature or
green-CI approval. Do not ask again when authorized. Ordinary tests for
approved new or changed code, bug-fix regression coverage, and their routine
integration in established CI need no separate approval.
Proposals use only these three short fields: **Failure caught**, **Existing
coverage gap**, and **Recurring cost**. State trigger frequency,
runner/matrix footprint, expected runtime, external charges and what the
check replaces, where applicable. Mark unknowns and distinguish estimates
from measurements. Do not run paid benchmarks to fill these fields.

For authorized additions, use appropriate timeouts, safe cancellation of
superseded runs and relevant-change selection that preserves coverage and
required-status reporting. Avoid duplicate enforcement. When a new check
replaces an old one, remove the obsolete check in the same change without
losing required coverage.

This policy does not permit skipping required tests, weakening security,
hiding failures or disabling established gates to save cost. Tests of testing
machinery remain prohibited unless that machinery is the shipped product.

**CI is the gate** means use established project gates. It does not instruct
you to invent a new gate for each task.