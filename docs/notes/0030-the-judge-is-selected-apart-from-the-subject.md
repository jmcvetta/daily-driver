# The judge is selected apart from the subject

**Status:** decided, 2026-10-05.
**Resolves:** [#542](https://github.com/jmcvetta/daily-driver/issues/542).
**Amends:** [`0014`](0014-the-judge-runs-on-the-subscription.md) — its rule
stays, and becomes conditional on the judge being Claude.
**Builds on:** [`0013`](0013-the-omp-arm.md), whose adapter, throwaway home and
tool boundary the new route reuses.

**Observed.** Every semantic criterion in `evals/tasks/` pins an
`agent_judge` on the Claude Code agent and `claude-sonnet-5`. An experiment that
runs an Omp subject changes `agent.type` for the subject only. So an
independent Omp run still needed a Claude Code session, for its judge.

`coder_eval` 0.11.6 does not let that be configured. `AgentJudgeCriterion.agent`
is the closed built-in agent union; `AgentJudgeChecker` builds a
`ClaudeCodeAgentConfig` and runs it through `SubAgentRunner`, which constructs
`ClaudeCodeAgent`. The `coder_eval.plugins` seam registers agent kinds and
nothing else, and the success-criterion union has no extension hook. An earlier
attempt at #542 stopped here and called a supported route missing. The route
exists if the grade is taken out of `coder_eval` and the rest left in it.

## Decided

**The subject still runs under `coder_eval`; the semantic grade is a separate,
repo-owned stage over the preserved transcripts.**
[`scripts/evals-judge.py`](../../scripts/evals-judge.py) owns it. No fork, no
patched checker, no second criterion model.

- **A judge is a committed definition** in [`evals/judges/`](../../evals/judges/):
  `route` (`claude-code` or `omp`), an explicit `model`, `settings`, and a
  `status`. `JUDGE=<id>` selects it for a run, apart from the experiment's
  subject. The model is never inferred from the subject or a role default, and
  the definition loader refuses `default`, `auto`, an unknown key, and an
  Anthropic model on the Omp route.
- **The Claude route is unchanged.** It is each task's pinned `agent_judge`,
  run by `coder_eval` from a Claude Code session. Naming it with
  `JUDGE=claude-code-sonnet-5` only adds two refusals: a task pinning another
  judge, and a run outside a Claude Code session.
- **The Omp route grades a transcript and nothing else.** `make
  evals-judge-preflight` writes `evals/tasks-judged/`, the same tasks with every
  `agent_judge` set `enabled: false`; `coder_eval` runs the deterministic criteria
  there and skips the Claude judge. After the run, `evals-judge.py judge-run`
  reads the **original** task's rubric, unchanged, and the preserved `task.json`,
  and runs `omp -p --no-tools` with every discovery switch off, in an empty
  directory, in a throwaway home with the provider files of `0013` and none of
  the person's own. A criterion that needs `files:` or the reference is refused,
  because a judge without tools cannot read them and a thinner transcript would
  grade a different question.
- **Deterministic criteria stay the authority.** Nothing here grades a command,
  a fixture or a forbidden operation. `materialize` changes one key, `enabled`,
  on `agent_judge` criteria and nothing else.
- **A judge error is an evaluation error.** Unavailable, timed out, transport
  failure, and a reply that is not exactly one `{score, rationale, findings}`
  object are all recorded as errors with no score. The replicate's score is null
  and its case outcome is `error`. There is no retry and no other judge, the
  subject's model included. `preflight` refuses an unavailable judge before any
  subject starts, and leaves no task tree behind.
- **A judge is frozen for a comparison.** `freeze_sha` hashes route, model,
  settings, the judge prompt version and every rubric. It is in each sidecar and
  in the record's `judge` object. Different judges, or different hashes, are
  different measurements.
- **Judge identity is recorded apart from the subject's**, as requested and as
  observed. Omp reports the model and usage of each judge call; where a route
  reports none, the record says `unavailable` and does not fill it from the
  configured name. Records that predate this keep their task-pinned Claude judge
  and no observed identity.
- **Adoption needs calibration.** [`calibration/labels.yaml`](../../evals/judges/calibration/labels.yaml)
  holds 11 hand-labelled transcripts and the acceptance rule, committed
  (`c47417a`) before any candidate ran. The rubric is read from
  `undertake-09-title-before-claim-omp`, not copied. A judge is `validated` only
  with a committed result that met the rule against the current labels, and
  `make check-agent-judges` enforces that. A candidate that fails stays
  `candidate`; the fixture is not tuned to it. The default judge stays Claude.

## What was measured

All of it live, on 2026-10-05, on Omp 18.6.1 with
`vercel-ai-gateway/zai/glm-5.3`, from a container with no Claude session
involved in the judging.

| What | Result |
| ---- | ------ |
| Calibration, `omp-glm-5.3`, one pass over the 11 labels | 11 of 11 reproduced; 0 false passes; 0 errors; rule **met** ([`observed/omp-glm-5.3.json`](../../evals/judges/calibration/observed/omp-glm-5.3.json)) |
| Smoke: Omp subject on `undertake-09-title-before-claim-omp`, both variants, one repeat, judged by `omp-glm-5.3` | both replicates judged, no errors; `bare` 0.167, `with-plugin` 1.0, the same on a second `judge-run` of the same transcripts; each judged criterion carries its rationale, observed model and usage. Recorded as [`omp-glm-5-3-2026-10-05-2026-10-05_15-08-44.json`](../../evals/provenance/omp-glm-5-3-2026-10-05-2026-10-05_15-08-44.json) |

The calibration sample is one rubric and eleven constructed transcripts. It
shows this judge reproduces a human reading of that rubric, including a
fabricated narration, a wrong order, a forbidden client and a grade injected into
the transcript. It does not rank GLM 5.3 against any other judge, and it does not
say the judge agrees with Claude on rubrics it was not shown. That agreement was
not measured and is not claimed.

## What this does not do

- It does not run the GPT 6 matrix of [#481](https://github.com/jmcvetta/daily-driver/issues/481).
- It does not judge criteria that read sandbox files or the reference. Those
  stay on the Claude route.
- It does not make a panel: one judge per run.
- It does not put judge cost in the subject's price. A run-selected judge's
  usage is under `judge.usage`, and `judge.price_included_in_cases` is `false`.
- It does not change the Claude rule of `0014`. No Anthropic model goes through
  the gateway or a metered API, and no OAuth token is sought, moved or asked for.
