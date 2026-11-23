# Property-based testing for human-controlled acceptance contracts

Research date: 2026-11-24.

## Purpose and conclusion

Property-based testing (PBT) complements the approach in
[Human-Controlled Acceptance Contracts for Agentic Software Development](agentic_development_acceptance_contracts.md).
Concrete examples establish intended behavior; executable properties challenge
that behavior across generated inputs and operation sequences. This can give a
small human-reviewed contract more discriminating power without prescribing an
implementation.

PBT is not a replacement for acceptance examples, a specification workflow, or
human product decisions. It does not prove correctness or prevent an agent from
weakening assertions. The promising experiment is one real feature with both a
required successful operation and an enduring invariant, not a repository-wide
tooling rollout.

This document synthesizes a paper and primary tool documentation. Tool
capabilities below are documentation-based findings, not results from running
these frameworks or comparing their performance. Recommendations are engineering
judgments. No framework has been adopted by this research.

## What the motivating paper establishes

Deepak Babu Piskala's technical report,
[Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants, v1](https://arxiv.org/html/2602.00180v1),
briefly discusses PBT in section IV as a way to check specification-derived
invariants across implementation variations. Sections III and V place validation
and executable examples within a broader specification-driven workflow.

The report does not present a PBT experiment, evaluate a PBT framework, or
establish that PBT reduces agent errors or human review effort. Its case-study
claims are not a substitute for a controlled evaluation of this technique.
Section IX also identifies the underlying limit: an implementation can agree
with an incorrect specification and still be wrong for its users.

The useful hypothesis for our work is narrower: a human-approved invariant,
executed against many generated cases, might reject consequential mistakes that
a few selected examples miss. That hypothesis needs a practical feature trial.

## How PBT works

A property test combines:

1. **A property:** an executable assertion about observable behavior.
2. **An input domain and generator:** the values or action sequences to explore.
3. **An execution boundary:** the real function, domain operation, API, or other
   product interface being exercised.
4. **An oracle:** the means of deciding whether the observed result is correct.
   This may be a simple invariant, a reference model, or a relation between runs.

The framework generates cases and searches for a counterexample. When a case
fails, shrinking attempts to find a simpler failing input or sequence. A smaller
counterexample is easier to understand, reproduce, and retain as a regression.
Shrinking is a search process; it does not guarantee the globally smallest case.

The assertion returns an objective pass/fail verdict. Generated sampling does
not make this an LLM judgment, but uncontrolled clocks, services, randomness, or
concurrency can still make the execution flaky. A finite successful run is not
proof that the property holds for every possible input.

## One example: refunds

Assume, for illustration only, a payment product with integer minor currency
units and sequential refund requests. Its exact retry, authorization, currency,
and concurrency rules would need separate product decisions.

| Contract element | Behavior it establishes |
| --- | --- |
| Example: a 4,000-unit refund against a 10,000-unit capture succeeds | A required successful operation |
| Example: a subsequent 7,000-unit refund is rejected | A concrete rejection after a partial refund |
| Property: cumulative successful refunds never exceed the capture | A safety invariant over generated sequences |
| Property: a rejected refund leaves the refundable balance unchanged | Rejection has no unintended balance effect |
| Model comparison: eligible requests succeed and update the balance as specified | Required outcomes, not merely an upper bound |

An implementation that rejects every refund satisfies the upper-bound invariant.
It fails the successful example and a model that requires eligible refunds to
succeed. This is why invariants alone are not a complete acceptance contract.

A stateful test can generate a capture followed by multiple refund requests,
including exact-balance, over-balance, and repeated requests. After each operation
it checks outputs and observable balance against a small reference model.
[Hypothesis's stateful guide](https://hypothesis.readthedocs.io/en/latest/stateful.html)
and [fast-check's model-based guide](https://fast-check.dev/docs/advanced/model-based-testing)
describe generated action sequences of this kind.

The model must express agreed product rules rather than copy implementation
logic. A sequential state machine does not establish correctness under concurrent
requests. Concurrency requires a defined consistency contract and an execution
strategy that actually explores relevant interleavings.

## Useful property shapes

- **Invariants:** a balance stays within its allowed range after every operation.
- **Round trips:** decoding an encoded supported value returns the original value,
  subject to an explicit normalization rule.
- **Idempotence:** repeating an operation with the same idempotency key has the
  same specified effect as executing it once.
- **Metamorphic relations:** a defined transformation of the input has a known
  relationship to the output, even when computing an exact expected output is
  difficult.
- **Model agreement:** generated operations produce the same observable outcomes
  as a simpler, independently expressed behavioral model.

Each shape needs domain justification. Not every operation is idempotent; a
round trip can pass when encoder and decoder share a compensating defect.
Properties are useful because of the incorrect behavior they exclude, not because
of how many generated cases pass.

## Tool shortlist by ecosystem

| Ecosystem | Starting point | Relevant capabilities and limits |
| --- | --- | --- |
| Python | [Hypothesis](https://hypothesis.readthedocs.io/en/latest/) | Rich strategies, shrinking, an example database, and rule-based state machines. Integrates with common Python test runners. Strong initial candidate for domain properties. |
| TypeScript / JavaScript | [fast-check](https://fast-check.dev/docs/introduction/) | Shrinking, seed/path replay, asynchronous properties and commands, and scheduling support for exploring asynchronous execution. Runner-agnostic; a strong candidate when the product is already in this ecosystem. |
| Go | [rapid](https://github.com/flyingmutant/rapid) | Structured generators, automatic shrinking, saved failures, and state-machine testing through `go test`. A practical starting point for domain-level PBT. |
| Rust | [proptest](https://github.com/proptest-rs/proptest) | Composable per-value strategies, shrinking, and regression persistence. The reviewed README describes passive maintenance; assess that support model before adoption. |
| C++ | [RapidCheck](https://github.com/emil-e/rapidcheck) or [FuzzTest](https://github.com/google/fuzztest) | RapidCheck provides conventional PBT, shrinking, stateful commands, and test-framework integrations. FuzzTest combines properties and input domains with coverage-guided exploration. RapidCheck's current maintenance cadence was not established by this research. |

For an initial experiment with no existing stack constraint, Hypothesis or
fast-check offers a direct route to generated domain-operation sequences. Prefer
the product's existing ecosystem when possible: adding a second language and
adapter layer creates its own maintenance cost.

### Other tools worth recognizing

- **Python:** [HypoFuzz](https://hypofuzz.com/docs/features.html) runs longer,
  coverage-guided campaigns over Hypothesis tests.
  [Atheris](https://github.com/google/atheris) provides libFuzzer-based
  coverage-guided fuzzing, including use with native extensions.
- **Go:** [native fuzzing](https://go.dev/doc/fuzz) integrates with the standard
  toolchain and maintains a corpus, but fuzz target arguments use a restricted
  set of types. Structured domain inputs need a deliberate representation.
  [gopter](https://github.com/leanovate/gopter) provides generators, shrinking,
  and stateful commands. The standard `testing/quick` package is a simpler
  option without a comparable shrinking-first workflow.
- **Rust:** [quickcheck](https://docs.rs/quickcheck/latest/quickcheck/) offers an
  `Arbitrary`-based approach with shrinking.
  [cargo-fuzz](https://github.com/rust-fuzz/cargo-fuzz) supports libFuzzer
  campaigns; its toolchain and platform requirements differ from ordinary
  stable-Rust test execution.

These are alternatives and complements, not a recommendation to install all of
these tools. Maintenance observations are a dated documentation snapshot, not a
guarantee of support or a comprehensive project-health audit.

## PBT and coverage-guided fuzzing overlap

A property defines what must hold. Coverage guidance helps decide which inputs
to explore next. They are not mutually exclusive techniques.

Traditional PBT emphasizes structured generation, user-written properties, and
shrinking. Coverage-guided fuzzing uses execution feedback to search new paths.
It often detects crashes or sanitizer violations, but can also detect semantic
errors when the target includes appropriate assertions. FuzzTest deliberately
combines these ideas; HypoFuzz applies coverage-guided exploration to Hypothesis
tests. Rapid also documents integration with Go's native fuzzing.

For acceptance contracts, the decisive issue is the oracle. A long fuzzing run
without assertions about business behavior cannot establish that behavior.
Likewise, a short PBT run is not evidence that all important paths were explored.

## Trust, reproducibility, and cost

Human ownership must extend beyond a property's prose label. Review changes to:

- **Assertions and reference models:** do they reject meaningful errors and
  require successful behavior where promised?
- **Generators and preconditions:** do they cover boundaries and invalid requests
  where those matter? Excessive filtering can exclude precisely the failures
  the property should expose or leave too few useful cases.
- **Fixtures and adapters:** do they execute the real product behavior rather
  than replace it with a model or stub of the behavior under test?
- **Execution settings:** did changes reduce examples, sequence lengths, search
  time, or other meaningful coverage without an explicit decision?

Control state, time, dependencies, and randomness. Keep tests offline against
controlled dependencies where possible. A seed alone cannot reproduce a failure
caused by an uncontrolled service or scheduling change.

Replay mechanisms vary: Hypothesis retains examples in a database; fast-check
reports seeds and shrink paths, with additional command replay information for
model-based cases; proptest persists regression information; rapid saves failure
information. Do not assume replay tokens are portable across arbitrary tool or
strategy changes. Retain consequential counterexamples as explicit regression
cases where appropriate, along with enough environment information to reproduce
them.

Generated sequences can multiply runtime at an API or browser boundary. Start
with bounded normal-test runs. A longer fuzzing campaign is a separate cost
choice, not an automatic requirement. Use the lowest public boundary that still
establishes the promised behavior; retain UI-level checks when the promise is
specifically about the user interface.

## Relationship to ATDD and specification tools

ATDD determines when acceptance is agreed and used to guide implementation. PBT
is one technique for executing part of that acceptance. Cucumber or Gauge can
provide a human-readable example surface; they are not prerequisites for PBT.
Spec Kit can structure planning and implementation, but is not the property
oracle or a deterministic acceptance engine.

Avoid maintaining a second prose specification that restates every assertion.
Keep human-readable rule descriptions close to their executable properties, and
review the descriptions, generators, models, and assertions together. This
research note explains the technique; it is not an application specification.

No reviewed source establishes that these frameworks enforce an agent-resistant
trust boundary. Preventing silent contract changes still requires an explicit
ownership and review process.

## Proposed first feature trial

1. Choose a bounded feature in an existing product with a required successful
   operation, a meaningful rejection, and a durable invariant.
2. Agree concrete examples and general rules with the human before implementation.
   Define the input domain and observable outcomes, including rejection effects.
3. Add executable examples and a generated property or state machine. Establish
   a failure caused by missing behavior, not an undefined binding or broken fixture.
4. Implement without silently changing acceptance. Review proposed changes to
   assertions, generators, and models as contract changes.
5. Run the established CI and retain useful counterexamples. Deliver examples,
   properties, bindings, and implementation in one ordinary PR.
6. Exercise a behavior-preserving refactor, then one actual behavior change. Assess
   whether the contract survived the first and clearly expressed the second.

Evaluate human review effort, counterexample clarity, runtime, and maintenance
of generators and models. Do not use generated-case counts as a correctness
score. The open question is whether a compact contract can reject consequential
agent mistakes at lower human cost, not which framework produces the most tests.
