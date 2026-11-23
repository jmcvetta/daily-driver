# Human-Controlled Acceptance Contracts for Agentic Software Development

## The problem

Agentic software development can generate and review code at volumes that make routine human code review impractical. Green CI and successful agentic reviews do not, by themselves, establish that the product is what its human engineers intended. The challenge is to preserve **human control of product behavior** without making specification maintenance as burdensome as implementation.

> **Conversation can be production; writing is control.**

Interactive conversations with agents can discover and produce features. A durable, human-authored acceptance contract is the engineering team's independent expression of what the product must do.

## Proposed approach

Use **Acceptance Test-Driven Development (ATDD)** as the baseline, with lower-level BDD where useful (particularly around modules or services), and ordinary unit testing delegated largely to agents.

1. **Human engineers own the acceptance contract.** Agents may propose scenarios and identify gaps, but cannot unilaterally change what constitutes acceptance.
2. **Acceptance tests are deterministic and executable.** They return objective pass/fail results, not an LLM's subjective assessment. Tests must control relevant state, time, randomness, dependencies, and asynchronous behavior.
3. **Specify observable product behavior, not implementation.** A test should reject consequentially wrong behavior yet survive a complete rewrite of the implementation.
4. **Protect the trusted execution layer.** Step definitions, fixtures, assertions, and CI configuration must not be silently weakened by implementation agents.
5. **Automate implementation and review.** Agents write code, lower-level tests, and most verification machinery within defined authority boundaries. Human effort concentrates on consequential product decisions.

A new human-specification bottleneck is acceptable if it permits a very large increase in useful development output. Removing that bottleneck prematurely could also remove the mechanism of human control.

## Choosing the right abstraction

Aim for **high discriminating power per unit of human cognitive effort**: a small, comprehensible contract that rules out many undesirable implementations while leaving engineering choices open.

The natural unit is often a **domain operation or user journey**, not an individual function or a vague product aspiration. Examples and decision tables clarify behavior; broader rules can constrain multiple features at once.

**Product invariants** (e.g., “refunds never exceed captured payments”) and enduring capabilities can guide agentic review of proposed *changes to the acceptance contract*. Some invariants can be tested mechanically; semantic ones may require agentic review and escalation to humans. Such review complements rather than replaces deterministic acceptance tests.

## Tooling options

| Tool | Potential role | Main consideration |
| --- | --- | --- |
| **Gherkin + Cucumber** | Natural-language executable acceptance scenarios | Clean `Given`/`When`/`Then` source; requires trusted step definitions |
| **Gauge** | Markdown-like executable specifications | Flexible, readable prose; assess ecosystem and maintenance |
| **Concordion** | Executable prose, tables, and living documentation | Rendered output is readable; source annotations add clutter |
| **Robot Framework** | Keyword-driven ATDD | Mature approach, but can become procedural and verbose |
| **Playwright** | Browser/API execution for acceptance tests | Execution layer, not the human-readable contract language |
| **Vitest / pytest** | Conventional deterministic test runners | Useful underneath; raw code takes more effort to scan |
| **Testcontainers** | Isolated service dependencies | Helps make execution reproducible |
| **Hypothesis / fast-check** | Property-based or stateful testing | Useful for machine-checkable invariants |
| **Spec Kit** | Structured agentic specification/development workflow | Workflow guidance, **not** a deterministic acceptance engine |
| **Pact** | Consumer-provider API compatibility contracts | Valuable for API development, but generally below the product-level acceptance boundary; especially relevant when the API is the product |

**No framework selected yet.** Human-readable, natural-language specifications are preferred to writing the core acceptance contract directly in pytest or TypeScript. Gherkin, Gauge, and Concordion warrant hands-on comparison.

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

- Which human-readable format offers the best **readability, precision, compactness, and maintainability** at product scale?
- How should trusted step definitions and test fixtures be governed so the written contract cannot lose its meaning?
- How should proposed contract changes be reviewed against product invariants and enduring capabilities?
- How can the team evaluate whole-product coherence and usability beyond the cases covered by deterministic tests?

**Practical next step:** Express a representative set of product behaviors—state transitions, permissions, edge cases, and user journeys—in Gherkin, Gauge, and Concordion. Compare both the source and the resulting execution/reporting workflows before choosing a foundation.
