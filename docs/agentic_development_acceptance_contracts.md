# Human-Controlled Acceptance Contracts for Agentic Software Development

## The problem

Agentic software development can generate and review code at volumes that make routine human code review impractical. Green CI and successful agentic reviews do not, by themselves, establish that the product is what its human engineers intended. The challenge is to preserve **human control of product behavior** without making specification maintenance as burdensome as implementation.

> **Conversation can be production; executable writing is control.**

Interactive conversations with agents can discover and produce features. The executable acceptance contract is the specification: a durable, human-owned expression of what the product must do. Planning documents and design notes can explain the work, but they are not a second behavioral specification and do not need to remain synchronized with it.

## Proposed approach

Use **Acceptance Test-Driven Development (ATDD)** as the baseline, with lower-level BDD where useful (particularly around modules or services), and ordinary unit testing delegated largely to agents.

1. **Human engineers own the acceptance contract.** Agents may propose scenarios and identify gaps, but cannot silently redefine acceptance.
2. **Acceptance tests are deterministic and executable.** They return objective pass/fail results, not an LLM's subjective assessment. Tests must control relevant state, time, randomness, dependencies, and asynchronous behavior.
3. **Specify observable product behavior, not implementation.** A test should reject consequentially wrong behavior yet survive a complete rewrite of the implementation.
4. **Protect the trusted execution layer.** Step definitions, fixtures, assertions, and CI configuration must not be silently weakened by implementation agents.
5. **Automate implementation and review.** Agents write code, lower-level tests, and most verification machinery. Human effort concentrates on consequential product decisions.

Keep the process light: executable scenarios, implementation, ordinary CI, and review. Do not add a parallel Markdown specification, requirement registry, traceability matrix, or separate acceptance-evidence gate.

## A typical feature, end to end

1. **Discuss the behavior.** Settle consequential product questions in conversation. Small tasks need no additional specification ceremony; larger efforts can retain planning notes and issue dependencies.
2. **Write scenarios on the task branch.** This is the `specification` activity. Express the agreed behavior in the project's acceptance format and review the concise scenario text with the human engineer. The scenarios are the deliverable, not a canonical prose document.
3. **Establish the failing behavior.** Add or reuse step definitions and fixtures. New scenarios should fail because the feature is absent, while existing behavior stays green.
4. **Implement in the same branch.** This is `undertake`. Make the scenarios and existing tests pass. If the contract is wrong or incomplete, discuss and change it openly; never edit it silently merely to accommodate the implementation.
5. **Deliver one ordinary pull request.** Include the scenarios, bindings, implementation, and lower-level tests together. The PR description needs no acceptance traceability matrix; reviewers can read the scenarios directly.
6. **Review and merge normally.** `review-cycle` reviews the scenarios, bindings, and implementation together. CI supplies the deterministic verdict; agentic review checks that the tests are meaningful and the implementation satisfies their intent. The human reviewer can focus on behavioral diffs and retains the merge decision.

Later refactoring leaves the scenarios unchanged. New or changed observable behavior updates the scenarios in the same reviewed change as the implementation. The contract stays current because normal delivery executes it, not because anyone remembers to update a separate document.

## Choosing the right abstraction

Aim for **high discriminating power per unit of human cognitive effort**: a small, comprehensible contract that rules out many undesirable implementations while leaving engineering choices open.

The natural unit is often a **domain operation or user journey**, not an individual function or a vague product aspiration. Examples and decision tables clarify behavior; broader rules can constrain multiple features at once.

**Product invariants** (e.g., “refunds never exceed captured payments”) and enduring capabilities can guide agentic review of proposed *changes to the acceptance contract*. Some invariants can be tested mechanically; semantic ones may require agentic review and escalation to humans. Such review complements rather than replaces deterministic acceptance tests.

## TypeScript tooling

Gherkin and `@cucumber/cucumber` are the initial TypeScript default. Use the
[`atdd` skill](../skills/atdd/SKILL.md) to resolve and run its bundled bootstrap
against an npm or pnpm repository with one lockfile. It installs the pinned
dependencies and creates reusable configuration, not product scenarios.

Write the project's own `.feature` files under `acceptance/features/` and
TypeScript step definitions under `acceptance/steps/`; put shared support under
`acceptance/support/`. Run `npm run acceptance` or `pnpm acceptance` and include
that command in the project's established test, typecheck and CI conventions.
For preinstalled dependencies, the bootstrap also supports `--no-install`.
Add Playwright only when a pilot needs browser execution.

Agree scenarios on the implementation branch, record agreement and exclusions
on the task issue, establish the behavioral failure, and deliver scenarios,
bindings and implementation together. An optional separate specification issue
records the implementation issue, branch, scenario paths and any allocation or
exclusions before completing. Review implementation and trusted bindings against
the agreed scenarios; discuss a wrong, incomplete or ambiguous scenario with
the operator before treating an amendment as accepted.

## Gherkin's table-driven capabilities

- **`Scenario Outline` + `Examples`:** Each table row generates a separate scenario, making decision tables concise and scannable.
- **Data Tables:** Provide structured data to a step within one scenario; they do not automatically create separate executions.

```gherkin
Scenario Outline: Cancellation eligibility
  Given an order is in the "<state>" state
  When the customer requests cancellation
  Then the request is "<outcome>"

  Examples:
    | state   | outcome  |
    | paid    | accepted |
    | shipped | rejected |
```

## Open design questions

- How should trusted step definitions and test fixtures be governed so the written contract cannot lose its meaning?
- How should proposed contract changes be reviewed against product invariants and enduring capabilities?
- How can the team evaluate whole-product coherence and usability beyond the cases covered by deterministic tests?

