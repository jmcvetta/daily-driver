# GPT 5.6 Sol: the Omp two-arm slice

**Status:** observed, 2026-09-16.
**Records:** [#208](https://github.com/jmcvetta/daily-driver/issues/208).
**Run:** `evals/runs/2026-09-16_18-01-07`, experiment
`omp-gpt-5-6-sol`, subject model `openai-codex/gpt-5.6-sol`.

The requested slice ran once, with five replicates of both `bare` and
`with-plugin`:

- `tasks/constitution/reaches-subagent.yaml`;
- `tasks/deps/02-dependabot-is-complaining.yaml`, the positive trigger row;
- `tasks/deps/03-neg-one-named-dependency.yaml`, the negative trigger row; and
- `tasks/deps/05-references-search-not-list-omp.yaml`, the ported `omp-only`
  judged row.

`reply-is-concise` was not run. Issue #195 remains open and this model has no
pre-registered, re-derived word bands. The exact invocation was:

```sh
make evals-run-omp-gpt-5-6-sol \
  TASKS='tasks/constitution/reaches-subagent.yaml tasks/deps/02-dependabot-is-complaining.yaml tasks/deps/03-neg-one-named-dependency.yaml tasks/deps/05-references-search-not-list-omp.yaml'
```

The run completed all 40 replicates and wrote `experiment.md`; `make` returned
2 because 28 replicates failed their task criteria, not because the run was
aborted. The report records 12/40 successful replicates.

## Per-replicate scores

These are each task's `weighted_score`. Delta is `with-plugin - bare`, paired
by replicate; it is shown per replicate rather than inferred from the means.

| Task | Replicate | bare | with-plugin | Delta |
| --- | ---: | ---: | ---: | ---: |
| `constitution-reaches-subagent` | 00 | 0.250 | 0.750 | +0.500 |
| `constitution-reaches-subagent` | 01 | 0.250 | 1.000 | +0.750 |
| `constitution-reaches-subagent` | 02 | 0.250 | 1.000 | +0.750 |
| `constitution-reaches-subagent` | 03 | 0.500 | 0.750 | +0.250 |
| `constitution-reaches-subagent` | 04 | 0.250 | 0.750 | +0.500 |
| `deps-02-dependabot-is-complaining` | 00 | 0.000 | 0.000 | 0.000 |
| `deps-02-dependabot-is-complaining` | 01 | 0.000 | 0.000 | 0.000 |
| `deps-02-dependabot-is-complaining` | 02 | 0.000 | 0.000 | 0.000 |
| `deps-02-dependabot-is-complaining` | 03 | 0.000 | 0.000 | 0.000 |
| `deps-02-dependabot-is-complaining` | 04 | 0.000 | 0.000 | 0.000 |
| `deps-03-neg-one-named-dependency` | 00 | 1.000 | 1.000 | 0.000 |
| `deps-03-neg-one-named-dependency` | 01 | 1.000 | 1.000 | 0.000 |
| `deps-03-neg-one-named-dependency` | 02 | 1.000 | 1.000 | 0.000 |
| `deps-03-neg-one-named-dependency` | 03 | 1.000 | 1.000 | 0.000 |
| `deps-03-neg-one-named-dependency` | 04 | 1.000 | 1.000 | 0.000 |
| `deps-05-references-search-not-list-omp` | 00 | 0.000 | 0.333 | +0.333 |
| `deps-05-references-search-not-list-omp` | 01 | 0.000 | 0.333 | +0.333 |
| `deps-05-references-search-not-list-omp` | 02 | 0.000 | 0.333 | +0.333 |
| `deps-05-references-search-not-list-omp` | 03 | 0.000 | 0.333 | +0.333 |
| `deps-05-references-search-not-list-omp` | 04 | 0.000 | 0.333 | +0.333 |

## What the scores say

The constitution marker itself separated cleanly: its weight-2
`file_matches_regex` criterion scored 0 in every bare replicate and 1 in every
with-plugin replicate. The `Agent` telemetry criterion was less stable. It
scored 1 in bare replicate 03 and with-plugin replicates 01 and 02, and 0 in
the other seven, producing the varying task-level scores above. The negative
trigger held at 1.000 in all ten replicates. The positive trigger did not fire
in either arm: all ten replicates scored 0.000.

The judged row needs a separate reading. Its `deps` trigger scored 0 in every
bare replicate and 1 in every with-plugin replicate, which alone produces the
0.333 treated score because the judge has weight 2. The judged finding did not
produce a score: every `agent_judge` invocation returned 0 with
`AgentCrashError: Failed to authenticate: OAuth session expired and could not
be refreshed`.

## The judge is asymmetric

The subject in both arms is GPT 5.6 Sol, but the judge is not. The
`agent_judge` configured to grade both arms is `claude-sonnet-5`, launched by
the Claude Code agent and authenticated through the Claude subscription, as
[`0014`](0014-the-judge-runs-on-the-subscription.md) records. Both arms were
sent to that Claude judge. In this run all ten judge calls failed before a
verdict because the subscription OAuth session had expired. The +0.333 deltas
on the judged row therefore establish treated-arm skill triggering only; they
do not establish the rubric's finding and must not be read as GPT judging
GPT, or as a successful model-neutral judgment.
