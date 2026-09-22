# GPT 5.6 Sol Omp slice: invalid-instrument amendment

**Status:** observed with limits, 2026-09-16; amended 2026-09-22.
**Records:** [#208](https://github.com/jmcvetta/daily-driver/issues/208).
**Provenance:** [`omp-gpt-5-6-sol-2026-09-16-2026-09-16_18-01-07.json`](../../evals/provenance/omp-gpt-5-6-sol-2026-09-16-2026-09-16_18-01-07.json).

This is the frozen two-arm Omp run `2026-09-16_18-01-07`. It has 40
attempts: five repeats of `bare` and `with-plugin` for each of four rows.
The raw artifacts remain outside Git. The committed provenance record preserves
the observed scores, requested identity, and run timestamps; figures below cite
that record.

## Scope and identity

The experiment requested `openai-codex/gpt-5.6-sol` in both Omp variants.
`model_used` and `environment_info.omp_model` repeat that pin, but Omp provided
no backend served-model evidence. The record therefore reports
`model_served: unknown`. The task artifacts also record the historical plugin
revision as `unknown`; the record's `plugin_revision` and `recorded_at` describe
the checkout and time of this later recording, not the revision that served the
2026-09-16 run. This is not a confirmed GPT family or tier measurement.

This slice differs from the GLM slice. It used
`constitution-reaches-subagent`, `deps-02-dependabot-is-complaining`,
`deps-03-neg-one-named-dependency`, and the Omp-only
`deps-05-references-search-not-list-omp`; it is not a relabelled copy of GLM's
positive or judged rows.

`reply-is-concise` is excluded. Issue #195 remains open, and this subject has
no pre-registered, re-derived word bands.

## Per-replicate results

Each delta is `with-plugin - bare`, paired by replicate. The scores are raw
historical observations from the record, not all valid measurements.

| Row | bare scores | with-plugin scores | paired deltas | reading |
| --- | --- | --- | --- | --- |
| `constitution-reaches-subagent` | 0.250, 0.250, 0.250, 0.500, 0.250 | 0.750, 1.000, 1.000, 0.750, 0.750 | +0.500, +0.750, +0.750, +0.250, +0.500 | valid delivery observations |
| `deps-02-dependabot-is-complaining` | 0.000, 0.000, 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000, 0.000, 0.000 | 0.000, 0.000, 0.000, 0.000, 0.000 | invalid instrument; raw scores retained only |
| `deps-03-neg-one-named-dependency` | 1.000, 1.000, 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | 0.000, 0.000, 0.000, 0.000, 0.000 | valid no-fire observations |
| `deps-05-references-search-not-list-omp` | 0.000, 0.000, 0.000, 0.000, 0.000 | 0.333, 0.333, 0.333, 0.333, 0.333 | +0.333, +0.333, +0.333, +0.333, +0.333 | trigger component only; judged finding unmeasured |

The constitution row completed its file and command criteria, so its deltas
remain usable delivery observations. The negative row's five scores in each arm
mean no `deps` engagement on a named single dependency. That is the expected
passing no-fire result, not a task score of zero.

## Invalid and unmeasured criteria

The positive `deps-02` treated attempts all logged an early-stop pass for
`skill_triggered` and then finalized that same criterion as zero. The pre-fix
abort-settle path dropped the in-flight skill event from the frozen trajectory.
The raw zero scores do not show that GPT failed to trigger `deps`, and their
zero deltas do not measure the plugin effect. [PR #278](https://github.com/jmcvetta/daily-driver/pull/278)
describes the corrected Omp adapter and its settle invariant. No subject turn
was re-run for this amendment.

The Omp-only judged row has a separate limit. Each of its ten `agent_judge`
calls ended with `AgentCrashError: Failed to authenticate: OAuth session
expired and could not be refreshed`. The treated 0.333 score comes only from
its `skill_triggered` criterion; all five +0.333 deltas establish that trigger
component, not the rubric's finding. The preserved transcripts may receive an
owner-authorized evaluate-only regrade after login. They do not supply verdicts
now.

The subject was the named Omp model, but `agent_judge` used `claude-sonnet-5`
through the Claude subscription, as [0014](0014-the-judge-runs-on-the-subscription.md)
decides. The failed judge is therefore neither a GPT judgment nor evidence of
an unfavorable model answer.

No model-family conclusion combines the invalid positive row with the
unmeasured judged criterion. The run is frozen: prompts, rubrics, weights, rows,
and all 40 attempts remain as recorded, and this amendment does not add a
configuration, adapter change, or replacement subject run.
