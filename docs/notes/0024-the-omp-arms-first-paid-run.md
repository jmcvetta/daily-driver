# The Omp arm's first paid run

**Status:** measured, 2026-09-22.
**Records:** [scores and run metadata](../../evals/provenance/omp-glm-5-3-2026-09-22-2026-09-22_14-39-00.json) and [attempt evidence](../../evals/provenance/omp-glm-5-3-2026-09-22-2026-09-22_14-39-00-evidence.json).

Issue #206 ran the authorized replacement once. The earlier GLM attempt and
its raw artifacts are unrecorded. This note does not use them as evidence.

## Instrument and scope

The run used `omp-glm-5-3`, revision `54f4b79df07aaaaab3c8f46295286cd4fde05d28`,
and `coder_eval` 0.11.6. It ran the bare and `with-plugin` Omp variants five
times against these four rows:

- `constitution-reaches-subagent`
- `deps-01-slash-deps`
- `deps-03-neg-one-named-dependency`
- `session-title-07-one-call-sets-the-title-omp`

That is 40 attempts. All finished and their preserved sandboxes remain at
`evals/runs/2026-09-22_14-39-00/` until this pull request merges. The committed
records above preserve every score, status, criterion result, protocol capture,
and cost figure used below.

## Scores

| Row | bare scores | with-plugin scores | paired delta, with-plugin - bare |
| --- | --- | --- | --- |
| `constitution-reaches-subagent` | 0.500, 0.500, 0.500, 0.500, 0.500 | 1.000, 1.000, 1.000, 1.000, 1.000 | +0.500, +0.500, +0.500, +0.500, +0.500; mean +0.500 |
| `deps-01-slash-deps` | 0.000, 0.000, 0.000, 0.000, 0.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | +1.000, +1.000, +1.000, +1.000, +1.000; mean +1.000 |
| `deps-03-neg-one-named-dependency` | 1.000, 1.000, 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000, 1.000, ERROR | 0.000, 0.000, 0.000, 0.000, n/a; mean 0.000 over four measured pairs |
| `session-title-07-one-call-sets-the-title-omp` | 0.333, 0.000, 0.000, 0.000, 0.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | +0.667, +1.000, +1.000, +1.000, +1.000; mean +0.933 |

The measured bare mean was 0.392 across 20 attempts. The measured treated mean
was 1.000 across 19 attempts. `coder_eval` reports 0.950 for the treated arm
only because it retains the timed-out attempt's raw 0.000 placeholder. That is
an error-as-zero aggregate, not a measured score or a valid paired delta.
The results are recorded as observed; they are not grounds for another paid run.

## Every attempt and error

24 attempts succeeded, 15 finished with a failed criterion, and one ended in
an execution error. No criterion result carried an internal error. The evidence
record lists the status, result, and capture output for every attempt.

- All five bare constitution attempts missed
  `voice:.*Doubt outranks the register` in `subagent-report.txt`.
- All five bare `/deps` attempts observed no `deps` skill.
- Bare session-title attempt 0 fired the skill but its `agent_judge` scored
  0.000. Attempts 1–4 observed neither the skill nor a passing judge result.
- The negative one-dependency row correctly reported no bulk-dependency
  engagement in all five bare attempts and in treated attempts 0–3. Those are
  passing no-fire results.
- Treated negative-row attempt 4 timed out after 120 seconds. It is an
  unmeasured error, not a no-fire result or a model failure.

## Protocol evidence and limits

Every task's `post_run_results` contains readable adapter evidence. Thirty-nine
attempts recorded `{"omp_argument_keys_seen":["args"],"omp_usage_keys_seen":[]}`.
The timed-out attempt recorded the explicit empty observation. The run therefore
observed `args` for tool arguments and did not observe a usage-accounting key.
`environment_info` contains only startup routing and plugin facts.

The subject requested `vercel-ai-gateway/zai/glm-5.3`. Both `model_used` and
`environment_info.omp_model` repeat that request. Omp did not supply backend
identity evidence, so the served model is **unknown**. This is not a verified
full-GLM identity claim.

The session-title `agent_judge` used `claude-sonnet-5` through the Claude
subscription. It is a separate Claude judge path, while the measured subject
uses Omp through Vercel AI Gateway. Omp RPC does not enforce the configured tool
allowlist. It also provided no observed token-usage key. The recorded
$0.5809576 is judge overhead, not a complete subject-run cost: `coder_eval`
has no price for the GLM gateway route.
