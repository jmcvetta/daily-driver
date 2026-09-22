# DeepSeek v4 Pro on the Omp arm

**Status:** measured, 2026-09-22.

**Experiment:** `omp-deepseek-v4-pro`.

**Run:** `2026-09-22_19-48-07`.

**Record:** [`evals/provenance/omp-deepseek-v4-pro-2026-09-22-2026-09-22_19-48-07.json`](../../evals/provenance/omp-deepseek-v4-pro-2026-09-22-2026-09-22_19-48-07.json).

## What was measured

This was one frozen, resumed run. It used the fixed Omp abort-settle instrument and the four selected files:

- `tasks/constitution/reaches-subagent.yaml`
- `tasks/deps/01-slash-deps.yaml`
- `tasks/deps/03-neg-one-named-dependency.yaml`
- `tasks/session-title/07-one-call-sets-the-title-omp.yaml`

The run kept the `bare` and `with-plugin` variants, five replicates per row and variant, and the subscription judge. It ran 40 attempts. There were 26 successful attempts, 14 failed attempts and no attempt-level errors. A failed criterion is a result, not a reason to buy a replacement run.

The run resumed the existing `2026-09-22_19-48-07` directory. Completed replicates stayed in place. The resume command used the same experiment, task selector, model and exclusion set; coder-eval warned only that the exclusion tags were listed in a different order in the resume command. No prompt, rubric, weight, row or replicate was changed.

The requested Omp model was `vercel-ai-gateway/deepseek/deepseek-v4-pro`. `omp models find deepseek-v4-pro` listed that model under `vercel-ai-gateway`. The recorder reports `model_served: unknown` for Omp by design. The task artifacts' `model_used` and `environment_info.omp_model` repeat the requested route; they do not prove which backend served a request. This note therefore does not claim confirmed backend family or tier.

The subject model was the requested Omp model. The `agent_judge` criterion in the session-title row used `claude-sonnet-5` on the subscription. The selected files contained no enabled `llm_judge` criterion; the exact preflight reported that fact. This judge asymmetry is part of the measurement.

## Per-replicate scores and deltas

Scores are in replicate order `00, 01, 02, 03, 04`. Delta is `with-plugin - bare`.

| Task | Bare | With plugin | Delta |
| --- | --- | --- | --- |
| `deps-03-neg-one-named-dependency` | `1.000, 1.000, 1.000, 1.000, 1.000` | `1.000, 1.000, 1.000, 1.000, 1.000` | `0.000, 0.000, 0.000, 0.000, 0.000` |
| `deps-01-slash-deps` | `0.000, 0.000, 0.000, 0.000, 0.000` | `1.000, 1.000, 1.000, 1.000, 1.000` | `+1.000, +1.000, +1.000, +1.000, +1.000` |
| `constitution-reaches-subagent` | `0.500, 0.500, 0.500, 0.500, 0.500` | `1.000, 1.000, 1.000, 1.000, 1.000` | `+0.500, +0.500, +0.500, +0.500, +0.500` |
| `session-title-07-one-call-sets-the-title-omp` | `0.333, 0.000, 1.000, 0.000, 0.000` | `1.000, 1.000, 1.000, 1.000, 1.000` | `+0.667, +1.000, 0.000, +1.000, +1.000` |

The aggregate report gives mean score `0.442` for `bare` and `1.000` for `with-plugin`. The paired mean difference is `+0.558` for `with-plugin - bare`, with 95% CI `[-0.117, +1.234]`, Cohen's `d = 1.31`, and `p = 0.078`. The interval crosses zero. The result is reported without a favorable-effect claim.

The negative row is a passing no-fire result in both variants. Its score of `1.000` is not evidence that the task fired.

## Criterion errors

The treated arm passed every criterion in all 20 replicates. Its error set is empty.

The bare-arm failures were:

- `deps-01-slash-deps`, replicates `00`–`04`: `skill_triggered` scored `0.0`; the observed value was `no` rather than the expected `yes` for `deps`.
- `constitution-reaches-subagent`, replicates `00`–`04`: `file_matches_regex` scored `0.0`; `voice:.*Doubt outranks the register` was not found in `subagent-report.txt`. The other two criteria passed.
- `session-title-07-one-call-sets-the-title-omp`, replicate `00`: `agent_judge` scored `0.0`; the reply was raw file-listing output and did not name `daily_driver_set_session_title`.
- The same row, replicate `01`: `skill_triggered` scored `0.0` with observed `no`; `agent_judge` scored `0.0` because the reply was a documentation-file error and did not name the call.
- The same row, replicate `02`: all criteria passed.
- The same row, replicate `03`: `skill_triggered` scored `0.0` with observed `no`; `agent_judge` scored `0.0` because the reply was configuration-list output and did not name the call.
- The same row, replicate `04`: `skill_triggered` scored `0.0` with observed `no`; `agent_judge` scored `0.0` because the reply listed tool attributes instead of naming the call.

No criterion reported an authentication failure. The failures above are model outputs or routing outcomes, not discarded tool events. The raw per-replicate `task.json` files remain in the ignored run directory.

## Invalid pre-fix evidence

The earlier 40-replicate run, `evals/runs/2026-09-16_18-13-11/`, remains untouched and is not merged into these results. It used the pre-fix Omp adapter. All five treated positive replicates early-stopped on `skill_triggered`, but the final trajectory lost the event. That run is evidence of the invalid instrument, not a replacement measurement and not a score comparison with this run.

## Gates

Before the paid run:

- `make evals-plan` passed for the repository experiment set.
- `make evals-preflight TASKS='tasks/constitution/reaches-subagent.yaml tasks/deps/01-slash-deps.yaml tasks/deps/03-neg-one-named-dependency.yaml tasks/session-title/07-one-call-sets-the-title-omp.yaml'` passed.
- `omp models find deepseek-v4-pro` found the configured gateway route.
- `make check-omp-agent-settle` passed.
- `make check-eval-arms` passed after the gateway route was aligned in the guard and model-set table.

The exact run command resumed the frozen run directory rather than selecting `latest`. The raw run remains outside git under `evals/runs/`; the committed provenance record is the durable citation for the measured figures.
