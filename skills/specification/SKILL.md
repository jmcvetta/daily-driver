---
name: specification
description: >-
  Use when an operator wants to agree executable acceptance scenarios
  collaboratively, or when an issue of kind `specification` is handed over.
  Interactive work, not an unattended implementation assignment.
---

# Specification

A specification is an agreed executable contract for intended behavior and
acceptance, not a project plan. Work interactively with the operator; do not
use `undertake` or `embark` to dispatch a specification issue unattended.
Small tasks with adequate observable acceptance and verification stay on the
ordinary task path without specification or ATDD ceremony.

## Collaborate

1. Read the implementation task, its references and relevant repository
   context. Apply `issue-labels`, `issue-body` and `issue-deps` to issue kind,
   body and edges. A separate interactive `specification` issue is optional;
   use `issue` when one is needed. It carries no implementation model class.
   Keep questions, research references, alternatives and decisions on the
   task or specification issue; use research issues for bounded investigations.
2. Investigate and answer questions the repository can answer. Apply
   `judgement-call`: choose ordinary engineering details, explain genuine
   tradeoffs, and ask the operator only for unresolved intent or product
   decisions. An agent can research, explain, draft and edit; the issue is not
   `human` merely because the operator must decide or agree.
3. Establish or adopt the implementation task branch through `task-worktree`,
   and keep scenario authoring and implementation on that branch. Invoke
   `atdd` when a supported TypeScript repository lacks its acceptance harness.
   Write concise executable scenarios and iterate with the operator. Apply
   `provenance` and the normal change workflow. An unresolved decision that
   prevents implementation keeps the affected behavior unready.
4. Obtain explicit operator agreement to the scenarios and record the
   agreement, its scope and any exclusions on the issue. Independent review
   is not product agreement, and silence is not agreement. Agreement to a
   decomposition is separate; neither decision implies the other.
5. When a separate specification issue is used, record its implementation
   handoff: implementation task issue, task branch, scenario paths, and
   explicit exclusions or allocated behavior where applicable. Complete the
   specification issue once agreement and that handoff are recorded; do not
   wait for implementation or merge. If specification and implementation
   share one task issue, record agreement there without creating a second
   issue or handoff comment. The implementation task remains open for delivery.
   Rejection or abandonment follows the existing issue disposition rules.

## Executable scenarios

Scenarios own intended behavior and acceptance. Use observable outcomes,
meaningful examples, constraints and edge cases; keep product non-goals and
allocation or exclusions explicit on the issue. Bindings and fixtures must
express the agreed behavior through real product interfaces and assertions,
not silently replace it. `atdd` owns supported harness setup and execution;
the feature supplies its own scenarios, bindings and fixtures.

Planning notes and diagrams may explain purpose, architecture or interfaces,
but are non-authoritative. Keep unresolved questions and research on issues.
There is no separately merged Markdown specification, approval manifest,
requirement registry, traceability matrix or mandatory scenario-ID scheme.

The same ordinary PR carries scenarios, bindings, implementation and required
lower-level tests. Reuse a scenario PR if one exists; otherwise `undertake`
opens it on the same task branch. The implementation agent confirms the
allocated scenarios exist, establishes the expected behavioral failure, and
implements to green. Current-head CI supplies deterministic execution evidence
under the existing review and readiness gates, not a second acceptance gate.
An implementation task completes when its scenarios and required lower-level
checks pass on the delivered head and those ordinary gates clear. The human
merge decision remains the ordinary PR merge decision.

## Amendments and base updates

- If implementation violates an agreed scenario, change implementation and
  continue.
- If a binding or fixture fails to express the agreed scenario, repair it and
  continue with independent review.
- If a scenario is wrong, incomplete or ambiguous, pause only the affected
  behavior, discuss it with the operator, and record the decision on the
  implementation task or its specification issue. Continue unaffected work.
  New behavior is not accepted until the operator agrees.
- A reviewer may propose a missing case, but cannot make new behavior
  mandatory by editing scenarios or withholding the PR without operator
  agreement.
- If the change alters an epic's agreed scope or decomposition, use `epic`'s
  ordinary `Agree the plan` boundary. Do not automatically demote the parent.

After agreement, edit scenarios in the same branch and PR and continue through
`review-cycle`; material scope changes use its existing full-review rule.
A mechanical conflict resolution that preserves agreed scenario text and
behavior may proceed normally. A base change or conflict that changes,
removes or contradicts an allocated scenario follows the amendment rule:
pause affected behavior for an explicit product decision, not a silent choice
of either revision. There is no separate amendment or scenario-revision gate.
