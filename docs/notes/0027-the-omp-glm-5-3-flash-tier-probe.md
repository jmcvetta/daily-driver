# The Omp GLM 5.3 Flash tier probe

**Status:** measured, 2026-09-22.
**Provenance:** [`omp-glm-5-3-flash-2026-09-22-2026-09-22_19-48-37.json`](../../evals/provenance/omp-glm-5-3-flash-2026-09-22-2026-09-22_19-48-37.json).

Issue #270 measured the requested Flash route once, with the bare and
`with-plugin` variants. The retired session left a frozen run directory with
33 finalized attempts. The resumed run kept those results and completed the
seven missing attempts. No score-driven rerun occurred.

## Route, instrument and scope

Before the paid run, `omp models find glm-5.3-flash` resolved
`vercel-ai-gateway/zai/glm-5.3-flash` in the Vercel AI Gateway catalog. The
route reported a 1M context window, 131K maximum output, and image support.
The catalog proves availability at lookup time. It does not prove the backend
served the requested model.

The run used experiment `omp-glm-5-3-flash`, `coder_eval` 0.11.6, five repeats,
and these four rows in both variants:

- `constitution-reaches-subagent`
- `deps-01-slash-deps`
- `deps-03-neg-one-named-dependency`
- `session-title-07-one-call-sets-the-title-omp`

That is 40 attempts. The raw run remains in the ignored
`evals/runs/2026-09-22_19-48-37/` directory. The resume fingerprint remains
local run state outside Git. The committed record preserves all 40 attempts,
criterion results, scores, statuses, and protocol captures.

The corrected early-stop settle instrument was active for this run. Every
attempt preserved `omp-protocol-observations.json`. All 40 recorded
`omp_argument_keys_seen: ["args"]`; none recorded a usage key. The instrument
therefore observed the RPC argument field but did not establish token-usage
accounting.

The preserved file observations remain in each attempt's `protocol_evidence`
and the record's `protocol_summary`. `post_run_results` are empty because the
retired run predates the capture block; the Flash experiment now carries the
same command for future runs.

The run recorded 25 successful attempts and 15 failed attempts. It recorded no
execution errors. One bare constitution attempt had a grader error because
`subagent-report.txt` did not exist; the record keeps that criterion error
separate from the four measured pattern misses. The bare arm's failures were
measured outcomes except for that invalid criterion result, not authentication
failures. The run-level judge overhead was `$0.7781364`; Omp subject cost was
unavailable because the Gateway route has no registered coder_eval price.

## Flash scores

| Row | bare scores | with-plugin scores | paired delta, with-plugin - bare |
| --- | --- | --- | --- |
| `constitution-reaches-subagent` | 0.500, 0.500, 0.500, 0.500, 0.500 | 1.000, 1.000, 1.000, 1.000, 1.000 | +0.500, +0.500, +0.500, +0.500, +0.500; mean +0.500 |
| `deps-01-slash-deps` | 0.000, 0.000, 0.000, 0.000, 0.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | +1.000, +1.000, +1.000, +1.000, +1.000; mean +1.000 |
| `deps-03-neg-one-named-dependency` | 1.000, 1.000, 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | 0.000, 0.000, 0.000, 0.000, 0.000; mean 0.000 |
| `session-title-07-one-call-sets-the-title-omp` | 0.000, 0.000, 0.000, 0.000, 0.000 | 1.000, 1.000, 1.000, 1.000, 1.000 | +1.000, +1.000, +1.000, +1.000, +1.000; mean +1.000 |

The bare mean was 0.375 across 20 attempts. The treated mean was 1.000
across 20 attempts. The overall paired mean delta was +0.625.

The negative dependency row is a passing no-fire result. Its score of 1.000
does not mean that the model engaged the forbidden bulk dependency path.

Criterion failures were stable across the bare repeats:

- Four bare constitution attempts missed `voice:.*Doubt outranks the register`.
  The third attempt (replicate index 2) has the
  `subagent-report.txt` grader error recorded above. The other two criteria
  passed in the four measured attempts.
- The bare `/deps` row did not trigger the `deps` skill in all five attempts.
- The bare session-title row did not trigger `session-title` and its
  `agent_judge` returned 0.0 in all five attempts.
- The treated arm passed every criterion in all 20 attempts.

The `agent_judge` criterion used Claude through the subscription. This is a
separate judge path from the Omp subject route. Its result cannot establish
which model served the Omp subject.

## Comparison with full GLM

The full-GLM run is recorded in
[`0024`](0024-the-omp-arms-first-paid-run.md). Its requested model was
`vercel-ai-gateway/zai/glm-5.3`; its served identity was also unknown. The
full-GLM paired deltas were:

| Row | full-GLM paired delta | Flash paired delta |
| --- | --- | --- |
| `constitution-reaches-subagent` | +0.500, +0.500, +0.500, +0.500, +0.500 | +0.500, +0.500, +0.500, +0.500, +0.500 |
| `deps-01-slash-deps` | +1.000, +1.000, +1.000, +1.000, +1.000 | +1.000, +1.000, +1.000, +1.000, +1.000 |
| `deps-03-neg-one-named-dependency` | 0.000, 0.000, 0.000, 0.000, n/a | 0.000, 0.000, 0.000, 0.000, 0.000 |
| `session-title-07-one-call-sets-the-title-omp` | +0.667, +1.000, +1.000, +1.000, +1.000 | +1.000, +1.000, +1.000, +1.000, +1.000 |

The full-GLM fifth treated negative-row attempt timed out and is unmeasured;
its report keeps a raw 0.000 placeholder, so the full-GLM treated aggregate
is not a valid paired comparison for that attempt. Flash had no execution
errors.

The full-GLM record names measured revision `54f4b79df07aaaaab3c8f46295286cd4fde05d28`.
The Flash task metadata records its source revision as `unknown`; the
provenance record's `plugin_revision` is the checkout used when recording the
artifact, not proof of the revision that served the run. The Flash artifacts
show the corrected settle instrument and its protocol captures, but they do
not provide backend-serving identity evidence.

Both records therefore support an ablation result for their requested model
pins. Neither supports a verified full-GLM-versus-Flash tier delta. The tier
identity acceptance item is **blocked** until genuine backend identity
evidence exists. The requested Flash pin is not proof that Flash was served.

## Limits

Omp RPC does not enforce the configured per-session tool allowlist. The
experiment records `allowed_tools: [Skill]`, but the adapter warns that this
is not a runtime boundary. Omp also supplied no usage-accounting key. These
limits apply to both variants and remain part of the measurement result.
