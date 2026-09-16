# The Omp arm's first paid run

**Status:** recorded, 2026-09-16.
**Provenance:** the run `evals/runs/2026-09-16_20-03-53`, launched 2026-09-16
20:03:53 local, on branch `issue-206-omp-first-paid-slice` at the paid run's
head (`848b9ee` + the instrument fix, see below). Implemented across three
sessions — `GlmPaidRun` (cancelled at laptop teardown), `GlmRunResume` (lost
with the watching session's teardown), `GlmRunRecovery` (this one).
**Resolves:** the run half of
[#206](https://github.com/jmcvetta/daily-driver/issues/206) — `0013`'s second
acceptance criterion, one paid run of a narrow slice, non-zero on a positive
row and zero on a negative one.
**Extends:** [`0013`](0013-the-omp-arm.md), whose open protocol questions this
run answers and whose second acceptance criterion this run closes.

The Omp arm had never touched a live model. This note records the first paid
slice — four rows, both arms, 5 replicates each, on `zai/glm-5.3` served
through `vercel-ai-gateway` — and the three things the run found that no
amount of offline checking could: a defect in the arm's own event handling,
the answer to the two protocol questions `0013` left open, and one row whose
judge could not run at all.

## The slice

| Row | What it is | Arm |
| --- | --- | --- |
| `constitution/reaches-subagent` | the constitution suite's reach row | both |
| `deps/01-slash-deps` | positive trigger row (fire) | both |
| `deps/03-neg-one-named-dependency` | negative trigger row (no-fire) | both |
| `session-title/07-one-call-sets-the-title-omp` | the ported `omp-only` judged row, standing in for `reply-is-concise` while [#195](https://github.com/jmcvetta/daily-driver/issues/195) is open | both, 5 replicates each |

`reply-is-concise` rides only once #195 closes; the judged `omp-only` row
takes its place, so the run also proves the judged path — the tagged
transcript `0013` says the agent renders, read by an `agent_judge`. One run,
both arms, 5 replicates. Re-running because the numbers were unwelcome is the
failure #195 exists to prevent; this task inherits the rule.

## The model, confirmed from the recording

Every one of the 40 replicates records `model_used` and
`environment_info.omp_model` as `vercel-ai-gateway/zai/glm-5.3` — the full
model the issue pins, through the one gateway this machine is credentialed
for. No Flash fallback appears anywhere in the 40; the pin was read mid-run,
while replicates were landing, rather than after the money was spent. The
Claude arm is not in this run; `experiments/with-without.yaml` keeps every
Claude suite pinned to `claude-sonnet-5`, and this run is the Omp arm's own.

`coder_eval` has no pricing rate for `vercel-ai-gateway/zai/glm-5.3`, so the
run-level cost totals understate the bill (`cost_complete` is false in the
report); the model's own usage accounting below is what the note carries.

## Per-replicate scores

Read per replicate, not the mean. Each cell is the replicate's
`weighted_score`; the criterion scores sit beside it. Run
`evals/runs/2026-09-16_20-03-53`, both arms, 5 replicates, sequential.

**`deps-01-slash-deps` — the positive trigger row** (`/deps`; `skill_triggered`
is the whole row):

| Replicate | 00 | 01 | 02 | 03 | 04 |
| --- | --- | --- | --- | --- | --- |
| bare | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| with-plugin | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

`skill_triggered` 0.0 in every bare replicate, 1.0 in every treated one. The
treated replicates early-stopped on the pass at the first tool call. Four of
the five bare replicates ran to the turn cap improvising, which is what an
untreated session does with a slash command it has no skill for; replicate 03
finished its answer normally inside the cap (5 assistant turns, 25s) and
failed only on the criterion — the no-fire reading is unaffected either way.

**`deps-03-neg-one-named-dependency` — the negative trigger row** (one named
dependency, version pinned; the skill must not fire):

| Replicate | 00 | 01 | 02 | 03 | 04 |
| --- | --- | --- | --- | --- | --- |
| bare engagement | none | none | none | none | none |
| with-plugin engagement | none | none | none | none | none |

The row scores 1.000 in all ten replicates because the criterion is a
distractor that passes in silence — the reading that matters for `0013`'s
criterion is the engagement it detects: **zero in both arms, ten of ten**. On
this arm the no-fire guarantee is weaker than on Claude Code by the known
limit recorded in `0013` (`disallowed_tools` is not enforced in Omp RPC), so
this row measures the model choosing silence, not a closed route.

**`constitution/reaches-subagent` — the reach row** (criteria: the weight-2
phrase the subagent writes, the `Agent` call, the parent-did-not-supply
control):

| Replicate | 00 | 01 | 02 | 03 | 04 |
| --- | --- | --- | --- | --- | --- |
| bare | 0.500 | 0.500 | 0.500 | 0.500 | 0.500 |
| with-plugin | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Five for five, and identical to the shape the Claude arm reports: bare
replicates fail the weight-2 phrase criterion exactly as designed (the
subagent writes `voice: NONE` because nothing reached it) while the tool
criteria hold, and every treated replicate carries the phrase its subagent
could only have received through the `PreToolUse` hook on the `Agent` tool.
The delivery finding reproduces off Claude: the parent's own prompt carried
no phrase (the negative control held in all ten), so the hook put it there.

**`session-title/07-one-call-sets-the-title-omp` — the judged row:**

| Replicate | 00 | 01 | 02 | 03 | 04 |
| --- | --- | --- | --- | --- | --- |
| bare | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| with-plugin | 0.333 | 0.333 | 0.333 | 0.333 | 0.333 |

**The judged criterion measured nothing in either arm.** Every `agent_judge`
verdict in this row — ten of ten, both arms — carries the same error beside
its 0.0: `Judge agent crashed before producing a verdict: CLI process failed
(exit code 1): Failed to authenticate: OAuth session expired and could not be
refreshed`. The judge transport is a `claude-code` session per the row's own
pin, and this machine's Claude OAuth is wiped (empty access and refresh
tokens; `claude -p` answers the same authentication failure). The 0.0 in the
report is the placeholder `coder_eval` records for a judge that produced no
verdict, with the crash in the `error` field beside it — not a judgment of
the reply.

What the row did measure: `skill_triggered` passed 1.0 in all five treated
replicates and 0.0 in all five bare ones, and the treated replies are intact
under the anchor the judge reads — each names `daily_driver_set_session_title`
with the title alone, no `get_session` lookup, and carries
`[RESULT - SUCCESS]`, so the transcript is judge-ready as rendered. The
unmeasured half is graded from the frozen transcripts, not re-run: after the
credential is renewed, `coder-eval`'s evaluate-only path re-grades the
preserved records for judge calls alone, without touching the agent turns
already paid for. That re-grade, and the OAuth re-login it waits on, are the
one item this run leaves open.

## The two protocol questions `0013` leaves open

`0013` leaves two questions to be answered by what a live run records:
which key a `tool_execution_*` frame carries its arguments under, and which
telemetry fields carry the token counts. Both are answered, per replicate,
in all 40:

- **`omp_argument_keys_seen: ["args"]`.** Every tool frame that carried
  arguments carried them under `args` — on `tool_execution_start`, with
  `tool_execution_update` repeating them for streaming calls.
- **`omp_usage_keys_seen: ["input", "output", "cacheRead", "cacheWrite"]`.**
  The counts sit in a `usage` dict on the last entry of `agent_end`'s
  `messages`, where `input` is the uncached slice — the four buckets sum to
  the frame's own `totalTokens`, so nothing is double-counted by leaving
  `totalTokens` out.

Two qualifications the run measured alongside the answers:

**The answers are recorded per replicate under `sdk_options`, not
`environment_info`, and that is a measurement, not a preference.** `0013` and
the issue name `environment_info` as the place these answers are recorded.
Measured on the live harness: `coder_eval` merges an agent's
`environment_info` into the result once, at agent start — before any turn has
run — so both sets would be permanently empty there no matter what the frames
carried. The agent therefore replays the same facts, under the same names,
through `get_sdk_options`, which the harness reads at finalize time after the
last turn; the fields appear in each replicate's `task.json` under
`sdk_options`. The adapter README carries the same note.

**An aborted turn books all-zero usage.** Omp reports the all-zero payload on
the `agent_end` of every early-stopped and max-turn-exhausted turn — the
positive rows' replicates are early-stopped by design, so their per-turn
`token_usage` is honestly None (all-zero collapses to None by `coder_eval`'s
own rule) while `omp_usage_keys_seen` still records which spellings the frame
carried. This is why `require_token_telemetry` stays off: a zero count on an
aborted turn is Omp's own accounting, and failing those turns would fail
exactly the replicates the early-stop exists to make cheap.

## The invalid-instrument run, and the fix

The first launch of this run measured nothing, and said so loudly enough to
stop before spending the rest. In `with-plugin/deps-01-slash-deps/00` under
`evals/runs/2026-09-16_19-29-28/` (kept as evidence, labelled
invalid-instrument, not deleted): the skill provably fired — the treated
reply contains the `deps` skill body verbatim, and the early-stop watcher
latched a pass on the in-flight `Skill` call — yet the final
`skill_triggered` scored 0.0 with `commands: []`. The cause: the abort
settle fed the stream's remaining frames to the reducer while emitting
nothing, so a tool call that finished during the abort never reached the
frozen trajectory the final check scores — the watcher saw the engagement,
the frozen record did not, and every positive row read 0 with the plugin
provably loaded (`omp_skills_loaded` listing all fifteen skills, no
extension errors, the model pinned). The same signature appeared
independently in the GPT arm's run of 2026-09-16 (`PR #271`, run
`2026-09-16_18-01-07`), which is what distinguished an arm defect from a
provider quirk.

The fix ships on this branch: the abort settle emits through the same
dispatch as the live loop, and `scripts/check-omp-agent-settle.py` drives the
real `communicate` against a fake `omp --mode rpc` asserting the invariant —
a replicate that early-stops on `skill_triggered` cannot final-score 0 on
that same criterion. The test reproduces the live failure exactly on the
pre-fix agent (the frozen record holds no command) and passes on the fix;
one live diagnostic replicate through the full harness scored the treated
arm 1.000 where the pre-fix arm scored 0.0.

## The accounting

- **The paid run**: `runs/2026-09-16_20-03-53`, 40 replicates, one model,
  both arms. Costs one narrow slice; `cost_complete` false (no pricing rate
  registered for the gateway route — the report's own totals understate the
  bill by the judge calls it never priced).
- **One re-run in-flight replicate.** The shell layer killed the run 300
  seconds in — the async job's deadline, not the harness — at replicate 9
  (`bare/deps-03-neg-one-named-dependency/01`, in flight, unfinalized). The
  run resumed in the same directory with `--resume`; finalized replicates
  were not re-paid, and the one in-flight replicate re-ran. Eight finalized
  replicates from the killed launch are part of this run's numbers.
- **Invalid-instrument, evidence rather than the run**: the 2026-09-14
  partial (`~2` replicates, `2026-09-14_21-39-42/`) was lost with the old
  worktree; the 2026-09-16_19-29-28 directory holds 4 launched replicates,
  3 of them finalized (`with-plugin/constitution-reaches-subagent/00` was in
  flight when the stop landed) — all pre-fix, the silent-zero evidence
  above; the 2026-09-16_19-53-50 pair (2, pre-fix) is the same defect
  confirmed on a second task; the 2026-09-16_19-55-11 pair (2) is the
  post-fix live verification. None of these are the run, and none of their
  numbers appear in the tables above.
- **Frame probes** (~5 short `omp` sessions on the pinned model) captured the
  raw frames the reduction was rebuilt against.
- Token accounting: natural-completion turns carry real counts; every
  early-stopped replicate books zeros (see the caveat above), so run-level
  token totals understate spend by exactly the replicates that early-stopped.
