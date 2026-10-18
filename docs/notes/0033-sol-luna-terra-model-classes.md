# Sol 6.1, Luna 6, and Terra 5.6 on model-class work

**Status:** bounded comparison complete; retirement evidence inconclusive, 2026-10-18.
**Assignment:** [#579](https://github.com/jmcvetta/daily-driver/issues/579).

**Recommendation [INFERENCE]: prefer Luna for the tested mechanical and implementation handoffs; do not retire Terra on this evidence.** Luna recovered all 18 planned results after two transport retries and has the lowest known normalized resource cost. Terra completed all 18 raw tasks, but the recorder rejected eleven because sandbox paths printed this checkout's root. Sol also lacks a valid `career-469` result. Neither limitation establishes a model reliability difference. No defaults or retirement settings change here.

## Design, routes, and bounds

The six cases are `career-141`, `career-370`, `career-444`, `career-462`, `career-469`, and `career-475`: three mechanical and three implementation tasks from `jmcvetta/career`. Each subject's full comparison planned three repeats per case: 18 slots per model, 54 across the three subjects. These are merged-PR answer keys, not plugin-following or reasoning-class tests.

All subjects used the **OpenAI Codex subscription**, `coder-eval` 0.11.6, high thinking effort, `acceptEdits`, and tools `[Bash, Read, Write, Edit, Grep, Glob]`. No metered gateway, helper model, or judge model ran. The grading instrument consists of three executable checks: no deleted base tests, no added skip/xfail markers, and the merged PR's tests passing. The recorder separately disqualifies answer-key contact. Requested model identity is not served identity: Omp reported no served-model identity, so provenance retains `unknown`/`unreported`.

The Omp 18.12.1 catalog, read with `omp models openai-codex --json --no-extensions` on 2026-10-18, resolves these exact subjects:

| Subject selector | Catalog context limit | Catalog output limit | Effort |
| --- | ---: | ---: | --- |
| `openai-codex/gpt-6.1-sol` | 500,000 | 128,000 | high |
| `openai-codex/gpt-6-luna` | 272,000 | 128,000 | high |
| `openai-codex/gpt-5.6-terra` | 272,000 | 128,000 | high |

These are catalog limits, not measured context use. All experiments pin 30 turns and a 780-second task limit. The experiment sets a 600-second turn limit, but the task files override it to **660 seconds**. The effective single-iteration agent budget is therefore 660 seconds; a longer task limit does not extend it. Service tier was not pinned or reported. Equal high effort does not imply equal internal reasoning work; separate reasoning-token detail was not reported.

Sol and Luna ran on Omp 18.8.4 at `JOBS=32`, with at most 18 tasks concurrently. The original Terra batches used `JOBS=32`, `16`, and `4`; all were interrupted. A new Terra batch used `JOBS=1`: nine finalized tasks on Omp 18.11.3, then nine on 18.12.1 through `coder-eval run --resume --run-dir runs/2026-10-17_17-56-32`. The original nine task JSON hashes remained unchanged. The resume warned about reordered excluded tags; the excluded set was unchanged. Harness version, concurrency, execution date, host load, and interruption are confounds, not model effects.

The task and fixture snapshot for the new Terra batch is frozen at `a78122b2df25aa818dd6a790cb9ca25487336ac4`. The original Sol `career-469` grader was not equivalent: its optional authenticated label check had no Git remote. The corrected grader isolates `GH_CONFIG_DIR`, `GH_TOKEN`, and `GITHUB_TOKEN`; Luna and the new Terra batch used that correction. Historical records remain unchanged rather than being presented as a uniformly frozen comparison.

The documented two-case smoke (`career-462`, `career-475`) preceded full runs. Terra's October 17 smoke passed both cases with no recorded contact. The [recovery envelope](https://github.com/jmcvetta/daily-driver/issues/579#issuecomment-6232987378) bounded that work to two smoke calls plus 18 full slots at `JOBS=1`. The [continuation envelope](https://github.com/jmcvetta/daily-driver/issues/579#issuecomment-6246806954) authorized only the nine unfinished slots, with no retries, new batch, helper, or judge calls. It estimated 50.63 normalized credits from a selected historical sample; it was not a spending cap or a forecast of subscription allowance consumption. All nine continuation slots finalized; no further subject calls were made.

## Outcomes and failure modes

The main comparison uses the Sol full run, the Luna full run plus its two recovery attempts, and the completed Terra batch. `E` is an evaluation/transport error, `G` an invalid grader result, `K` the recorder's answer-key-contact rejection, and `P` its conservative sandbox-path rejection. Neither `G` nor `P` is an implementation failure rate.

| Case (class) | Sol 6.1, repeats 0–2 | Luna 6, repeats 0–2; retries | Terra 5.6, repeats 0–2 |
| --- | --- | --- | --- |
| `career-141` (implementation) | 1, 1, 1 | 1, 1, E; retry 1 | P, 1, P |
| `career-370` (mechanical) | 1, 1, 1 | 1, 1, 1 | 1, 1, 1 |
| `career-444` (mechanical) | 1, K, 1 | 1, 1, 1 | P, 1, 1 |
| `career-462` (mechanical) | 1, 1, 1 | 1, 1, 1 | P, 1, P |
| `career-469` (implementation) | E, G, G; corrected retry timed out | 1, 1, E; retry 1 | P, P, P |
| `career-475` (implementation) | 1, 1, 1 | 1, 1, 1 | P, P, P |

Sol has eight accepted mechanical results out of nine and six accepted implementation results out of nine. Its `career-444` replicate 1 printed a staged-reference path during a broad host glob; the recorder zeroed the raw pass. Both `career-469` raw failures scored 0.4 because of the invalid label check. A corrected single-task retry hit the task timeout. Its recorded elapsed field is anomalous at 88,712.8 seconds and is not usable latency evidence.

Luna has nine accepted results per class after recovery. Its initial full run accepted 16/18; `career-141` replicate 2 and `career-469` replicate 2 lost their Omp streams without `agent_end`. Retries passed in 199.4 and 331.7 seconds. Both failed attempts remain in resource accounting. The evidence does not attribute the disconnects to concurrency.

Terra has **18/18 raw executable passes**, but only six accepted mechanical results and one accepted implementation result. All eleven recorder rejections contain only `printed <task repository root>` evidence. Inspection found package-build output and test paths under the local `evals/runs/recovery-579-2026-10-17/tmp/` sandbox storage. The detector treats any printed checkout-root path as contact; it cannot distinguish this placement from an exposed evaluation checkout. These are not eleven demonstrated answer-key reads. The report keeps the recorder's zero scores; it does not silently turn them into valid passes. A future clean run must place sandboxes outside the evaluation checkout and keep the same contact policy.

Three earlier Terra batches remain separate: six finalized passes in the first; seven passes and one stream error in the second; three passes and nine invalid disk-quota grades in the third. Their 28 unfinalized slots are neither scored failures nor free attempts. Recovery records preserve the finalized artifacts and identify the missing slots. The new batch also restarted one interrupted execution whose usage is unknown; its pre-resume log was preserved locally. Duplicate historical passes do not increase independent case coverage.

## Elapsed time

| Main cohort | Recorded invocation wall time | Median task elapsed | Sum of finalized task elapsed |
| --- | ---: | ---: | ---: |
| Sol full, 18 attempts | 688.9 s | 316.9 s | 5,975.1 s |
| Luna full plus two retries, 20 attempts | Full batch 673.0 s; retries separate | 238.3 s | 5,905.9 s |
| Terra completed batch, 18 tasks | Resume invocation only: 2,108.5 s | 278.5 s | 4,469.3 s |

Terra's run-level timestamps cover only the nine-task resume invocation, while its cases include nine earlier tasks. The generated results page therefore shows resume wall time, not full-batch latency. Summed task time excludes the interruption gap, queue time, and the unfinished execution. It is not wall time. Sequential Terra and concurrent Sol/Luna do not support a throughput ranking.

## Measured tokens and normalized credit estimates

The current [Codex credit rate card](https://learn.chatgpt.com/docs/pricing#token-rates), retrieved **2026-10-18**, publishes Standard-speed credits per million tokens:

| Requested model | Uncached input | Cached input | Output |
| --- | ---: | ---: | ---: |
| `gpt-6.1-sol` | 50 | 2.5 | 250 |
| `gpt-6-luna` | 2.5 | 0.25 | 12.5 |
| `gpt-5.6-terra` | 50 | 5 | 300 |

`estimated credits = ((uncached input + cache creation) × input rate + cached input × cached rate + output × output rate) / 1,000,000`.

The same published billing basis applies to every subject. Standard speed is an assumption, not an observed service tier. Cache creation is zero wherever reported; the formula assigns it the uncached rate. Input buckets are disjoint. Output is counted once; unreported reasoning detail is not added to it. These are **calculated normalized credits**, not actual charges, USD, or measured included subscription allowance use. They are not stored in actual-charge fields. Schema-5 records retain token buckets and subscription billing; both historical schema-4 formats remain readable without rewriting them.

The main-cohort numerator includes every finalized attempt, including transport errors, invalid grades, and contact rejections. A missing usage bucket makes a complete total unknown.

| Main cohort | Accepted / attempts | Known uncached / cached / output tokens | Normalized credits | Tokens per accepted result | Credits per accepted result |
| --- | ---: | --- | ---: | ---: | ---: |
| Sol full | 14/18 | 1,007,068 / 11,755,264 / 98,811 | 104.44 | 918,653 | 7.46 |
| Luna full + retries | 18/20 | 901,873 / 8,546,304 / 84,126 | Unknown; known subtotal 5.44 | Unknown | Unknown |
| Terra finalized batch | 7/18 | 880,994 / 9,212,416 / 123,459 | 127.15 | 1,459,553 | 18.16 |

Token-per-result figures sum uncached input, cached input, cache creation, and output, then divide by accepted results. They include failed/rejected attempts in the numerator. Luna's two disconnects lack usage, so its complete per-success figures are unknown, not zero. Terra's figures cover finalized tasks only; the interrupted execution is additional unknown consumption. Its rejection-heavy denominator makes these recorder-accepted-result costs, not an estimate of cost per correct implementation. A cohort with no accepted results would have undefined per-success figures.

The campaign ledger includes every committed comparison smoke, full, retry, and recovered partial record, not unrelated GPT evaluations:

| Subject | Finalized records / accepted results | Known uncached / cached / cache-creation / output tokens | Known normalized-credit subtotal | Finalized records with missing buckets |
| --- | ---: | --- | ---: | ---: |
| Sol 6.1 | 28 / 17 | 1,108,183 / 12,558,336 / 0 / 106,473 | 113.42 | 7 |
| Luna 6 | 22 / 20 | 992,167 / 8,958,464 / 0 / 90,209 | 5.85 | 2 |
| Terra 5.6 | 48 / 27 | 2,111,602 / 19,862,528 / 0 / 277,889 | 288.26 | 1 |
| Known campaign subtotal | 98 / 64 | 4,211,952 / 41,379,328 / 0 / 474,571 | 407.53 | 10 |

This is not a complete campaign total: it excludes unknown usage from the ten finalized records with missing fields, 28 unfinalized historical Terra slots, and the restarted interrupted execution. Seven Sol records lack complete buckets: two old smoke rows and five model-selection errors. The startup errors reported no model turn, but missing usage is not assumed zero. No helper/judge model overhead was incurred; operator-session usage is not measured by these subject records. Complete campaign cost per success is unknown for every subject.

## Decision and limits

- **Luna [INFERENCE]:** the best-supported choice for these tested handoffs. All six case IDs recovered successfully, with a much lower known credit subtotal. Missing disconnect usage prevents a complete cost ratio, and transport recovery is part of its observed reliability trade-off.
- **Sol [INFERENCE]:** this sample demonstrates no reliability or resource-use advantage over Luna. Its invalid `career-469` grades prevent a complete implementation comparison; its one contact-policy rejection remains a measured zero.
- **Terra [INFERENCE]:** raw tasks show capability on all six case IDs, but the isolation fault prevents a clean reliability estimate. Retain it pending better evidence, not because this study established an advantage. Retirement remains inconclusive.

The stopping rule was the bounded completion of the frozen Terra slots, not an unbounded search for clean scores. The next evidence needed is a matched-version, matched-concurrency run outside the evaluation checkout, with three repeats per case and a valid `career-469` grader for every subject. That is a new quota envelope, not work silently added here. Six cases from one repository cannot prove general superiority, reasoning-role suitability, or plugin compliance. Small score differences would not establish those claims even without the grading faults.

## Provenance ledger

- [Sol full](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-38-45.json).
- [Luna full](../../evals/provenance/classes-luna-6-2026-10-09-2026-10-09_19-52-53.json), [`career-141` retry](../../evals/provenance/classes-smoke-luna-6-2026-10-09-2026-10-09_20-05-37.json), [`career-469` retry](../../evals/provenance/classes-smoke-luna-6-2026-10-09-2026-10-09_20-10-04.json).
- [Terra completed/resumed batch](../../evals/provenance/classes-terra-5-6-2026-10-18-2026-10-17_17-56-32.json), with continuation and contact-limit metadata; [October 17 smoke](../../evals/provenance/classes-smoke-terra-5-6-2026-10-17-2026-10-17_17-50-08.json).
- Recovered Terra batches: [first](../../evals/provenance/classes-terra-5-6-2026-10-09-2026-10-09_20-16-52.json), [second](../../evals/provenance/classes-terra-5-6-2026-10-09-2026-10-09_20-28-05.json), [third, including disk-quota grades](../../evals/provenance/classes-terra-5-6-2026-10-09-2026-10-09_21-43-57.json). Recovery metadata describes recovery, not the original subject execution environment.
- Sol smoke and retries: [initial](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_18-12-37.json), [corrected smoke](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_18-21-32.json), [`career-462` retry](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_19-02-13.json), [corrected-grader timeout](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_19-06-53.json).
- Initial [Luna smoke](../../evals/provenance/classes-smoke-luna-6-2026-10-08-2026-10-08_18-24-17.json) and [Terra smoke](../../evals/provenance/classes-smoke-terra-5-6-2026-10-08-2026-10-08_18-29-58.json).
- Sol startup errors: [two records](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-52-27.json), [three records](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-55-17.json).
