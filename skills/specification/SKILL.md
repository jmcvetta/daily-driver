---
name: specification
description: >-
  Use when an operator wants to collaboratively draft, review, and publish a
  canonical specification, or when an issue of kind `specification` is handed
  over. This is interactive work, not an unattended implementation assignment.
---

# Specification

A specification is an agreed contract for intended behavior and acceptance,
not a project plan. Work interactively with the operator; do not use
`undertake` or `embark` to dispatch a specification issue unattended. A
`proposal` closes on a decision or handoff; a specification completes only
when the approved canonical document is merged and its handoff is recorded.

## Collaborate

1. Read the issue, its references and relevant repository context. Apply
   `issue-labels`, `issue-body` and `issue-deps` to its kind, body and edges.
   Use `issue` to create or update the interactive `specification` issue when
   needed. It carries no implementation model class. Keep questions, research
   references, alternatives, decisions and draft revisions on that issue;
   use research issues for bounded investigations where appropriate.
2. Investigate and answer questions the repository can answer. Apply
   `judgement-call`: choose ordinary engineering details, explain genuine
   tradeoffs, and ask the operator only for unresolved intent or product
   decisions. An agent can research, explain, draft and edit; the issue is not
   `human` merely because the operator must decide or approve.
3. Draft the document in an isolated task worktree under the repository's
   conventional `docs/specs/<feature>.md` path. Apply `task-worktree`,
   `provenance` and the repository's normal change and PR workflows. Iterate
   with the operator and record decisions on the issue. Do not pretend an
   omission is settled: a missing decision or research result that prevents
   implementation keeps the document unready.
4. Open a specification PR under `pr` and obtain independent review through
   `review-cycle`. Address findings and keep the PR current. Independent agent
   review is not product approval. Ask for explicit operator approval of the
   specification, and separately for approval of any proposed decomposition;
   neither approval implies the other. Record the decisions and their scope on
   the issue. Do not treat silence or a review as approval.
5. The operator merges the specification PR; the agent never merges it.
   Once approval and merge are observed, record the merged document path,
   immutable commit, approval and any separately approved handoff on the issue.
   Complete the issue only then. Rejection or abandonment follows the existing
   issue disposition rules; neither is a completed specification.

## Canonical document

Write a concise human brief describing the purpose and intended outcome. Add a
Mermaid diagram when it clarifies nontrivial structure. Textual requirements
are authoritative; summaries and diagrams explain them and never replace or
override them. When explaining the document contract, state that distinction.
State settled behavior, architecture, interfaces, constraints, edge cases,
acceptance criteria and product non-goals. Make requirements unambiguous and
independently verifiable.
Assign stable, meaningful IDs and anchors to requirements and acceptance
criteria so later work can cite an exact requirement at an immutable commit.
Preserve IDs across editorial changes; do not reuse an ID for different behavior.

The document is authoritative for intended behavior and acceptance. It must
not contain issue status, assignments, waves, progress checklists, unresolved
alternatives, TBDs, research requests or operator questions. Implementation
status and ordering stay outside it. Keep unresolved questions on the issue or
in research issues, not hidden in explanatory diagrams or deferred requirements.

## Amendments

Classify an amendment before applying it. An editorial correction clarifies
wording without changing agreed behavior, scope or acceptance and needs no
renewed scope agreement. A substantive amendment changes any of those and
requires renewed operator scope agreement; do not infer it from prior approval.
Use the same reviewed PR and operator approval and merge boundaries for the
changed canonical document. Record the decision and resulting commit in the
issue handoff.
When the document governs an epic, `epic` first demotes that same parent to
`discovery` and pauses affected implementation. After the operator approves
and merges the substantive amendment, hand its exact merge SHA back to `epic`
for allocation, contract and graph reconciliation before re-promotion. An
implementation PR must not amend its governing specification silently.
