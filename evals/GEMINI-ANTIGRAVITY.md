# Gemini through Google Antigravity in Omp

## Decision

Do not assign Flash coding work in this tested Omp setup. It inspected the
repositories but made no source-file changes before its turn budgets ended.
Pro showed implementation ability on one case, but that result does not
qualify as a clean measured pass. Neither model earns a default main-agent
or reasoning-role recommendation from this study.

The study stopped at partial coverage to preserve the shared Gemini allowance.
After the first Flash batch consumed a large fraction of the observed window,
the user requested `JOBS=1` and preferred one or two evaluations over exhaustion.
No explicit provider quota-exhaustion response was observed. This is a
quota-budget stop, not a claim that the account exhausted its quota.

## Scope and identity

Runs took place on 2026-10-08 and 2026-10-09 with Omp `18.8.4` and the
repository-pinned `coder-eval==0.11.6`. Every record names base commit
`73b2e7b7019a0fbf29bea2d40c53025480ac1370` and reports a dirty task checkout.
The executable coding graders, source fixtures, workflow definitions,
rubrics, and answer-key detector were not changed. The task-local adapter
was repaired between the initial startup failure and the corrected runs.

Requested subject identities were:

- Flash: `google-antigravity/gemini-3.8-flash:high`.
- Pro: `google-antigravity/gemini-3.1-pro:high`.
- Fresh control: `openai-codex/gpt-6.1-sol:high`.

Subject chat, helper, and subagent roles were pinned to the subject in an
isolated Omp home. Subject execution identity is `unreported` in the records;
model availability and requested routing are not proof of a served identity.
No provider substitution or default-role promotion was configured.

Coding cases used executable grading only. Workflow judging used the validated
`omp-gpt-6.1-sol` judge through `openai-codex`, with medium thinking and its
existing 300-second timeout. All three workflow judge records report observed
`gpt-6.1-sol` execution. The common rubric freeze is
`74b8f4aac67f14e02d46a6996e6f28e3895ac3b261c72c82b648cd9cf4c5828c`.

The initial and corrected Flash coding smoke and the fresh Sol coding control
each selected `career-462` and `career-475`, two repeats, and concurrency four.
Pro selected only `career-475`, one repeat, and concurrency one after the quota
instruction. Coding limits were 30 turns, 660 seconds per turn, and 780 seconds
per task. Pro's partial smoke is not a matched two-repeat comparison.

Each workflow probe selected only
`constitution-active-harness-is-not-model-omp`, one repeat, concurrency one,
and the `with-plugin` variant. Limits were 30 turns, 600 seconds per turn,
and 1,200 seconds per task. These are matched single-case probes, not the
requested ten-case workflow comparison. No smoke was pooled with a full run.

## Recorded outcomes

Every row links to its committed provenance. Completed means a terminal result
with grading, including a behavioral failure; startup errors are not completed
inferences. Qualified passes exclude answer-key-contact disqualifications and
use the selected semantic judge where applicable. Subject wall time excludes
subsequent semantic judging. Tokens are recorded subject usage, including
repeated context, not unique source text. Judge tokens are input plus output.

| Run | Attempted | Completed | Qualified passes | Errors | Subject tokens | Judge tokens | Subject wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| [Flash startup failure][flash-startup] | 4 | 0 | 0 | 4 | unreported | — | 59.3 |
| [Flash corrected coding smoke][flash-coding] | 4 | 4 | 0 | 0 | 2,459,798 | — | 457.2 |
| [Pro partial coding smoke][pro-coding] | 1 | 1 | 0 | 0 | 766,204 | — | 214.7 |
| [Sol fresh coding control][sol-coding] | 4 | 4 | 2 | 0 | 1,290,582 | — | 247.6 |
| [Flash workflow probe][flash-workflow] | 1 | 1 | 0 | 0 | 24,918 | 1,077 | 17.9 |
| [Pro workflow probe][pro-workflow] | 1 | 1 | 0 | 0 | 7,064 | 889 | 11.1 |
| [Sol fresh workflow control][sol-workflow] | 1 | 1 | 0 | 0 | 14,219 | 963 | 37.7 |

Dollar cost is unavailable, not zero. The records preserve null case costs and
`unreported` cost sources. Antigravity subscription allowance has no applicable
per-token price in this study. Judge usage is separate from case usage and
`price_included_in_cases` is false. Do not substitute Gemini API list prices.
See the [Antigravity plan documentation](https://antigravity.google/docs/plans).

### Coding failures and useful behavior

- **Initial Flash startup:** the old adapter passed `:high` inside the RPC
  `modelId`. Omp rejected that identifier before an inference iteration.
  These errors remain a distinct run. The adapter now sends `set_model` and
  `set_thinking_level` separately. The recorder also accepts null startup
  `agent_config` so error rows are not lost.
- **Corrected Flash smoke:** all replicates reached the turn budget without
  source-file edits. `Read`, `Grep`, and `Bash` activity shows real repository
  exploration, but not implementation. Recorded `Write` calls targeted process
  termination, not source files. `career-475` retained the failing merged
  worktree-without-upstream behavior. `career-462` retained a missing
  `projection` rename; a second failure also reached the unrelated live-label
  check. No answer-key contact was recorded.
- **Pro partial smoke:** real reads, source edits, commands, and executable
  grading were observed on `career-475`. The agent recovered from invalid
  edit anchors. The executable criteria passed and the raw weighted score is
  1.0. The unchanged answer-key detector flagged `git pull` and `git fetch`
  inside quoted here-document patch data, not executed Git commands.
  [Issue #590](https://github.com/jmcvetta/daily-driver/issues/590) records
  that false positive. The official measured score remains 0.0. The recorder
  now propagates that disqualification into the case outcome, rather than
  advertising a class-qualified success in the generated route table.
- **Sol fresh control:** both `career-475` repeats passed without answer-key
  contact. Both `career-462` transcripts show the requested rename, but their
  executable grader failed at `test_declared_labels_match_github` because
  the fixture removes the Git remote and `gh label list` then fails.
  [Issue #591](https://github.com/jmcvetta/daily-driver/issues/591) records
  the fixture defect. Those failures remain in the measured result; they are
  not evidence that Sol failed to perform the rename.

The generated route table applies its existing threshold to the cases present
in a run. A class label there does not establish full six-case coverage or
justify changing default roles. The positive Pro observation is one narrow
implementation result with a detector disqualification, not a clean class
qualification. The six-case suite also does not measure difficult reasoning.

### Workflow verdict review

Each [workflow record][flash-workflow] contains a selected-judge score of
0.5, below the existing 0.7 threshold. [Pro][pro-workflow] and
[Sol][sol-workflow] received the same score. None passed the official rubric.
The runner's pre-judge `SUCCESS` reflects disabled semantic criteria in the
rewritten task; it is not the final verdict.

All three replies correctly identified Omp as the active harness and separated
model/provider identity from harness identity. Flash and Sol named the Omp
references with `skill://` URIs. Pro named `references/omp.md` for each skill.
The judge required the literal `skills/provenance/references/omp.md` and
`skills/pr/references/omp.md` paths. It also penalized Flash and Pro for not
naming the full model identifier. The replies and judge rationales were
reviewed. These results mainly expose a strict path-spelling requirement;
they do not show confusion between Omp and Codex. The rubric and scores were
not changed. No conclusion about the other workflow skills follows.

## Shared Gemini quota observations

Snapshot times below are UTC `generatedAt` values. Links contain the observed
weekly-window data. Deltas are percentage points since the preceding snapshot,
not a model's measured per-request cost. The baseline was cached: its actual
`fetchedAt` was 2026-10-08T11:44:49.153Z. Later snapshots explicitly invalidated
the provider cache before fetching. All report the same weekly reset,
2026-10-10T10:03:00Z.

| Snapshot | Generated UTC | Remaining percent | Drop since prior snapshot |
| --- | --- | ---: | ---: |
| [Before corrected Flash smoke][quota-before] | 2026-10-08 11:47:42.129 | 99.96456 | — |
| [After Flash smoke / before Pro smoke][quota-flash-after] | 2026-10-08 11:58:09.735 | 61.04632 | 38.91824 |
| [After Pro coding smoke][quota-pro-after] | 2026-10-08 12:02:26.347 | 38.19240 | 22.85392 |
| [Before Flash workflow][quota-workflow-before] | 2026-10-08 12:07:20.139 | 37.86560 | 0.32680 |
| [After Flash workflow][quota-flash-workflow-after] | 2026-10-08 12:10:01.300 | 37.60824 | 0.25736 |
| [After Pro workflow / before Sol workflow][quota-pro-workflow-after] | 2026-10-09 12:52:35.462 | 36.85496 | 0.75328 |
| [After Sol workflow / final][quota-final] | 2026-10-09 12:54:17.421 | 36.85496 | 0.00000 |

The Pro workflow observation follows a day-long gap. Its delta cannot be
attributed entirely to that one probe. These are shared-account observations;
settlement delay or other account use can affect them. Do not infer a remaining
request count, per-token dollar price, or reliable per-eval quota forecast.
The large drops around coding justified serial execution and stopping before
the full sweep. There was no authentication, transport, or quota error during
the completed inference runs, and no semantic judge error.

## Exact deferred work

The user's quota-preservation instruction limited this study. The remaining
comparison is not presented as completed:

- Pro's original two-case, two-repeat smoke still lacks both `career-462`
  repeats and the second `career-475` repeat. These must be a separately
  identified run, not retakes that erase the partial record.
- The full coding comparison was not started: `career-141`, `career-370`,
  `career-444`, `career-462`, `career-469`, and `career-475`, three repeats for
  each subject and the control: 54 full-comparison replicates.
- The full workflow comparison was not started: the ten fixed tasks listed
  in the [runbook](README.md#gemini-through-google-antigravity), three repeats
  for each subject and the control: 90 full-comparison replicates. The
  single-case probes remain separate and do not replace those repeats.

A later run must capture fresh quota first, retain `JOBS=1` for Gemini under
this instruction, and stop on an explicit quota response without changing
providers or retrying finalized failures. The runbook provides single-case
and full-comparison commands. Full-sweep commands are configuration, not
permission to spend the remaining allowance.

## Reproduction and verification

The six experiments and three workflow Make targets use existing repository
patterns. `REPEATS` supports bounded runs. Selected plans and the Sol judge
preflight completed before execution. Raw transcripts, errors, fixture
sandboxes, and judge sidecars remain under the ignored `evals/runs/<run_id>/`
directories. Committed provenance retains the terminal statuses and criteria.

Offline regression coverage exercises recognized thinking suffixes, unchanged
plain and unknown-colon model IDs, the actual RPC model/thinking command
sequence, startup errors without agent configuration, and answer-key
case-outcome disqualification. The last regression failed before the recorder
fix and passed afterward. Actual subject runs exercised the repaired adapter;
re-recording the existing Pro run exercised the repaired recorder without a
new inference. Project-wide gates run in CI, not as a duplicate local suite.

[flash-startup]: provenance/classes-gemini-3-8-flash-2026-10-08-2026-10-08_18-33-41.json
[flash-coding]: provenance/classes-gemini-3-8-flash-2026-10-08-2026-10-08_18-49-13.json
[pro-coding]: provenance/classes-gemini-3-1-pro-2026-10-08-2026-10-08_18-58-28.json
[sol-coding]: provenance/classes-gpt-6-1-sol-2026-10-08-2026-10-08_19-02-43.json
[flash-workflow]: provenance/omp-gemini-3-8-flash-2026-10-08-2026-10-08_19-08-44.json
[pro-workflow]: provenance/omp-gemini-3-1-pro-2026-10-09-2026-10-09_19-51-34.json
[sol-workflow]: provenance/omp-gpt-6-1-sol-workflow-2026-10-09-2026-10-09_19-52-54.json
[quota-before]: quota/2026-10-08-flash-smoke-before.json
[quota-flash-after]: quota/2026-10-08-flash-smoke-after-pro-smoke-before.json
[quota-pro-after]: quota/2026-10-08-pro-coding-smoke-after.json
[quota-workflow-before]: quota/2026-10-08-flash-workflow-before.json
[quota-flash-workflow-after]: quota/2026-10-08-flash-workflow-after-pro-workflow-before.json
[quota-pro-workflow-after]: quota/2026-10-09-pro-workflow-after-sol-workflow-before.json
[quota-final]: quota/2026-10-09-sol-workflow-after-final.json
