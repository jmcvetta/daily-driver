# Sol 6.1, Luna 6, and Terra 5.6 on model-class work

**Status:** inconclusive, 2026-10-09.
**Provenance:** [#579](https://github.com/jmcvetta/daily-driver/issues/579).

The bounded comparison does not support a Terra retirement decision. Luna passed every scored replicate after two transport retries. Sol lacks a valid score for `career-469`. Terra's two full batches were stopped before completion after the owner reported high laptop load and then asked to stop the evaluations. Do not read the partial Terra results as evidence of reliability.

## Design and route

The six frozen cases are `career-141`, `career-370`, `career-444`, `career-462`, `career-469` and `career-475`: three mechanical and three implementation tasks from `jmcvetta/career`. Each full experiment planned three repeats per case: 18 task attempts per model, 54 across the three models. All used Omp 18.8.4 through the OpenAI Codex subscription, with the exact requested model IDs `openai-codex/gpt-6.1-sol`, `openai-codex/gpt-6-luna` and `openai-codex/gpt-5.6-terra`. None used Vercel AI Gateway. Each config pinned `--thinking high`, `acceptEdits`, tools `[Bash, Read, Write, Edit, Grep, Glob]`, 30 max turns, a 780-second task timeout and a 600-second turn timeout. Omp did not report a served model; records say `unknown`.

Smoke runs preceded the full batches. Sol and Luna full batches used `JOBS=32`; each had only 18 tasks, so at most 18 ran concurrently. Terra first ran at `JOBS=32`, then at `JOBS=16`. Both Terra batches were canceled by the owner. After the final stop instruction, no more evaluation ran. The concurrency change and incomplete Terra batches limit timing and reliability comparisons.

## Measured outcomes

Scores below are the recorder's measured scores. `E` is an unscored evaluation error. `G` is an invalid grader result, not a model score. `K` is a zero caused by recorded answer-key contact, not a valid implementation score. The Luna retry replaces neither original transport error in the ledger; it adds a new successful attempt.

| Case (class) | Sol 6.1 full, repeats 0–2 | Luna 6 full, repeats 0–2; retries | Terra 5.6 finalized task records |
| --- | --- | --- | --- |
| `career-141` (implementation) | 1, 1, 1 | 1, 1, E; retry 1 | One pass (`replicate 00`) in the `JOBS=16` batch |
| `career-370` (mechanical) | 1, 1, 1 | 1, 1, 1 | Repeats 00–02 passed in both aborted batches; duplicate observations |
| `career-444` (mechanical) | 1, K, 1 | 1, 1, 1 | No finalized task record |
| `career-462` (mechanical) | 1, 1, 1 | 1, 1, 1 | Repeats 00–02 passed in both aborted batches; duplicate observations |
| `career-469` (implementation) | E, G, G; corrected-grader retry timed out | 1, 1, E; retry 1 | One Omp error (`replicate 01`) in the `JOBS=16` batch |
| `career-475` (implementation) | 1, 1, 1 | 1, 1, 1 | No finalized task record |

By class, Sol produced eight valid score-1 mechanical results and one answer-key contact; Luna scored all nine mechanical tasks 1.0. Sol produced six valid score-1 implementation results, but no valid `career-469` score. Luna scored all nine implementation tasks 1.0 after the retries. Terra's partial artifacts cover only two of three case IDs per class and do not supply a complete set of repeats.

The Sol full run recorded 15 `SUCCESS`, two `FAILURE` and one `ERROR` statuses. Its `career-444` replicate 1 contacted the answer key and was measured as zero, despite passing the task criteria. Both `career-469` failures scored 0.4 because the grader's `gh label list` check had no Git remote. The corrected grader isolates `GH_CONFIG_DIR`, `GH_TOKEN` and `GITHUB_TOKEN`; Luna's first two `career-469` runs then passed all three criteria, with 85 tests passed and one optional test skipped. A corrected single-task Sol retry timed out at the 780-second task limit. The timeout record's duration field is anomalous (88,712.8 seconds); use the timeout event, not that field.

Luna's full batch finished 16/18 tasks. `career-141` replicate 2 and `career-469` replicate 2 lost their Omp streams after 50,063 and 2,376 recognized frames without `agent_end`. Single-task retries passed at 199.4 and 331.7 seconds. Thus the 18 planned Luna scores are all 1.0 after recovery, with two additional failed transport attempts still counted in resource use. No evidence ties those disconnects to concurrency.

The first Terra batch (`2026-10-09_20-16-52`, `JOBS=32`) finalized six task artifacts: three `career-370` and three `career-462` passes. The second (`2026-10-09_20-28-05`, `JOBS=16`) finalized eight: seven passes (`career-141` replicate 00, and repeats 00–02 for `career-370` and `career-462`) and one `career-469` Omp stream error. The other 22 task attempts across both batches did not finalize task artifacts. Neither canceled run produced a root `run.json`, so the existing recorder could not make provenance records for them. The task artifacts' measured scores and known token buckets are summarized here; unfinished usage remains unknown. These partial, duplicated results do not constitute a Terra full run.

The completed Sol run took 688.9 seconds wall time; its median task duration was 316.9 seconds across 18 attempts. Luna took 673.0 seconds; its median was 229.5 seconds across 18 attempts, including the two errors. Both full runs used `JOBS=32` and could run at most 18 tasks concurrently. Terra has no completed full-run wall time. The canceled Terra batches ran at different limits, so their task durations are not a comparable latency sample.

## Token use and normalized credits

The OpenAI [Codex pricing page](https://developers.openai.com/codex/pricing), read 2026-10-06 for Sol and 2026-10-08 for Luna and Terra, publishes Standard-speed credits per million tokens. The normalization uses uncached input, cache creation at the uncached-input rate, cache reads and output:

| Requested model | Uncached input | Cache read | Output |
| --- | ---: | ---: | ---: |
| `gpt-6.1-sol` | 50 | 2.5 | 250 |
| `gpt-6-luna` | 2.5 | 0.25 | 12.5 |
| `gpt-5.6-terra` | 50 | 5 | 300 |

`credits = ((uncached_input + cache_creation) × input_rate + cache_read × cache_read_rate + output × output_rate) / 1,000,000`. Standard speed is an assumption; the runs do not record service tier. These are normalized credits, not USD and not measured Codex subscription allowance consumption. Reasoning-token detail is unreported and is not added to output. Cache creation was zero where reported.

The table covers every recorded smoke, full and retry run, plus finalized task artifacts from the two canceled Terra runs. “Known subtotal” excludes attempts with missing token buckets; it is not a campaign total. It includes failed attempts where their usage was reported.

| Model | Attempts | Known uncached input / cache read / cache creation / output tokens | Known credit subtotal | Usage unknown |
| --- | ---: | --- | ---: | ---: |
| Sol 6.1 | 28 | 1,108,183 / 12,558,336 / 0 / 106,473 | 113.42 | 7 attempts |
| Luna 6 | 22 | 992,167 / 8,958,464 / 0 / 90,209 | 5.85 | 2 attempts |
| Terra 5.6 | 38 | 609,120 / 4,614,656 / 0 / 64,871 | 72.99 | 23 attempts |

Sol's complete 18-attempt full batch used 104.44 normalized credits. It produced 14 valid score-1 results, so that batch's measured cost per valid pass was 7.46 credits, with failed and invalid attempts in the numerator. The other per-success campaign estimates are unavailable: Luna's two disconnect rows have no usage buckets; Terra's interrupted tasks and one disconnect have no usage; Sol has two schema-v3 smoke rows without token fields and five model-selection errors without token usage. The five model-selection errors reported no model turn; their missing buckets remain unreported, not zero.

No judge or helper calls ran in these model-class tasks. Campaign totals are incomplete because the canceled runs and several failure rows lack token usage. The table therefore does not establish a complete relative cost ranking.

## Recommendation and limits

**Recommendation: evidence inconclusive; do not retire Terra on this comparison.** Luna's recovered results are uniformly successful and its known normalized credit subtotal is much lower. That does not answer whether Terra can be retired: Terra has no completed 18-attempt run, its partial records duplicate cases, and 23 Terra campaign attempts lack token buckets. Sol also has no valid `career-469` score. The six-case, three-repeat suite is a small sample from one repository. It does not measure reasoning-role suitability or plugin-following behavior, and `model_served` is unknown. No model defaults or retirement settings change here.

### Provenance records

- [Sol full run](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-38-45.json)
- [Luna full run](../../evals/provenance/classes-luna-6-2026-10-09-2026-10-09_19-52-53.json)
- [Luna `career-141` retry](../../evals/provenance/classes-smoke-luna-6-2026-10-09-2026-10-09_20-05-37.json)
- [Luna `career-469` retry](../../evals/provenance/classes-smoke-luna-6-2026-10-09-2026-10-09_20-10-04.json)
- [Sol smoke and corrected `career-462` retry](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_18-12-37.json), [corrected smoke](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_18-21-32.json), [additional `career-462` retry](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_19-02-13.json), [corrected-grader `career-469` timeout](../../evals/provenance/classes-smoke-sol-6-1-2026-10-08-2026-10-08_19-06-53.json)
- [Luna smoke](../../evals/provenance/classes-smoke-luna-6-2026-10-08-2026-10-08_18-24-17.json); [Terra smoke](../../evals/provenance/classes-smoke-terra-5-6-2026-10-08-2026-10-08_18-29-58.json)
- Sol model-selection failures: [two attempts](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-52-27.json) and [three attempts](../../evals/provenance/classes-sol-6-1-2026-10-08-2026-10-08_18-55-17.json)
