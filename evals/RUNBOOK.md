# Reviewer-quality campaign runbook

The ordered procedure for a paid reviewer-quality campaign: preflight,
calibration, smoke, cohort, record, report. It exists because the same
recovery steps were being rediscovered from prose and from provenance JSON.
The suite's measurement contract stays in [`README.md`](README.md); this file
owns the operating order and the actions each terminal state permits.

Nothing here starts a campaign. Each paid phase needs the authority the task
names, and a stop is a stop.

## Inputs

- `JUDGE`: a judge id under `evals/judges/`, for example `omp-gpt-6.1-sol`.
- One experiment per arm under `evals/experiments/`, each pinning exactly one
  route overlay under `evals/fixtures/*/shared/routes/`.
- The eight frozen cases in `evals/tasks/reviewer-quality/`.

Arm names are the `--arm` values in `scripts/evals-reviewer-run.py`. Do not
copy an arm table from one campaign into another; the experiment and overlay
are the source.

## Phases

Run from the repository root, in this order. Every attempt in a campaign runs
serially: `--max-parallel 1` is fixed in the runner and the runner holds one
active arm.

| Phase | Command | Cost | Gate |
| --- | --- | --- | --- |
| Install | `make evals-install && make evals-setup-omp` | free | `omp` and the pinned `coder-eval` resolve |
| Plan | `make evals-plan-reviewer-quality` | free | every arm registers and plans |
| Preflight | `make evals-campaign-preflight JUDGE=<id>` | free, read-only | no `fail` line |
| Judge preflight | `make evals-judge-preflight JUDGE=<id>` | free | `evals/tasks-judged/reviewer-quality/` holds all eight cases |
| Calibrate | `uv run --frozen python3 scripts/evals-judge.py calibrate --judge <id> --dir <labels> --output <record>` | paid, small | the calibration meets its acceptance rule |
| Smoke | `python3 scripts/evals-reviewer-run.py --arm <arm> --phase smoke --run-dir evals/runs/<campaign>/<arm>-smoke` | paid | the collected smoke passes |
| Collect smoke | `python3 scripts/evals-reviewer-quality.py --arm <arm> --experiment <experiment> --run-dir <smoke-dir> --repeats 1 --output evals/provenance/reviewer-quality/<arm>-smoke.json` | free | exit 0; `gate.valid` is true |
| Cohort | `python3 scripts/evals-reviewer-run.py --arm <arm> --phase cohort --run-dir evals/runs/<campaign>/<arm>-cohort --smoke-record evals/provenance/reviewer-quality/<arm>-smoke.json` | paid | a fresh run directory; no retry |
| Collect cohort | `python3 scripts/evals-reviewer-quality.py --arm <arm> --experiment <experiment> --run-dir <cohort-dir> --repeats 5 --output evals/provenance/reviewer-quality/<arm>-cohort.json` | free | exit 0 on a complete cohort; exit 3 records invalid evidence |
| Report | `make evals-render-results` and the approved report update | free | the rendered rows agree with the record |

Notes:

- The preflight is read-only. Its usage probe reads the provider's own balance
  report and never spends.
- The judge calibration is a paid inference step. A prior calibration for
  another route, model, prompt version or label set does not transfer.
- `--allow-invalid` on the collector exists only to regenerate historical
  evidence. Never use it for a campaign.
- Keep `evals/runs/latest` out of a campaign. Name every run directory.
- A smoke is two attempts, `01-boundary` and `05-clean-boundary`, once per arm.
  It is excluded from cohort metrics.
- The smoke artifact must come from the current collector and carry
  `coverage`. An older smoke record without it is refused; collect the smoke
  again rather than editing the record.

## Terminal states and the only permitted action

The collector writes the status and the cause; the runbook says what may
happen next. In every row, preserve the record and the run directory.

| State | Meaning | Permitted action | Evidence |
| --- | --- | --- | --- |
| `provider_error` | The provider refused the request: quota, rate limit, `402`, or insufficient funds. | Stop the process group. Do not retry, switch provider, buy credit, or change a plan. Resume only on explicit operator authorization and with a fresh run directory. | `provider-stop.json`; `attempts[].error`; `gate.reasons` |
| `harness_error` | The harness or adapter failed before a reviewer result. | Read `attempts[].error` (`message`, `category`, `component`, `stderr_tail`), fix the cause, then rerun the affected slot only with authorization. Never count it as a model result. | `attempts[].error`; the local task log |
| `interrupted` | The run stopped before a terminal evaluator record. | Keep the original log. Write a clearly labelled synthetic `ERROR` `task.json` so `coder-eval --resume` cannot replay the slot. Rerun the slot only with authorization. | the synthetic record; the original log |
| `judge_error` | The judge could not grade a completed reviewer result. | Do not rerun the subject. Fix the calibration or the label definitions, recalibrate, and regrade the preserved responses. | the judge sidecar and the calibration record |
| `attribution_mismatch` | The delivered reviewer result, the parent's final JSON, or the adapter's resolved route disagree. | Treat the attempt as unattributable. Fix the capture path (the parent calls `wait` immediately after dispatch), then rerun with authorization. | `attribution.mismatches`; `attempts[].reviewer_telemetry` |
| `delivery_unverified` | A final response exists but no completed reviewer result was captured. | Same as `attribution_mismatch`: fix capture, rerun with authorization, never infer the reviewer wrote it. | `attempts[].reviewer_delivery_observed` |
| `unreported` cost | The reviewer usage or its price card is missing. | Record `unreported`. Never record zero, never use the parent's cost, and do not claim a measured-cost comparison. | `summary.reviewer_telemetry`; the price tables |
| smoke gate failed | The smoke record does not meet the cohort conditions. | Do not dispatch the cohort. Fix the named condition and collect a new smoke. | the collector's `gate.reasons`; the runner's refusal |

## Stop and resume

- Stop new dispatch on provider pushback. The wrapper writes
  `provider-stop.json` and terminates the process group.
- Do not purchase credit, change a plan, migrate credentials, or evade a limit.
  A fallback provider, model, upstream, or effort is not a permitted recovery.
- Refused slots are not model results. They keep their place in the record and
  are rerun only in fresh run directories with explicit authorization.
- Recalibration after a prompt or label change is a separate paid step. It does
  not authorize the subject cohort.
- A stop leaves the record publishable. The collector writes the artifact
  before it exits, and a partial cohort is reported as partial.

## Pointers

- [`README.md`](README.md): the reviewer-quality contract, metrics and the
  accepted evidence.
- `scripts/evals-campaign-preflight.py`: the checks and their remedies.
- `scripts/evals-reviewer-quality.py`: the evidence gate, `error_causes`, and
  the per-attempt `error` object.
- `scripts/evals-reviewer-run.py`: the smoke prerequisite and provider stop.
