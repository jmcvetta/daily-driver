# Evals

Eighteen suites, run by [`coder_eval`](https://github.com/UiPath/coder_eval) rather
than by `claude plugin eval`. The reasoning for the harness is
[`docs/notes/0002-eval-harness.md`](../docs/notes/0002-eval-harness.md);
the short version is that the built-in cannot be run on this account, is
publicly undocumented, announces no changes, and — decisively — ships inside
the `claude` binary, so there is no version to hold back.

```
evals/
├── experiments/
│   ├── with-without.yaml           the ablation every Claude case is measured under
│   ├── base-vs-candidate.yaml      the plugin at `master` against this checkout, constitution in both arms
│   ├── omp-*.yaml                  Omp model experiments; paired ablations or focused acceptance runs
│   ├── codex.yaml                  the same suites, on Codex — see "The Codex arm"
│   └── classes-*.yaml              model-classes experiments with their own model pins
├── tasks/
│   ├── fix-daily-driver-bugs/  offline GitHub-fixture triage and dispatch cases
│   ├── pr/              does `pr` fire when a PR is opened, and only then?
│   ├── pr-title/        … when a title is written, and only then?
│   ├── conventional-commits-type/
│   │                    … when a type is chosen, and never for a commit message?
│   ├── pr-body/         … when a body is written, and only then?
│   ├── review-cycle/    … when a review is to be run and answered, and only then?
│   ├── undertake/       … when work is undertaken, and only when handed over?
│   ├── epic/            … when work is broken up, and never when it fits one PR?
│   ├── embark/          … when an epic's wave is put to sea, and never one issue?
│   ├── deps/            … when the deps are upgraded in bulk, and not for one?
│   ├── issue-deps/      … when an issue relationship is read or written?
│   ├── issue-labels/    … when an issue is labelled, and not when it is linked?
│   ├── judgement-call/  … when a choice is about to be put to the user?
│   ├── session-title/   … when the session is named, and not the PR?
│   ├── task-worktree/   … before repository-changing work, and not for read-only work?
│   ├── constitution/    does the constitution reach a subagent, and land?
│   ├── review-depth/    does `review` send the right panel at the diff?
│   └── model-classes/   does this model finish real delegated work? see below
├── fixtures/
│   ├── fix-daily-driver-bugs/shared/
│   │                    offline `gh` recorder and issue-state assertions
│   ├── review-depth/
│   │   ├── shared/       builds the git repository every case starts from
│   │   └── cases/<name>/ one `case.sh`, mounted alone beside `shared/`
│   └── model-classes/
│       ├── shared/       clones the source repo's base SHA; the grader and its two checks
│       ├── cases/<repo>-<pr>/  the answer key, one per selected PR: a `reference:`, never mounted
│       └── candidates.json     every qualifying PR the builder saw, selected or not
├── judges/              selectable judges of the semantic criteria, and their calibration
├── coder-eval-omp/      the `omp` agent kind, so the same cases run on Omp
└── coder-eval-codex/    `coder_eval`'s Codex agent, with the judge's anchor put back
```

## Provenance

Every measured figure must cite a committed record under
[`provenance/`](provenance/). A figure without that citation is an
**unrecorded** anecdote: its run artifacts are no longer available for audit.

Every record also carries a `cases` list, one row per task per repeat.
`scripts/evals-render-routes.py` reads every committed record's `cases` and
writes the `Measured routes` table in
[`omp.md`](../skills/issue-body/references/omp.md) -- the harness-specific
reference, since every route it names is a concrete Omp model or overlay --
from them; a model and settings pair with no case row is listed `unmeasured`.

[`RESULTS.md`](RESULTS.md) lists every committed record on one page: pass
rate, price and wall time per run. `make evals-render-results` writes it, and
`make check` fails when it is stale.

[`GEMINI-ANTIGRAVITY.md`](GEMINI-ANTIGRAVITY.md) records the bounded Gemini
study, its quota stop, reviewed failures, and exact deferred comparison.

From schema version 3, every case row carries positive `elapsed_seconds` and
its cost evidence. `cost` is numeric where the harness reports a price
(`cost_source: reported`) or reports token counts the recorder can price from
[`prices.yaml`](prices.yaml) (`cost_source: computed`). When usage is missing,
or a source documents subscription billing without an applicable per-token
price, `cost` is null and `cost_source` is `unreported`; it is never treated
as free. The results page shows that cost as `not recorded`. Reported tokens
without a rate or explicit unpriced subscription entry still fail recording.
Records at versions 1 and 2 stay as they are.

## Running them

### Choose the execution session first

Choose the subject model, judge model, and execution session separately. A
Claude subject does not require a Claude judge, and a Claude judge is not
required for every evaluation. **Only a Claude judge requires a Claude Code
execution session**, web or CLI: its SDK agent inherits that session's
subscription. This applies when the subject arm is Omp as well. A non-Claude
judge runs through its own configured route; see [Choosing the judge](#choosing-the-judge).
Do not turn a failure in a non-Claude route into a request to repair Claude
authentication, or a Claude judge failure into a request to use a metered
Anthropic route.

Select the execution session required by the chosen judge before setup or
probes. A non-Claude judge does not require a Claude Code session. A supported
Claude SDK failure must be diagnosed from current evidence in the Claude Code
execution session. A previous error, an agent's claim, or a local CLI failure
in Omp does not establish that the subscription route is unavailable. Request
human action only when current evidence shows an indispensable human
contribution.
[`docs/notes/0014`](../docs/notes/0014-the-judge-runs-on-the-subscription.md)
is the current decision; this README is the single operational runbook.

### Credentials: read this before any paid run

**Claude runs on the subscription, and only on the subscription.** A Claude
agent under test and every Claude-judged `agent_judge` inherit the Claude auth
of the shell that runs `make`, so a Claude-judged evaluation runs only from a
Claude Code web or CLI session. A non-Claude judge does not need one: see
[Choosing the judge](#choosing-the-judge). Set nothing. Once the evaluation is
running from a Claude Code session, use the target unchanged; do not ask the
user to reauthenticate based on an error observed in another execution
context.

**Never route an Anthropic model through the Vercel AI Gateway.** The
container can hold a `VERCEL_AI_GATEWAY_API_KEY`, and the gateway lists
`anthropic/*` models, but it is not the route for them. Do not point
`ANTHROPIC_BASE_URL` or `ANTHROPIC_AUTH_TOKEN` at the gateway, and do not strip
the session's environment to make the CLI use it. Non-GPT, non-Anthropic Omp
models may use `vercel-ai-gateway/...` when configured. Every GPT subject,
judge, and helper call must use `openai-codex`; no GPT model may use the Vercel
AI Gateway.

**Never run an Anthropic model through the API.** Not the Anthropic API, not
Bedrock, not any other metered endpoint, not even for one test call. There is
no metered Anthropic key, and none is acquired. So no `ANTHROPIC_API_KEY`, no
`AWS_BEARER_TOKEN_BEDROCK`, and no new `llm_judge` criterion: `llm_judge`
calls the API directly and cannot run here. Write judges as `agent_judge`, with
`allowed_tools: []`, `permission_mode: default` and the `disallowed_tools`
list that `scripts/check-agent-judges.py` enforces. `allowed_tools: []` alone
hides nothing: a judge without the list reads the sandbox, times out, and
scores 0.0 with no verdict.
[`docs/notes/0014`](../docs/notes/0014-the-judge-runs-on-the-subscription.md)
is the decision. `make check` refuses an `llm_judge` row, and `make
evals-preflight` stops a run that carries one anyway. Port the row; do not look
for a key.

```sh
make evals-install    # coder-eval, pinned; uv fetches Python 3.13 itself
make evals-plan       # validate every case. Costs ZERO tokens. Do this first.
make evals-run        # the whole suite on Claude Code, both variants. Real money.
make evals-record RUN=evals/runs/<run_id> EXPERIMENT=evals/experiments/with-without.yaml
make evals-render-routes  # rewrite the Measured routes table from committed provenance
make evals-render-results # rewrite RESULTS.md from committed provenance

make evals-run TASKS='tasks/pr/*.yaml'     # one suite
make evals-run TASKS='tasks/*/*-neg-*.yaml' # just the no-fire half

# Do not run `make evals-run-omp` until #494 migrates the GPT 6 routes.
# Paired ablations compare bare and treated arms; focused runs name one arm.
# make evals-run-omp
make evals-run-codex  # the same suites on Codex. Needs the Codex SDK and a key.
```

Make eval commands use `uv tool run --isolated`, the pinned harness, and
editable adapters from this checkout. A shared `coder-eval` installation can
retain an older adapter, including one from another worktree. Direct CLI
commands must select the same isolated adapters instead of trusting that
installation. For example, this selected plan makes no inference calls:

```sh
(
  cd evals
  TELEMETRY_ENABLED=false uv tool run --isolated --python 3.13 \
    --from coder-eval==0.11.6 \
    --with-editable ./coder-eval-omp --with-editable ./coder-eval-codex \
    coder-eval plan -e experiments/classes-gemini-3.1-pro.yaml \
      tasks/model-classes/career-370.yaml
)
```

The repository-local automatic-report workflow has three Omp-only behavioral
fixtures. They use a fake `gh` that records issue reads and writes; no live
GitHub issue is read or changed. Case 03 states in its prompt that the
`reasoning` agent has no route; the sandbox does not remove that route from the
Omp configuration. No criterion checks which agent each batch item selects:
the judge sees only reply text, and `command_executed` sees a truncated
serialisation (see the `subagent_type` note below). Run them with an available
Omp model and judge:

```sh
make evals-run-omp-glm-5-3 JUDGE=omp-glm-5.3 \
  TASKS='tasks/fix-daily-driver-bugs/*.yaml'
```

`make evals-record ... POST_COMMENTS=1` also posts one comment per run on each
pull request a case was built from (model-classes cases, whose description
begins `owner/repo#N:`). The comment says an agent re-implemented that task in
an eval after the fact, and lists one row per model and variant: `pass n/m`
and the median elapsed minutes. Tokens, cost and transcripts stay in the
record. A comment is edited, not repeated, when its `eval-result` run marker
is already on the pull request. The token comes from `GITHUB_TOKEN` or
`GH_TOKEN`; without one the record is written, the comments are skipped, and
the command exits non-zero. A failure on one pull request is reported on stderr, the
rest still post, and the exit is non-zero. Posting is local only; CI never sets the flag.

The `*-neg-*` selector is a filename glob, and one absence assertion does not
live in a file it matches: `tasks/pr/02-open-a-pr.yaml` is a fire case that
also asserts `undertake` stays silent. Add `tasks/pr/*.yaml` when the question
being asked is about collisions rather than about the no-fire cases as such.

Not part of `make check`. The cases need a live model and this repository's CI
is deliberately credential-free. What *is* part of `make check` is
`check-eval-fixtures`, which builds every review-depth fixture repository with
nothing but git — see "The git problem" below for why that leg exists.

**`llm_judge` is not an alternate credential route.** It calls Anthropic's
metered API, which this project does not use. `make evals-run` rejects every
enabled `llm_judge` criterion, even if a key or alternate transport is
configured. Use `agent_judge` for subscription-backed Claude judging, and run
from a Claude Code session as described above. See
[`docs/notes/0014`](../docs/notes/0014-the-judge-runs-on-the-subscription.md)
for the decision and [`0012`](../docs/notes/0012-the-judge-needs-its-own-transport.md)
for the historical guard this preflight now enforces more strictly.
"Two defaults, decided on purpose" below covers how a `.env` file overrides
your shell environment.

**Run `plan` before every `run`.** It is free, and it catches the config errors
that otherwise cost a paid run to discover. `make evals-run` depends on
`evals-plan` for exactly that reason.

Three things the Makefile does that a hand-typed `coder-eval` will not:

- **`cd evals` first.** The plugin path in the experiment is relative and
  resolves against the *process* working directory. Point it at the wrong
  place and the SDK loads nothing, with no error, and every positive row scores
  0 — which reads exactly like a skill that never fires.
- **`-e experiments/with-without.yaml`, always.** A wheel install of
  `coder-eval` resolves its `--experiment` default to the copy packaged inside
  the wheel and never looks in the working directory. Omit `-e` and the tasks
  run as a single unlabelled arm on `coder-eval`'s own stale defaults, and the
  ablation silently is not measured.
- **`TELEMETRY_ENABLED=false`.** See "Two defaults, decided on purpose".

### Choosing the judge

The subject and judge are selected apart. `JUDGE=` selects a configured judge
from [`judges/`](judges/) without copying a task or touching a rubric. The
decision is
[`docs/notes/0030`](../docs/notes/0030-the-judge-is-selected-apart-from-the-subject.md).
Claude is not required for every judge: only the Claude judge rows below
require a Claude Code execution session. The Omp judge runs through its own
configured route.

| `JUDGE=` | Route | Where it can run |
| --- | --- | --- |
| unset | each task's pinned Claude Code `agent_judge`, run by `coder_eval` | a Claude Code web or CLI session |
| `claude-code-sonnet-5` | the same route, named; refuses a task that pins another judge | a Claude Code web or CLI session |
| `omp-glm-5.3` | no-tools Omp over the Vercel AI Gateway; validated, not the default | anywhere `omp` and the gateway key work |
| `omp-gpt-6.1-sol` | no-tools Omp through `openai-codex`; validated, not the default | anywhere Omp has the OpenAI Codex provider configured |

GPT 6.1 Sol (`openai-codex/gpt-6.1-sol`) is the calibrated semantic judge
defined in `judges/omp-gpt-6.1-sol.yaml`. It passed the predeclared calibration
rule on 2026-10-06: 11 of 11 labels correct, no false passes, no errors. The
small transcript set supports this route for the rubric tested; it is not a
general model-quality ranking
([`observed/omp-gpt-6.1-sol.json`](judges/calibration/observed/omp-gpt-6.1-sol.json)).

```sh
make evals-judge-calibrate JUDGE=omp-glm-5.3                              # measure a judge first; a few cents
make evals-run-omp-gpt-5-6-sol JUDGE=omp-glm-5.3 TASKS='tasks/undertake/09-title-before-claim-omp.yaml'
```

`omp-gpt-6.1-sol` met the predeclared calibration rule on 2026-10-06: 11 of 11
labels correct, no false passes, no errors. The small transcript set supports
this route for the rubric tested; it is not a general model-quality ranking
([`observed/omp-gpt-6.1-sol.json`](judges/calibration/observed/omp-gpt-6.1-sol.json)).

```sh
make evals-run-omp-gpt-6-1-sol JUDGE=omp-gpt-6.1-sol TASKS='tasks/undertake/17-*.yaml tasks/pr-body/08-capability-gap-is-not-human-blocker.yaml'
```

Both the subject and judge use `openai-codex` for this configuration. Do not
route OpenAI models through the Vercel AI Gateway. The experiment uses one
repeat per variant for the focused run; expand only after reviewing those results.

### Gemini through Google Antigravity

Run the exact Omp routes `google-antigravity/gemini-3.8-flash:high` and
`google-antigravity/gemini-3.1-pro:high`; never substitute Vercel. The Omp
adapter pins every chat role, including task, helper, and subagent roles, to
the experiment's subject model. `model_served` stays `unreported` when Omp does
not report it.

Before inference, read availability and quota:

```sh
omp models google-antigravity
omp usage --provider google-antigravity --json --redact --no-extensions
```

A listed model is not proof that inference works. Record the redacted quota
snapshot and timestamp before each model batch, and again after it. Refresh
the cache with `omp usage invalidate --provider google-antigravity` first.
Do not change the user's Omp defaults, buy credits, enable overages, or retry
authentication, transport, or quota failures through another provider. Keep
quota exhaustion distinct from model errors and preserve partial runs.
Antigravity has no applicable per-token price in the plan documentation, so
`prices.yaml` records token usage and an unavailable dollar cost.

The initial smoke uses two repeats on two coding cases, four replicates at
concurrency 4, with one subject model at a time. If quota drops sharply,
switch Gemini to `JOBS=1` and run one task and repeat at a time, checking
quota before dispatching another. A completed eval is more useful than
concurrent partial runs. Keep every run separate; concurrency does not reduce
the total token use of the same work.

```sh
make evals-run-classes MODEL=gemini-3.1-pro JOBS=1 REPEATS=1 \
  TASKS='tasks/model-classes/career-370.yaml'
omp usage invalidate --provider google-antigravity
omp usage --provider google-antigravity --json --redact --no-extensions
make evals-run-classes MODEL=gpt-6.1-sol JOBS=1 REPEATS=1 \
  TASKS='tasks/model-classes/career-370.yaml'
```

Review the transcripts for actual read/edit/command use and executable grader
results before expanding. When quota permits, run each full class model
separately at three repeats; use serial Gemini execution after high consumption:

```sh
make evals-run-classes MODEL=gemini-3.8-flash JOBS=1
make evals-run-classes MODEL=gemini-3.1-pro JOBS=1
make evals-run-classes MODEL=gpt-6.1-sol JOBS=4
```

The full workflow comparison uses the same ten Daily Driver tasks and three
repeats with `JUDGE=omp-gpt-6.1-sol` for Gemini and Sol. Use `JOBS=1` for
Gemini after high quota consumption. Run one case and repeat at a time when
quota is tight, and record incomplete coverage. Executable criteria remain
authoritative; Sol judges only the semantic rubrics. Run the commands separately:

```sh
WORKFLOW_TASKS='tasks/task-worktree/01-isolate-new-task-omp.yaml tasks/task-worktree/02-neg-read-only-review.yaml tasks/task-worktree/03-neg-existing-task-worktree.yaml tasks/session-title/07-one-call-sets-the-title-omp.yaml tasks/session-title/05-neg-pr-title.yaml tasks/judgement-call/01-ask-in-chat-extension-omp.yaml tasks/constitution/active-harness-is-not-model-omp.yaml tasks/undertake/17-access-gap-without-handoff.yaml tasks/undertake/17-actual-human-auth-contribution.yaml tasks/undertake/17-authorized-agent-handoff.yaml'
make evals-run-omp-gemini-3-8-flash JOBS=1 JUDGE=omp-gpt-6.1-sol TASKS="$WORKFLOW_TASKS"
make evals-run-omp-gemini-3-1-pro JOBS=1 JUDGE=omp-gpt-6.1-sol TASKS="$WORKFLOW_TASKS"
make evals-run-omp-gpt-6-1-sol-workflow JOBS=4 JUDGE=omp-gpt-6.1-sol TASKS="$WORKFLOW_TASKS"
```

For a single workflow eval with a quota check before the next dispatch:

```sh
make evals-run-omp-gemini-3-1-pro JOBS=1 REPEATS=1 JUDGE=omp-gpt-6.1-sol \
  TASKS='tasks/constitution/active-harness-is-not-model-omp.yaml'
omp usage invalidate --provider google-antigravity
omp usage --provider google-antigravity --json --redact --no-extensions
```

For the trigger-only read-only probe, use its bounded limits explicitly. It
has no semantic criteria, so no judge call is needed. Run each experiment
separately and refresh quota between Gemini runs:

```sh
(
  cd evals
  TELEMETRY_ENABLED=false uv tool run --isolated --python 3.13 \
    --from coder-eval==0.11.6 \
    --with-editable ./coder-eval-omp --with-editable ./coder-eval-codex \
    coder-eval run --max-parallel 1 --repeats 1 \
    -D run_limits.max_turns=5 -D run_limits.turn_timeout=120 \
    -D run_limits.task_timeout=300 -e experiments/omp-gemini-3.1-pro.yaml \
    --exclude-tags claude-only,codex-only,skip:omp,model-classes \
    tasks/task-worktree/02-neg-read-only-review.yaml
)
```

The matching experiments are `omp-gemini-3.8-flash.yaml` and
`omp-gpt-6.1-sol-workflow.yaml`. Record each exact run directory with its
experiment through `scripts/evals-record.py`; never overwrite a finalized run.

Keep smoke, full class, and workflow runs distinct. Record attempted,
completed, pass, and error counts; per-case failures; elapsed time; reported
tokens; and unavailable dollar cost. Never pool different tasks or judges,
remove failure rows, or infer a general main-agent or reasoning-class
recommendation from these small samples. Link every reported figure to its
committed provenance record.

**What a non-Claude judge changes.** `make evals-judge-preflight` runs first and
fails before any subject if `omp` is missing, Omp does not list the judge's exact
model, or the definition is invalid: no subject is started and nothing falls back
to another judge, the subject's model included. It writes `tasks-judged/`, the
same tasks with each `agent_judge` set `enabled: false`; the run uses that tree,
so deterministic criteria (`command_executed`, `file_matches_regex`, ...) run
exactly as before and stay the authority on commands, fixtures and forbidden
operations. `make evals-record` then runs `scripts/evals-judge.py judge-run`,
which grades each preserved transcript with the selected judge from the original
task's rubric, verbatim, and writes a sidecar under `<run>/judge/<judge-id>/`.

**`coder_eval`'s own scores are not the measurement for such a run.** It scores a
disabled criterion 1.0. The recorder replaces each judged replicate's
`measured_score` and `final_status` with ones recomputed from the deterministic
results and the judge's scores, and keeps `coder_eval_status` and
`raw_weighted_score` beside them.

**What the Omp judge sees.** The rubric and the transcript the criterion asked
for (`include_agent_output`, `include_tool_calls`, `include_dialog`), marked
untrusted, and nothing else: `omp --no-tools` with every discovery switch off, in
an empty directory, in a throwaway home that borrows only the provider files
`coder_eval_omp.home` lists. A criterion that attaches `files:` or the reference
cannot be judged that way and is refused, not degraded. `make check-agent-judges`
asserts the command line and the prompt, as it asserts the Claude denylist.

**Errors are not scores.** A judge that is unreachable, times out, or returns
anything but exactly one verdict object (`score` in [0, 1], `rationale`,
`findings`) is an evaluation error. The sidecar records it, the replicate's score
is null, and the case outcome is `error`; it is never a behavioural 0.0 and never
a pass. Re-run `judge-run` on the same run directory once the judge works.

**One judge, frozen, per comparison.** The sidecar and the record's `judge`
object carry a `freeze_sha` over route, model, settings, the judge prompt and
every rubric. Records with different `freeze_sha` values, or different judges,
are different measurements; do not read one against the other. The record names
the *requested* judge and the model Omp *reported*; an identity or usage the route
did not report is `unavailable`, never filled from the configured name. A
non-Claude judge's usage is under `judge.usage` and is not in the cases' price.
Historical records keep their task-pinned Claude judge, with no observed
identity.

**Adopting a judge.** A judge is `validated` only when
[`judges/calibration/`](judges/calibration/) holds a committed result that met the
acceptance rule in `labels.yaml`, declared before the candidate ran. The set is
11 hand-labelled transcripts written from the real rubric of
`undertake-09-title-before-claim-omp`: fabricated attempts, missing or misordered
command evidence, a forbidden client, an injected grade, a valid safety refusal
and genuine successes. It is measured against those labels, never against Claude.
`omp-glm-5.3` met the rule on 2026-10-05: 11 of 11, no false pass, no error
([`observed/omp-glm-5.3.json`](judges/calibration/observed/omp-glm-5.3.json)).
That is a small sample of one rubric: it licenses recommending the route, not a
ranking of models, and the default judge stays `claude-code-sonnet-5`. Change the
labels or the rule and it is a new set with a new `set_id`.

### `base-vs-candidate`: does a constitution change move a row

`with-without.yaml` compares the plugin with no plugin, so its control carries
no constitution. It cannot isolate a change to the constitution's text. The
comparison experiment loads the plugin in both arms and varies only the
revision: `base` is `master`, `candidate` is this checkout. It answers one
question the ablation cannot: does the new text change a reply once a
constitution is already delivered?

The base arm needs a second checkout that the experiment cannot create:
`git worktree add ../daily-driver-base <base-revision>`. Run it narrowed to
the rows below, five repeats, per-replicate results kept:

```sh
make evals-run-comparison TASKS="tasks/constitution/answer-selects-from-findings.yaml tasks/constitution/short-question-after-tool-heavy-work.yaml tasks/constitution/explanation-request-answered.yaml"
```

The target records the run against the comparison experiment. Record the
base revision (the sibling's `git rev-parse HEAD`) and the candidate revision
with it.

| Row | Role |
| --- | ---- |
| `constitution/answer-selects-from-findings.yaml` | finding: the "one contrast" sentence must raise the selection score |
| `constitution/short-question-after-tool-heavy-work.yaml` | finding: fails on `master` by construction; the restatement hook must raise it |
| `constitution/explanation-request-answered.yaml` | control: a requested explanation must still arrive |

Report replicates marked `ANCHOR: no-question` or `ANCHOR: tainted-question`
separately; they measured nothing. The Codex arm stays out: every constitution
row carries `skip:codex`.

## What the suites are for

The trigger-accuracy suites exist because these skills are siblings with
overlapping vocabulary — `pr`, `pr-title` and `pr-body` every one of them with
"PR" in its description, and `review-cycle` sharing the pull request with all
three — so the thing that can actually break is *which* one fires.
`conventional-commits-type` sits behind `pr-title` and is asked for without
a title in hand, so its suite adds the delegation route — a title correction
that must reach the type skill rather than decide the type in place — and
the one adjacent request where a type is tempting and wrong: a commit
message, which is prose by the constitution's rule. Each suite has two
halves, and the second is the one that earns its keep:

- **Fire cases** — four per skill, covering the literal slash command,
  natural phrasings, and Claude's own use of the call that skill's description
  names. That call is `mcp__github__create_pull_request` /
  `mcp__github__update_pull_request` on the three PR suites, and it is
  whatever the skill actually routes to elsewhere —
  `mcp__Claude_Code_Remote__set_session_title` on `session-title`, which is
  not a GitHub call at all.
- **No-fire cases** — two per skill, drawn from the *adjacent* skills rather
  than from unrelated work. "Fix just the title" asserts that `pr-title` fires
  and `pr` does not; a request to write a commit message asserts that none of
  the three does. A suite that only proved a skill fires would be green with
  all three descriptions collapsed into one.

`review-cycle/`'s siblings are `pr` — the round starts from a pull request
that already exists, so "raise a pull request" is `pr`'s and not the round's —
and a mood, which is the harder one. See "The two moods" below.

It also carries one of the two rows here that grade behaviour rather than
triggering: `07-wait-for-ci-is-not-a-sleep`, which enters the round with CI
still running and asserts that no shell `sleep` was run. `Bash` is open on
purpose — a negative control on a tool the model was never offered passes
vacuously — and both criteria are armed bare, the positive included, for the
reason the arming paragraph below gives. What the row cannot grade is the
loop `How to wait` prescribes in the sleep's place: reading the checks needs
the GitHub MCP and waking needs a surface that can wake itself, and the
sandbox is neither. It grades the failure, not the fix.

The other is `conventional-commits-type/07-user-set-type-is-not-reverted`,
built the same way and for the same kind of report. The title on a pull
request has moved since the branch was pushed, the prompt names who pushed it
and not who moved it, and the row asserts that no `gh pr edit` or `gh api`
call put the old type back. `Bash` is open for the same reason, and the diff
the prompt describes is one the type tests read as `chore(deps):` — so a bare
arm that reasons from the description reverts, and the ablation has somewhere
to show. The same half is ungradeable: that the disagreement is raised and
waited on needs a live pull request and someone to answer. It grades the
revert, not the asking.

`undertake/` asks the same question of a skill with two ways in. `Open the
issue` opens one for work that has none, so an issue reference no longer has
to be present for the skill to fire — and what fires it is now either an issue
handed over or the skill named. Three of the four cases are the three ways
that can go wrong. `01` is the slash command, which resolves the skill by name
and so tests the plumbing rather than the description. `02` names the skill in
prose on work with no issue: the description is the only thing saying an issue
is optional, so a drift back to requiring one fails here and nowhere else.
`03` is `Implement #191.` — the half of the register that predates `Open the
issue`, and the half a description rewritten around the invocation alone would
silently drop. `06` is the third way in, added with `Keep it current`: a pull
request already ready and now behind its base, which reaches the skill through
neither an issue nor an invocation.

Three no-fire rows. `04` is the same retry loop as `01` and `02` with neither an
issue nor an invocation. `05` is the mood — `What does #191 say?`, an issue
named and nothing assigned — which is the row that matters most here, because
`Open the issue` is what widened the description and a widened description is
answered by asking what it now sweeps in. `07` is `Merge PR #25.`, the
direction `Keep it current` does not go: that step merges the base branch into
the pull request, and the word it put in the description is the word this row
keeps from sweeping in the other one.

The escalation regression rows `undertake/17-*.yaml` and
`pr-body/08-capability-gap-is-not-human-blocker.yaml` grade both the decision
and its evidence. Sandbox command stubs in
`fixtures/undertake-escalation/shared/setup.sh` never access infrastructure or
GitHub; `command_executed` and the stub's `.fixture/trajectory.log` must both
show an operation before a judge credits an attempt. The rows cover a permitted
Tofu plan, an alternative route, an observed person-only authorization, a
production prohibition with no probe, pending CI, independent work before an
access gap and before a real human action, credentialed cloud execution, an
available authorized-agent handoff, a missing-handoff prerequisite, stale
versus still-outstanding Tofu apply blockers on resume, and PR-body maintenance
from undertaking evidence.
Run only this focused set with the documented
`make evals-run TASKS='tasks/undertake/17-*.yaml tasks/pr-body/08-capability-gap-is-not-human-blocker.yaml'`
route after its `evals-plan`; the normal project checks remain CI's gate.

One collision is asserted from the other side. `pr/02-open-a-pr.yaml` carries an
`undertake` distractor, because "get it to a pull request" is in `undertake`'s
register too and the only thing separating them is that the prompt has no issue
to undertake. Its `pr` criterion is armed bare rather than
pass-stopped for that reason: a pass-stop there would end the run the moment
`pr` fires and the distractor would pass vacuously, while the bare arm keeps
that criterion pass-capable so the distractor's fail-stop stays deferred. The reverse assertion is absent on purpose — `undertake` invokes
`pr` at `Open the draft`, so `pr` firing on an undertake prompt is correct.

`deps/` asks where the line falls between a bulk upgrade and one dependency.
`01` is the slash command and `02` is the register the skill was written for —
Dependabot's pull requests named, the whole set asked for. `03` and `04` are the rows
that carry the suite. `Bump requests to 2.32.3 — just that one, nothing else.`
is ordinary work through the package manager, and a description that swept it
in would answer a one-line ask by upgrading everything in the repository. `04`
is the ambient case: Dependabot's pull requests visible in the prompt and other
work asked for, which is the shape a description reaching for "noticing" would
misread as an invitation.

`task-worktree/` tests the boundary and the work, not a narrated command.
`01` names the feature branch but says nothing about isolation; the rule and
skill must supply Worktrunk creation in a sibling worktree. The shared fixture
uses real `wt` commands and accepts only a branch from the remote default, the
changed file in a registered sibling worktree, preserved primary-checkout
state, and no copied primary-only changes. `04` starts detached and requires the
feature branch in place. `02` keeps read-only review out; `03` keeps an already
attached worktree from nesting another one.

`issue-labels/` is separated from `issue-deps`, and the two are one word
apart: both are about an issue, and both are reached for with "what does this
issue need". The line is that a label says what *kind* of issue this is and a
relationship says what it *waits on*, so `05` is a blocked-by request, which
asserts `issue-deps` fires and `issue-labels` does not. `06` is the other
temptation, and it is the word rather than the subject: a label on a pull
request, written by a bot, where "label" is the whole of the pull. Nothing
fires, and `deps` is the distractor because a bot's pull requests are its
subject. The four fire rows are the slash command, the label for an issue not
yet filed, an epic-or-task choice, and the readiness question asked of a whole
backlog — the last of which is the question the standard exists to answer and
the one `undertake` asks on every issue it is handed.

`session-title/` is the pair that sits closest together: two skills about a
*title*, one noun apart, and two of `session-title`'s natural phrasings live
inside `pr-title`'s vocabulary. So the boundary is asserted in both
directions rather than one. `02` renames the session, and `pr-title/08-neg-session-title` asserts
`pr-title` stays out of that same prompt; `05` fixes a pull request title
with the session name ruled out, and asserts `session-title` stays out. The
two directions sit in different suites because a `-neg-` row belongs to the
skill it keeps silent, which is what
`make evals-run TASKS='tasks/*/*-neg-*.yaml'` selects on. A suite that only proved
`session-title` fires would stay green with both descriptions collapsed into
one.

`04` is the row that had to be designed rather than written down. It is the
initiative trigger — work on an issue beginning, and nothing in the prompt
asking for a title or a name — so the issue it quotes decides whether the row
tests anything. It quotes `session-title`'s own #212 worked example, whose
title shares no vocabulary with the skill. Quote an issue called "set the
session title" instead and the row passes on a keyword match without ever
reaching the clause it exists for.

`07-get-session-before-set` is the suite's behaviour row, and it grades the
reading rather than the triggering: `SKILL.md` sends the caller to the
reference file for the call, and the reference file is where the two-call
order lives — `get_session` with no id first, then `set_session_title` with
the id it returned.

`constitution/` is not a trigger-accuracy suite: it is the live half of the
constitution's own test, described under "Checks" in the repository README. Its credential-free half is
`scripts/check-constitution.py`.

**The compliance rows differ in how much true material the model is holding,
and that turns out to be the axis that matters.** The retired
`reply-is-concise` asked a question with one honest answer, so the model gave
it: measured at 1.000 in every arm of every run, treated and bare alike, which
means it separated nothing. **Unrecorded.**
`answer-selects-from-findings` first spends a turn filling the context with
five true findings the model wrote itself, and only then asks for one of them.
That is a selection problem rather than a compression one, and it is where the
rule is actually load-bearing. A compliance row that scores 1.000 everywhere is
proving the model's default, not the constitution — issue #279's comparison
concluded nothing for exactly that reason, and this row is what came out of it.

Its first probe run scored 0.40 bare against 0.80 treated, five replicates
each, with the correctness floor at 1.000 in all ten. **Unrecorded; the run
record is not committed.** Reviewing the run showed the simulated interlocutor
drifting off the question it was given: in one of the ten replicates it answered
itself and ended the dialog, so the graders read the audit instead of the reply,
and in three more an extra turn let it state the answer before the question
arrived. The row's `simulation` block has since been narrowed — two turns
instead of three, the model pinned, the `description` stripped of anything
describing the rule — so the run that produced 0.40/0.80 was made under a
configuration this repository no longer holds. The narrowing does not remove
the drift: at two turns a self-answer lands on the graded turn instead of a
spare one. Both graders now read the dialog and mark a replicate the drift
spoiled. The mark does not remove it from anything: a spoiled replicate still
scores 0.0 and still drags the mean until somebody drops it by hand. What it
buys is that the reader can now tell which zeros those are. What the row
establishes today is that it is not at ceiling; the number itself needs a fresh
run before any amendment is tested against it.

`review-depth/` asks whether `review` sends the *right panel* at the right
diff. Every case is anchored on something a person would notice if routing
broke — a security reviewer that never ran on the file holding the publishing
token, a rewritten README judged for correctness bugs, a full panel billed to
every pull request opened — rather than on a restated line from
`skills/review/SKILL.md`. A suite that restates the spec catches
drift away from the depth table and can never catch the depth table being
wrong.

Claude and Omp measurement arms carry the same ablation: every criterion is
scored in a `bare` session and in a treated session. The delta, not a treated
score alone, measures the plugin's effect. See "The Omp arm" for its per-model form.

## The two moods, and `expected_skill: none`

`pr`, `pr-title` and `pr-body` are separated from each other, so every one of
their no-fire rows can name the sibling that *should* have fired. Some skills
are not separated from a sibling at all. They are separated from a **mood** —
the same subject matter, arriving as a question rather than as an assignment:

- *"What did the reviewer say about the retry loop?"* is a question. The
  review comments `review-cycle` exists to answer are the very thing being
  asked about, and nothing should fire.
- *"What does #191 say?"* is the same shape for `undertake`, which fires on an
  issue handed over to be worked on or on being named for a task — and on
  neither when the issue is only being asked about.

Against a mood there is no positive counterpart to assert, so those rows use
`expected_skill: none` as their ground truth and carry the distractor alone.
That is a departure from the three PR suites, and it is deliberate: naming an
innocent sibling on a row where the correct behaviour is silence would assert
something the row does not mean.

Such a row also has nothing pass-capable beside it, so its `stop_early: {}` is
armed for the other reason — a misfire has already lost the row, and there is
no recall decision left for a fail-stop to pre-empt.

## Both arms, every criterion

Every criterion is scored under both variants: `bare` (nothing loaded) and
`with-plugin`. That is the point. A fire case's delta is the whole signal — 1
with the plugin, 0 without it, because without it there is no skill to fire —
and a number reported for the treated arm alone has nothing to compare itself
to. In the old format this took an explicit `arm: both` on every grader;
`coder_eval` does it by construction.

`repeats` is **5**, set explicitly, because `coder_eval` defaults it to 1. One
replicate of a non-deterministic agent is an anecdote. Even 3-of-3 — what the
old suites used — supports only a ~[0.37, 1.0] confidence interval on the rate.
Read `per_replicate_scores` in the report rather than the mean.

## How the graders ported

| `claude plugin eval` | here |
| --- | --- |
| `prompt.md` body | `initial_prompt` |
| `case.yaml` + `graders/*.md` | one `tasks/<suite>/<id>.yaml` |
| `runs: 3` | `defaults.repeats: 5` |
| `arm: both` | nothing — both variants are always scored |
| `tool_used` on `Skill` | `skill_triggered` |
| `tool_used` on `Agent` | `command_executed` with `tool_name: Agent` |
| `tool_used` on `Agent`, by `subagent_type` | **nothing** — see below |
| `regex` on `last_message` | **nothing** — see below |
| `max_turns`, `timeout_seconds` | `run_limits.max_turns`, `run_limits.turn_timeout` |

Two entries there disagree with the mapping in `0002` and in issue #37, and the
disagreement is load-bearing:

- **`command_executed` is the generic tool-call criterion**, not a shell-only
  one. It filters on `tool_name` for *any* tool and, off `Bash`, matches
  `command_pattern` against the JSON-serialised tool parameters; Claude Code's
  adapter records one telemetry row per `tool_use` block. So `tool_used` on
  `Agent` — including `input_match`, which becomes `command_pattern` — ported
  after all, and the `constitution` suite lost one grader to redesign rather
  than three. Its limit is length, not tool kind: the haystack is truncated to
  2000 characters, which is why it can assert *that* a subagent ran and cannot
  assert *which* — see "Grading dispatch" below.
- **`regex` on `last_message` genuinely has no equivalent.** Nothing in
  `coder_eval` matches the agent's final message deterministically —
  `file_matches_regex` needs a path and reads file content, and only
  `llm_judge` / `agent_judge` see the final message, as a scored judgment. That
  cost one grader a redesign and one intended check an omission; both are
  recorded below.

One hazard `skill_triggered` carries, which the criterion's name hides: besides
the `Skill` tool call, it scans **every string parameter of every tool** for the
substring `skills/<name>/`, so a `Read` of
`skills/review/references/review-guidelines.md` counts as engaging `review`.
That is deliberate — it is how the criterion scores agents with no `Skill` tool
— but it means a row that grants file tools and expects a skill *not* to fire is
only as sound as the paths that row can plausibly touch. `allowed_tools` is not
the mitigation: it is a permission allowlist, the model
is still offered `Read`, and telemetry records a `tool_use` block when it is
generated — before any result — so a *denied* read of `skills/pr/SKILL.md`,
which is what a model weighing two sibling skills reaches for, still scores as
engaging `pr`. The trigger rows therefore carry an explicit `disallowed_tools`,
which is the field that actually removes a tool. `review-depth`'s no-fire row
needs file tools and keeps them, and relies instead on the `pr` skill having no
reason to name a path under `skills/review/` — which it does not — with the
empty-roster criterion beside it as the check that does not depend on paths at
all.

`skill_triggered` also improved a detail. The old graders matched the skill
name out of the tool input as a regex, so `pr` had to be written `(:|")pr"` to
avoid matching `pr-title`. `skill_name` is an exact match against the set of
engaged skills, plugin namespace stripped, so that class of near-miss is gone.

Each `skill_triggered` row carries an `expected_skill`: the ground truth for
that row, repeated on every criterion of that type. (`review-depth` 01–06 have
none — they are graded entirely on the dispatch roster.) What it does today is
set the polarity — a criterion passes
when the skill's engagement matches whether `expected_skill` names it — and
`none` is a legitimate value, which is what the "neither of these should fire"
rows use.

It is *also* the input to `coder_eval`'s per-suite classification rollup
(accuracy, recall, F1, a confusion matrix), and that rollup does **not** run
here: it is computed only for tasks carrying a `suite_id`, which is set in
exactly one place — the `dataset:` expander. Getting it would mean collapsing
each suite's six files into one dataset-fanned task, trading six readable cases
for one table. Worth doing when the per-skill numbers are what someone is
actually reading; not worth doing to make a sentence in this file true.

`stop_early` is armed where it is free. On a single-criterion fire case,
`on_pass: stop` ends the run the moment the skill fires. On a no-fire case the
distractor is armed bare (`stop_early: {}`) — a misfire has already lost the
row, so there is nothing left to pay for — **and so is the positive criterion
beside it**, which is the part that is easy to get backwards.

On the trigger suites this is free. On `review-depth`'s no-fire row it is not,
and that row says so: the fail-stop is deferred while the pass-capable `pr`
criterion is undecided, so on the very trajectory the row exists to catch —
`review` fires, `pr` never does — nothing decides it, the stop never comes, and
the run pays for a full reviewer panel up to its turn cap. Recall is worth that
there; `max_turns` is what bounds the bill.

Arming the positive cannot truncate anything: a bare `stop_early: {}` leaves
`on_pass` at its default `continue`. What it does is put the criterion in the
watcher's *pass-capable* set, and a fail-stop is deferred while any pass-capable
armed criterion is still undecided. Leave the positive unarmed and the watcher
cannot see it: the first distractor misfire ends the run, the positive is then
scored on a trajectory that stopped before the right skill could fire, and the
row records a false negative a full run would never have produced.

## The constitution suite: reach, then compliance

Every row there carries `skip:codex` and is absent from the Codex arm.
`coder_eval`'s Codex agent links skills and installs no hooks, so the constitution never
reaches that session and a zero there would say nothing about the constitution.
See "The Codex arm" below.

`subagent-reports-the-token` was `regex` on `last_message`, weight 2 — the
grader that *is* the finding. It now has the subagent write its answer to a
file, and `file_matches_regex` reads it. That keeps determinism, which is what
a criterion carrying the whole result needs, and it changes what is exercised:
a subagent that knows the answer but cannot write now fails a test it used to
pass.

The case no longer grades a token planted in the constitution for it to find.
It grades a phrase the constitution says in its own prose, and every
file-reading tool is closed, so the injected copy is the only route to it.
`scripts/check-constitution.py` holds the two ends together: the phrase is
still in the file, and no text outside a criterion may name it.

Its negative control survives intact — `command_executed` on `Agent` with
`max_count: 0` and that phrase as the pattern, asserting the parent did not
hand the answer over in the prompt it sent.

One limitation is inherited rather than introduced. The parent holds the
constitution too, so it could write the answer itself instead of relaying it.
The prompt forbids it, and no criterion can catch it: subagent tool calls
bubble into the parent's telemetry tagged with `parent_tool_use_id`, and
`command_executed` cannot filter on that, so nothing here tells a parent
`Write` from a subagent `Write`. The `last_message` version had exactly the
same hole — the parent could simply type the answer. Closing it needs a marker
the parent never sees, which is a change to the hook, not to the case.

### `short-question-after-tool-heavy-work`, the row built to fail on `master`

Issue #474. The first compliance row, `reply-is-concise`, asked a small question
with one honest answer and scored 1.000 in every arm, bare included, so it
could not show a rule working. It is retired. The verbosity users get arrives
after long, tool-heavy work, when a short question gets a recap, narration, an
offer or a menu around one fact.

Turn one asks the agent to read a local tracker export (issues, pull requests,
comments, check listings) and catch up; it is not graded. Turn two is the
question `What's the status?`, and the honest answer is one fact: #457 is
blocked by #279. A sentence rather than the one word `Status`, because one word
reached the agent as harness tags and read as noise (issue #486). The
fixture holds a draft pull request with green checks, a long comment thread, a
closed issue and an epic, so every recap is true. The interlocutor is steered,
not pinned, with the limits `answer-selects-from-findings` documents, and the
rubrics carry the same `ANCHOR:` tokens.

Two `agent_judge` criteria. The floor, at weight 1, wants the one fact. The
unrequested-content criterion, at weight 2, scores recap, narration, offers,
menus and headings or bullets around a one-fact answer, and never counts
length. Each rubric carries a calibration pair, so neither compensates for the
other. The acceptance bar is a mean at or below 0.6 on the second criterion on
`master` with the plugin loaded; a probe that passes there cannot show the
restatement hook working.

### `answer-selects-from-findings`, the row that is not at ceiling

The retired `reply-is-concise` scored 1.000 in every arm of every run, bare arms included.
**Unrecorded.** It separated nothing: a row at ceiling on both sides is
measuring the model's default rather than the rule. This row is built to separate.
Turn one asks for an audit of a five-file service, is meant to be long, and is
not graded — it exists to fill the context with five true findings the model
wrote itself. Turn two asks which of them breaks first under load, and it is
the reply to that turn both graders read. Four of the five are load-independent
by construction, so the answer is not arguable, and the four decoys are real
bugs rather than trivia: repeating them is repeating things worth knowing,
which is the pull the rule has to overcome.

Two graders, each able to fail the row alone. The floor grader checks the pool
is named, so silence is never rewarded. The selection grader scores what the
reply carried beyond the answer, explicitly not its length.

Its weakness is the interlocutor. `coder_eval` has no scripted user turn, so
turn two's wording is a `constraints` instruction to a roleplaying model rather
than a pin, and the first probe run showed it drifting — see the block above
and the file's own header for what that cost and what was narrowed in
response.

The graders read the dialog, so the drift is scored rather than hidden. Both
criteria set `include_dialog: true`, and each judge checks the second user
turn before it grades anything: a turn that never arrived scores 0.0 under
`ANCHOR: no-question`, and one that asked the question while giving the answer
away scores 0.0 under `ANCHOR: tainted-question`. Grep those tokens to tell a
replicate that measured nothing from one that measured non-compliance, which
scores under `ANCHOR: result`.

`simulation.total_turns` does not do that job. It catches only an abort — a
stop token, or a simulator failure or timeout — and reads 2 for every
self-answer, which is the common failure. What the anchors still leave to the
reader: a lost replicate scores 0.0 like any other, so it drags the mean until
someone drops it by hand, and the check itself is a judgement by the grading
model rather than a field. Read the dialogs before trusting a mean.

### `completion-report-is-lean`, the row that grades a report

`short-question-after-tool-heavy-work` and `answer-selects-from-findings` grade an *answer*.
Both ask a question with one honest factual answer, and issue
#279's comparison across five probes of that shape measured a paired difference
of exactly 0.000, three of them at ceiling in both arms. **Unrecorded.** A probe
both arms pass cannot show a rule working.

The verbosity people complain about arrives somewhere else: in the text an
agent writes *after* doing work the user watched it do. This row grades that.
One turn. The agent is asked to rename one constant across the two files that
mention it, makes the edit, and closes with its own report — which is already
the final assistant message, so both graders reach it with no simulated second
turn and none of the simulator drift the sibling row's header records.

The fixture is empty on purpose: no planted defect, no ambiguity, no surprise,
no second caller, no test and no lint. Every one of those would be a legitimate
thing to write about, and a report that is long because the work was
interesting measures nothing. The honest report here is one sentence. The
prompt says nothing about how to report, how long to be, or brevity — that
steer is what the row exists to exclude.

The fixture must also neutralise the constitution's *own* post-work rules, not
only the work's interest. The constitution tells the agent to commit as it
works and to leave nothing uncommitted, and it is in force in the treated arm
alone — so a sandbox that is not a git repository hands that arm `fatal: not a
git repository`, a real anomaly its report has to carry, and makes the treated
report longer for a reason that is not concision. A `pre_run` command builds
the repository and commits the fixture, so the obligation is met in silence.

That fix is not enough on its own, and three attempts proved it. Adding the
repository armed "commit as you work", which the rubric scored as an
unsolicited next step; making the commit a fact armed `task-worktree`, whose
branch and sibling worktree are the same shape again. The plugin exists to
change how an agent behaves around a repository, so every repository-shaped
fixture hands the treated arm more true things to say, and each fixture patch
produces the next instance of the same confound. **The rubric answers it
instead, in one block: version-control housekeeping the agent REPORTS is NOT
SCORED, and an invitation to do it is a closing offer.** That block in
`completion-report-is-lean.yaml` is the only statement of the rule, and it
alone settles which operations it covers and how each case falls; this
paragraph summarises why the rule exists and defers to it on what the rule
says. The line is report against invitation, not the presence of a question
mark, because the two failures differ. One arm is told to do this work, so
reporting it is that arm obeying its rules. An invitation is the opposite: the
same rules say to commit without asking permission, so an agent that asks has
departed from them. It costs sensitivity, and that is the smaller loss:
scoring the reports would measure which arm the replicate is in rather than
how the agent reports, which inverts the signal rather than weakening it. The
rule holds for the next constitution rule that gives one arm more to say,
where another fixture patch would not.

Two `agent_judge` graders, each able to fail the row alone. The floor states
the rename was made; without it the fluff grader would pay best for silence,
since a report containing nothing contains no fluff. The fluff grader at weight
2 is the finding, and it scores six **named** modes and explicitly not length —
preamble and signposting, recap of what the user already watched, structure
imposed on three sentences, unasked-for hedging, unsolicited next steps, and a
closing offer. Naming the modes is what makes this gradable where "is it
concise" is not, and a correct four-sentence report carrying none of them
scores 1.0.

Both rubrics carry the `format_messages` warning the rows above carry, and it
matters more here than anywhere: the final text is rendered twice, and
"restating what the user already saw" is one of the very modes being hunted, so
a naive judge scores the renderer's echo as the agent's recap. A sibling row
lost five replicates to exactly that.

Neither judge can tell whether the edit landed, so an agent that renames
nothing and says so accurately passes the floor. Two `file_matches_regex`
criteria close that, both at `weight: 0` — which `coder_eval` documents as
purely informational, excluded from `weighted_score` and from the pass gate
alike. The number stays a reading of the report.

They read the sandbox root and only the sandbox root, so a treated-arm agent
that follows `task-worktree` into a sibling worktree leaves the root untouched
and both criteria report the rename never landed — falsely, for an agent
obeying the rules. Nothing scores it, since `weight: 0` is out of the score and
out of the gate; what it costs is the honesty of that signal. Read a weight-0
failure as "check the sandbox", not as "the agent did not do the work".

Two things a reader of a comparison should carry. With weights 1 and 2 and a
floor that is near-constant at 1.0, `weighted_score` is confined to roughly
[0.33, 1.0], so a third of the number is a constant. And both arms run with the
SDK's `claude_code` preset in force, which already instructs against preamble,
postamble and unsolicited summaries — most of the six modes. This row may
therefore sit at ceiling in both arms, like the answer probes it replaces; the
row's own header says what to sharpen if it does. Nothing here has been run: no
score for this row has been measured in either arm.

## The review-depth suite

Seven cases, each one claim:

| Case | The claim | What a broken routing table would do |
| --- | --- | --- |
| `01-readme-is-planning-not-docs` | `README.md` is planning-class *before* it is docs-only | review a rewritten README for correctness bugs |
| `02-tests-sit-with-code` | a 104-line test-only diff gets the judgment tier | skim a hundred lines of new assertions |
| `03-mixed-diff-falls-through-to-code` | one `src/` path makes the whole branch code | judge a sign-handling fix by a planning rubric |
| `04-planning-class-outranks-size` | 904 lines of prose is still prose | bill a security review to a rollout schedule |
| `05-named-depth-outranks-inference` | a depth the user names wins | overrule a request for a full review with a heuristic |
| `06-sensitive-touch-on-a-tiny-diff` | 11 lines of release workflow still get security | miss the file holding the publishing token |
| `07-neg-opening-a-pr` | opening a PR is not a review | tax every branch and train the skimming reflex |

### Grading dispatch

Every one of them grades which agents were dispatched. The draft in PR #36 was
dropped for grading the mode line the skill *announces*, which is a self-report:
a skill announcing "Standard" and then dispatching the Full panel would have
passed it.

**No criterion in `coder_eval` 0.11.6 can be relied on to see `subagent_type`.**
`command_executed` matches against `json.dumps(parameters)` truncated to 2000
characters, so whether the field is inside the window depends on how long the
prompt is and on where the key lands in the serialisation — neither of which the
eval controls. When it falls outside, the criterion reports "not dispatched" for
a dispatch that happened: it silently zeroes a positive and *inverts* a negative
control, and both failures read exactly like a router that dispatched nothing.
`llm_judge` and `agent_judge` are no help either: their tool-call summariser
renders an `Agent` call as its `description`, a three-word label the model
writes.
**Measured, but unrecorded.** Three live `review` dispatches (CLI 2.1.263,
`coder_eval` 0.11.6, `claude-opus-5`, 2026-09-07 — the three-agent panel over
a 1,397-line diff) serialised to 1,437 / 1,382 / 1,387 characters with
`subagent_type` as the **first** key, comfortably inside the window: `review`
hands its agents a summary and a file list, not the diff. So the truncation
does not bite this skill today, and an earlier reading of
this section — that key order is fixed at `description, prompt, subagent_type`
and the prompt therefore pushes the field past the window on *every* dispatch of
consequence — was wrong.

The hook below stays regardless, and the measurement is why it is worth its
weight rather than why it is unnecessary: argument order is the model's to
choose call by call, prompt length is the skill's to change without telling
anyone, and the failure mode is silent in the direction that looks like a
result.

So the observation is taken with a `PreToolUse` hook matching `^(Agent|Task)$`
— both names, because the harness has used both — wired through
each task's `claude_settings` and recorded by
`fixtures/review-depth/shared/record-dispatch.py`. It appends one
`subagent_type` per
line to `.fixture/dispatched.txt`, which `file_matches_regex` reads.

The hook is part of the **instrument**, not of the plugin under test: it is
configured by the eval, it fires identically in both arms, it reads the tool
input verbatim, and it emits nothing — so it cannot veto a dispatch or disagree
with the plugin's own `PreToolUse` hook on the same event. And it is still not
the mode line: the mode line is what the skill says it decided; the roster is
the argument it passed to the tool.

The roster is created empty by the fixture, so a `must_match: false` criterion
reads "nothing was dispatched" instead of erroring on a missing file — which is
the entire `bare` arm.

**What it proves, exactly.** `PreToolUse` fires before the tool resolves
`subagent_type`, so a roster line is a dispatch *requested*, not a subagent
confirmed to have run. A `review` that asks for `security-reviewer` under a name
the session cannot resolve records the line anyway. That is the routing decision
— which is what these cases grade — but it is not proof the reviewer ran, and no
criterion here claims otherwise. The old `command_executed`-on-`Agent` shape had
the same property, for the same reason.

**Two things the hook must never do**, both guarded rather than asserted in
prose. A `PreToolUse` hook that exits non-zero *blocks* the tool call, so a
recorder that failed would not merely lose the roster — it would veto every
dispatch, in both arms, and report a routing table that dispatched nobody. The
hook command is therefore absolute (via `$CLAUDE_PROJECT_DIR`, which Claude Code
puts in every hook's environment) and ends in `|| true`. And because `|| true`
would then hide a genuinely broken recorder behind an empty roster,
`scripts/check-eval-fixtures.sh` runs the recorder against the copy the sandbox
would get and fails `make check` if it does not record.

The hook also writes nothing to stdout, so it cannot contest the `updatedInput`
returned by the plugin's own `PreToolUse` hook on the same event.

### What the sandbox can see

The fixtures are mounted at `.fixture/` inside the sandbox and the agent under
test has `Read`, `Grep`, `Glob` and `Bash`, so anything there saying what a case
expects is an answer key one `cat` away. Three things follow, and they are
enforced rather than asked for:

- **The fixtures carry mechanics, not claims.** The reasoning lives here and in
  the task YAML. `evals/fixtures/review-depth/` is prose about `git`.
- **A task mounts the shared scaffolding plus its own case, and nothing else** —
  two `template_dir` sources at the same `mount_point`. The case script is
  `case.sh` in every case, because its *filename* is copied into the sandbox too
  and `sensitive-tiny.sh` names the routing rule being graded as loudly as any
  comment would.
- **No fixture file contains the substring `skills/`.**
  `scripts/check-eval-fixtures.sh` greps for it, because `skill_triggered`
  counts such a path in any tool parameter as engaging that skill — so a fixture
  carrying one would score as a skill firing the moment the agent read the file.
  (The check found its first offender immediately: a comment explaining the
  rule.)

**None of this is a boundary, and it should not be described as one.** The suite
runs on the default `driver: tempdir`, where `coder_eval`'s own note is that
"the agent under evaluation runs with the same filesystem view as the harness" —
its anti-cheat permission window is a documented no-op outside a container. So a
session with `Bash` can read this file, read the task YAML, and write to
`.fixture/dispatched.txt` directly. What the rules above buy is that nothing
*puts* the answer in front of a session going about its work; they buy nothing
at all against one that goes looking. `sandbox: {driver: docker}` is what would
make it a boundary, and moving the roster outside the sandbox needs the same
upstream fix as everything else here.

The upstream fixes that would retire this: make the truncation bound
configurable, or render `subagent_type` in the judge's tool-call summary.

**The mode line is not checked at all here, and that is a decision.** Keeping it
as a low-weight secondary signal was the plan, and it needs an `llm_judge` on
every row — the final message has no deterministic matcher — which would put a
scored model judgment, and its cost, on seven cases whose whole point is that
they are deterministic. Dispatch is the outcome; the mode line is the narration
of it, and the narration is what PR #36's draft was dropped for grading. If the
announced depth is ever worth asserting on its own, the way in is the roster's:
observe it where it is complete, not through a judge.

**Every case size is load-bearing and none should be "tidied".** The depth table
turns on ~50 and ~800 changed lines, so a case that drifts across a threshold
does not fail — it re-routes, and then measures a depth it was not written for.
`01`, `02` and `03` are over ~50 on purpose (under it they route to Skim on size
alone, whatever bucket their paths land in); `04` is over ~800; `05` and `06`
are deliberately under ~50, because "tiny and still reviewed" is the whole
claim. `scripts/check-eval-fixtures.sh` holds those bounds and fails on drift.

### The git problem

`review` needs a real repository — a base branch, a topic branch ahead of it, a
remote to diff against — and `coder_eval`'s sandbox does not build one:
`starter_files` and `template_dir` copy loose files, and `type: repo` clones a
URL onto a checked-out default branch, which is not the shape a branch under
review has. A `tempdir` of loose files makes `review` correctly refuse —
*"there's no branch, no commit history, nothing for the `review` skill to diff
against"* — which is a true negative from a bad case, and indistinguishable in
the report from the finding the suite exists to produce.

**`pre_run` is the seam.** It runs a shell command inside the sandbox after
setup and before the agent, and by default aborts the evaluation on a non-zero
exit, so a fixture that fails to build never reaches a model and never scores a
misleading 0. Each case mounts `fixtures/review-depth/shared/` and its own
`fixtures/review-depth/cases/<name>/` at `.fixture` — two `template_dir`
sources, one mount point, for the reason in "What the sandbox can see" — and
runs `.fixture/case.sh`. The scripts `git init` the sandbox
root, exclude `.fixture/` through `.git/info/exclude` (a `.gitignore` would show
up as a changed path and shift the diff's *kind*, which is the one thing this
suite measures), commit a base tree, publish it to a bare `origin` under
`.fixture/`, then branch, change, commit and push. The push is not optional:
`review` stops at "Local changes not pushed" when the branch is ahead of its
remote, and would never reach the routing decision under test.

`scripts/check-eval-fixtures.sh` builds all six and asserts that shape. It runs
in `make check` because it needs only git and bash — and because a fixture that
stops building does not turn the suite red, it turns every case into a silent 0.

These cases run in **Local mode**: there is no GitHub MCP in the sandbox, so the
pull-request lookup finds nothing and the skill assembles the diff from git.

## The Omp arm

The same suites and plugin run Omp subjects with paired `bare` and
`with-plugin` variants. GLM 5.3 Flash is the tier probe beside full GLM.
The committed GPT 6 Sol and Luna experiment files still pin Vercel AI Gateway
routes. They are unsupported legacy configuration, not supported subjects;
issue #494 owns their migration. Do not run those targets until the Codex-only
subject routes are committed. Historical run records remain unchanged.
`docs/notes/0013-the-omp-arm.md` records the adapter decision.

Only a Claude judge requires a Claude Code execution session for an Omp
subject run. A non-Claude judge uses its own configured route. See
["Choose the execution session first"](#choose-the-execution-session-first)
before setup or probes.

**On a fresh machine, set up first:**

```sh
make evals-install && make evals-setup-omp
```

`evals-setup-omp` installs `omp` with CI's command when it is missing, and
checks that Omp lists each arm's pinned model. It is free and idempotent.
Non-GPT gateway arms need `AI_GATEWAY_API_KEY`, the name Omp reads. A cloud
container exports `VERCEL_AI_GATEWAY_API_KEY` instead, and the Makefile maps
that name to Omp's for those targets. Without either, Omp lists no gateway
model and the target fails, naming the variable. An `openai-codex` arm needs
Omp's own Codex login; the target reports it as unconfigured and does not
fail.

```sh
make evals-run-omp-glm-5-3                    # GLM 5.3 only
make evals-run-omp-glm-5-3-flash              # GLM 5.3 Flash tier probe
make evals-run-omp-deepseek-v4-pro            # DeepSeek v4 Pro only
make evals-run-omp-gpt-5-6-sol                # GPT 5.6 Sol via openai-codex
make evals-run-omp-glm-5-3 TASKS='tasks/pr/*.yaml'
```

Each experiment pins one provider/model ID, and the Omp home the agent borrows
must configure it. Every GPT subject, judge, and helper call must use
`openai-codex`; no GPT call may use the Vercel AI Gateway.

| Experiment | Model |
| --- | --- |
| `omp-glm-5.3.yaml` | `vercel-ai-gateway/zai/glm-5.3` |
| `omp-glm-5.3-flash.yaml` | `vercel-ai-gateway/zai/glm-5.3-flash` |
| `omp-deepseek-v4-pro.yaml` | `vercel-ai-gateway/deepseek/deepseek-v4-pro` |
| `omp-gpt-5.6-sol.yaml` | `openai-codex/gpt-5.6-sol` |
| `omp-gpt-6-sol.yaml` (unsupported legacy; do not run) | `vercel-ai-gateway/openai/gpt-6-sol` |
| `omp-gpt-6-luna.yaml` (unsupported legacy; do not run) | `vercel-ai-gateway/openai/gpt-6-luna` |

For a supported non-GPT model, the experiment needs `omp` on PATH and its
provider's credentials: the gateway key above or a login in the caller's own
`~/.omp/agent/`. The agent borrows that directory by symlink into a throwaway
Omp home and writes nothing back into it. It does not borrow `config.yml`: the
throwaway home gets its own, which pins every Omp chat role to the arm's
`model`. Unpinned, Omp's subagents and helper calls would run on whatever the
provider catalog offers.

### Running an Omp arm

```sh
make evals-install                       # rebuilds the local agents every time
export AI_GATEWAY_API_KEY=…              # for a non-GPT gateway subject only
omp models find glm-5.3                  # the supported non-GPT route must resolve
TASKS='tasks/undertake/*.yaml'
setsid nohup make evals-run-omp-glm-5-3 TASKS="$TASKS" JOBS=16 > glm.log 2>&1 &
```

- **The judge runs on its selected route.** Only a Claude-judged `agent_judge`
  runs through the Claude Code SDK and inherits the shell's Claude subscription
  ([`0014`](../docs/notes/0014-the-judge-runs-on-the-subscription.md)). Leave
  `ANTHROPIC_API_KEY` and `ANTHROPIC_BASE_URL` alone: do not direct them to a
  gateway or use a metered Anthropic route.
- **Shell access is inherited.** Some rows grant `bash`, so the agent can use
  the shell's GitHub access. A Claude Code cloud proxy grants the owner's
  access as well. Run only tasks whose tool permissions and effects you accept;
  this is a risk disclosure, not a credential-isolation gate.
- **Run replicates in parallel.** `JOBS` sets how many run at once; the
  default is one, and one at a time a suite takes about two hours. A replicate
  waits on model calls, not on the container: at 12 at once, a four-core
  container ran about 70% busy.
- **The Omp targets raise every turn cap to 30.** `OMP_RUN_LIMITS` in the
  `Makefile` says why: caps sized for the Claude Code arm cut Omp off before
  its reply.
- **Run it detached.** An interrupted run continues from its run directory:

  ```sh
  cd evals && TELEMETRY_ENABLED=false coder-eval run -e experiments/omp-glm-5.3.yaml \
    --run-dir runs/<run_id> --resume --max-parallel 16 \
    -D run_limits.max_turns=30 -D run_limits.turn_timeout=600 -D run_limits.task_timeout=1200 \
    --exclude-tags claude-only,codex-only,skip:omp,model-classes $TASKS
  cd .. && make evals-record RUN=evals/runs/<run_id> EXPERIMENT=evals/experiments/omp-glm-5.3.yaml
  ```

- **`make -n` does not dry-run a run target.** Its recipe line calls
  `$(MAKE)`, so make executes it. `make evals-plan` is the free check.

**`agent: {type: omp}` is not a built-in kind.** It comes from
`coder-eval-omp/`, a `coder_eval` plugin in this repository, installed beside
the pinned harness by `make evals-install`. Its README says what the adapter
normalises and why each omission becomes a silent zero.

**An experiment file per model, a run per model, and tags in between.** Eleven
rows cannot be graded identically on Claude Code and Oh My Pi, so each is two
files tagged `claude-only` and `omp-only`, with `-omp` on the second's
`task_id`. `make evals-run` excludes `omp-only`; every `make evals-run-omp-*`
target excludes `claude-only` and `codex-only`; and with the Codex arm each
also excludes `codex-only`. `make check-eval-arms` holds the sets, model files,
variant pair and Make targets in step.

| Suite | Claude-only row | Omp counterpart |
| --- | --- | --- |
| `deps` | `05-references-search-not-list` | `05-references-search-not-list-omp` |
| `pr` | `07-one-call-sets-both` | `07-one-call-sets-both-omp` |
| `pr-title` | `07-mcp-not-gh-pr-edit` | `07-gh-pr-edit-not-mcp-omp` |
| `pr-body` | `07-mcp-not-gh-pr-edit` | `07-gh-pr-edit-not-mcp-omp` |
| `review-cycle` | `07-wait-for-ci-is-not-a-sleep` | `07-wait-for-ci-is-not-a-sleep-omp` |
| `review-cycle` | `08-subscribe-before-first-read` | `08-run-watch-then-statuses-omp` |
| `session-title` | `07-get-session-before-set` | `07-one-call-sets-the-title-omp` |
| `judgement-call` | `01-ask-in-chat-hook` | `01-ask-in-chat-extension-omp` |
| `undertake` | `08-wake-slot-is-refilled` | `08-cadence-stops-at-ready-omp` |
| `undertake` | `12-draft-ci-remains-unfinished` | `12-draft-handoff-omp` |
| `undertake` | `09-session-fields-for-claim` | `09-claim-carries-the-session-id-omp` |
| `task-worktree` | `01-isolate-new-task` | `01-isolate-new-task-omp` |

Each Omp row names its sibling with a `forks:<task_id>` tag, which is what
`check-eval-arms` pairs. The seven `review-depth` rows remain `claude-only`
because they drive Claude's settings and dispatch hook.

**`plan` does not fail on a broken arm.** With no plugin installed,
`coder-eval plan` prints a resolution failure and exits 0. `make evals-plan`
runs `scripts/evals-variants.py` first, so every variant in every model file
must resolve before a paid run begins.

**The Omp arm enforces the tool lists through `omp --tools`, with one
exception.** An allowed `Skill` keeps `read` on, because Omp engages a skill by
reading `skill://<name>`. A trigger row that denies `Read` therefore still has
`read` on this arm. A list the arm cannot express, such as an allowed tool with
no Omp twin, fails the task. `docs/notes/0013-the-omp-arm.md` records what
`--tools` does not restrict. Omp records made before issue #459 ran with every
tool on. Token accounting is best-effort. The adapter records the evidence it
has in each run's `environment_info`.

## The Codex arm

The same suites, the same skills, a third harness.
`docs/notes/0015-the-codex-arm.md` is the decision; this is how it is run.

```sh
make evals-run-codex                          # the Codex arm
make evals-run-codex TASKS='tasks/pr/*.yaml'  # one suite of it
```

It needs the Codex SDK, which `make evals-install` brings in with
`coder-eval-codex`, and OpenAI credentials the SDK can authenticate with
(`CODEX_API_KEY`, or an existing ChatGPT login on the machine).

**`agent: {type: codex-daily-driver}` is not the built-in `codex` kind**, and
the difference is not cosmetic. `coder_eval` already ships a `codex` agent that
does almost all of this — it drives the SDK, links a `plugins:` root's skills
into `<cwd>/.agents/skills/`, and records `commandExecution` as `Bash` with its
command string. What it does not do is build the `[RESULT - …]` transcript, and
every rubric here anchors on that tag and scores 0.0 without it. Point the
experiment at `codex` and the suite runs, costs money, and reports zeros that
read exactly like a plugin that never loaded — so `make check-eval-arms` reads
each experiment's variants against the arm table and refuses that spelling.
`coder-eval-codex/` is the built-in subclassed; its README says what it adds and
why.

**It also resolves the plugin root**, which the built-in does not.
`_setup_skills` symlinks each skill by the path it was handed, so the relative
`path: ".."` every experiment here writes — right for the Claude agent, which
never sees an unresolved path — links fifteen skills whose bodies point back at
their own directory. Measured with the current tree: fifteen entries, none with
a readable
`SKILL.md`, and `_setup_skills`'s own "0 skills linked" warning silent because it
counts entries. `start()` makes the root absolute and then raises rather than
warns when no readable skill arrived.

**This arm needs no skill-engagement normalisation, and the Omp arm does.**
Omp reads `skill://<name>`, which `skill_triggered` cannot see. Codex has no
skill tool at all: the model is handed a skills table and opens
`.agents/skills/<name>/SKILL.md` with the shell, and `skill_triggered` matches
`skills/<name>/` in any string tool parameter — its own docstring names Codex as
the agent that branch was written for. Issue #185 expected the Omp spelling
here; the spike in #181 measured that Codex does not use it.

**Eleven `codex-only` rows.** Each forked row grades a route stated in a
`skills/<name>/references/*.md`, so a Codex counterpart needs a
`references/codex.md` to grade against.

| Suite | Claude row | Codex counterpart | What the Codex row grades |
| --- | --- | --- | --- |
| `deps` | `05-references-search-not-list` | `05-gh-search-not-list-codex` | `author:app/dependabot` inside a `--search` query |
| `judgement-call` | `01-ask-in-chat-hook` | `01-ask-in-chat-request-user-input-codex` | `request_user_input`, denied by the same `hooks/ask-in-chat.py` |
| `pr` | `07-one-call-sets-both` | `07-one-gh-pr-edit-sets-both-codex` | one `gh pr edit` carrying both |
| `pr-title` | `07-mcp-not-gh-pr-edit` | `07-gh-pr-edit-title-codex` | `gh pr edit --title` |
| `pr-body` | `07-mcp-not-gh-pr-edit` | `07-body-file-not-body-codex` | `gh pr edit --body-file`, not `--body` |
| `review-cycle` | `07-wait-for-ci-is-not-a-sleep` | `07-there-is-no-wait-codex` | no sleep on a harness that ships one, and the stop |
| `review-cycle` | `08-subscribe-before-first-read` | `08-both-endpoints-once-codex` | the check runs and the commit statuses, one read each |
| `session-title` | `07-get-session-before-set` | `07-one-call-or-no-surface-codex` | one `agent_tasks` call with `threadId` omitted, or the stop |
| `undertake` | `08-wake-slot-is-refilled` | `08-no-wake-to-keep-codex` | no durable wake, so the cadence is handed on |
| `undertake` | `12-draft-ci-remains-unfinished` | `12-draft-handoff-codex` | unfinished drafts need an owner-resume handoff |
| `undertake` | `09-session-fields-for-claim` | `09-claim-records-session-na-codex` | branch from git, `session: n/a` recorded, model from the harness |
| `task-worktree` | `01-isolate-new-task` | `01-isolate-new-task-codex` | shell `workdir` and file paths keep every later operation in the task worktree |

None is its sibling's stem plus `-codex`, for the reason the Omp table above
gives: the stem states Claude's route, and on Codex the row grades the opposite.
Two of them grade a *stop* — Codex is the first harness where the right answer
to "title this session" and to "wait for CI" is that there is no way to do it.

Three of the eleven — `pr`, `pr-title` and `deps` — grade the same `gh` call their
Omp counterpart does, because Codex has no GitHub tool of its own either. They
need their own files regardless: an arm tag claims exactly one arm, so without
them the Codex arm would not measure those routes at all. `pr-body` is the
exception among the `gh` rows: Codex prescribes `--body-file` where Omp's row
grades `--body`.

**`tasks/constitution/*` is not in this arm**, and carries `skip:codex` to say
so. That tag takes a row out of one arm and leaves it in the rest, which an arm
tag cannot express. The reason is that `coder_eval`'s Codex agent links skills
and installs nothing else — no `hooks/hooks.json`, so no `SessionStart` and no
`PreToolUse` on the `Agent` tool, and no constitution in the session. Every row
there would score 0 for a reason that has nothing to do with the constitution. #181
measured that a *real* Codex session does load the hook file and does deliver
the constitution, behind persisted hook trust and an exactly-echoed
`hookEventName`; whether the SDK's app-server can be driven through those gates
is unmeasured, and `0015` says what settling it needs.

**Four things this arm measures more weakly than the Claude arms**, recorded so
a report is read with them in mind.

- **No bare-Codex control.** As with Omp: the arm reports the treated side
  alone, so a row's score has no delta beside it, and the no-fire rows in the
  same run are what say the skills reached the session at all.
- **`allowed_tools` and `disallowed_tools` are not enforced**, and Codex runs
  full-access on every `permission_mode` by the built-in agent's own design —
  `coder_eval`'s per-run sandbox is the boundary. That costs more here than on
  Omp: the mitigation under "How the graders ported" removes `Read` so a denied
  read of `skills/<name>/SKILL.md` cannot score as an engagement, and on Codex
  that read *is* the engagement signal. A no-fire row scoring badly in this arm
  should be read as that before it is read as a skill firing when it should not.
- **The constitution suite is absent**, per the paragraph above.
- **The model pin is unverified.** `gpt-5-codex`, pinned so a report says what
  produced it. Nothing here has resolved it against an account.

`codex_skills_linked` lands in each run's `environment_info`, for the reason the
Omp arm's equivalents do: a red arm and an arm whose skills never arrived must
not read alike. It counts skills with a readable `SKILL.md` rather than
directory entries, which is what makes it an answer — broken symlinks still
count as entries.

**It is the only such field, because `coder_eval` reads
`get_environment_info()` once, during setup, before any turn runs.** A counter
kept over the turns — how many transcripts this package retagged, say — would
always be recorded as zero, which is worse than absent: a field that says
nothing while looking like a measurement. The one thing worth alarming on, a
turn arriving with the anchor already in it, is logged where it happens instead:
it means the built-in has started rendering the transcript itself and
`coder-eval-codex` has become a no-op worth deleting.

## The model-classes suite

Every suite above is authored: a case is a fixture someone built to exercise
one rule. `model-classes` is built instead, by `scripts/evals-cases-from-prs.py`,
from pull requests this repository's own sources already merged. A merged
pull request that closed a task issue and shipped its own tests is an answer
key nobody has to write: the base SHA is the "before", the merge SHA is the
"after", and the PR's diff to its test files is what a correct implementation
must make pass. What it measures is the model, not the skill — the suite
carries no plugin and no ablation, one variant per case, because the question
is whether a given model, run in the `task` role real dispatch would put it
in, finishes ordinary delegated work and leaves its own tests passing.

**What it measures.** Six cases today, all from `jmcvetta/career`: three
`mechanical` and three `implementation`, small qualifying candidates whose
answer key asserts only what the issue decides (two of them by a recorded
trim, below), each verified at build time to fail on the base SHA and pass on
the merge SHA before it was shipped. A case's `initial_prompt` is the title
and body of the issue the pull request closed, and names neither number; its
three `run_command` criteria check, in order,
that no test file present at the base SHA was deleted, that no skip/xfail
marker was added to one, and that the pull request's own tests pass once
`tests.patch` is applied. `shared/apply-tests.sh` applies it: it first puts
each path the patch names back to the base SHA, because an agent that adds a
test beside its change has edited the very hunk the patch rewrites, and a
plain `git apply` would score that correct change 0. The agent's own tests in
other files stay. `evals/fixtures/model-classes/candidates.json`
records every qualifying pull request the builder saw, selected or not, so a
later run can widen the suite without re-walking history.

Career-462 narrows that last command to its measured contract node,
`test_projected_releases_skips_release_prs`. The source module also checks
declared GitHub labels, which is unrelated to the projected job and tries to
query GitHub when `gh` is authenticated. The isolated fixture correctly removes
its source remote; selecting the projection test keeps the grader offline
without weakening or skipping the live label-drift test in the source suite.
The selected command is stored in `candidates.json`, so `--rewrite-tasks`
preserves this case-specific grading boundary.

**Keeping the answer out of reach.** The merged change is the answer, and the
agent runs on the same host as the grader, so the suite closes each road to it:

- `tests.patch` and the two manifests sit in the case's `reference:`
  directory. coder_eval stages that outside the sandbox and names it in
  `REFERENCE_DIR` for criteria only, so a broad `grep` of the checkout cannot
  surface it. Under the `tempdir` driver the agent is the same user as the
  harness, so this hides the key rather than locking it.
- `shared/lib.sh` removes the clone's `origin` once it has fetched the base
  SHA, so `git fetch origin <default-branch>` or `refs/pull/<n>/head` has
  nowhere to go.
- The prompt carries the issue text and tells the agent not to consult the
  source repository on GitHub; with no number to look up, it has no reason to.

Hiding is not locking, so `scripts/evals-record.py` also checks every
replicate's tool calls, and what they printed, for the answer key's paths, any
`git` network command, a `gh` command or URL on the source repository, and a
pull ref. Bash calls are parsed as shell syntax: command positions and
executable substitutions count. Quoted arguments and here-document bodies
are data; substitutions in unquoted here-documents still run and count. The
recorder treats Bash syntax it cannot parse as contact rather than silently
accepting it.
A replicate that reached any of these is recorded with that evidence
under `answer_key_contact` and a measured score of 0. It is scored as a
failure, not dropped: a model that goes looking when stuck has failed the
case.

**What it does not measure.** No `reasoning` case: that class is decided by
the production table and public benchmarks, not by a fixture small enough to
grade in two minutes (see `skills/issue-body/references/model-classes.md`).
No plugin, no skill routing, no `bare`/`with-plugin` delta — that comparison
is the `omp` arm's, over a different question. And nothing here proves a
model *should* run in the `task` role generally, only that it cleared a few
specific cases; `make evals-run-classes` is a floor to check before promoting
a model into that role, not the whole case for doing so.

**Running it.** Each `evals/experiments/classes-<name>.yaml` file pins its own
`defaults.agent.model` and its own `defaults.agent.type`: the rows pin no
kind, so one suite measures a model on Omp or on Claude Code. Personal
`omp_configs/` overlays do not define or validate these experiments:

```
make evals-run-classes MODEL=glm
make evals-run-classes MODEL=cocktail
make evals-run-classes MODEL=opus-low
```

The Claude Code files (`classes-opus-low`, `classes-sonnet-high`,
`classes-sonnet-low`) set effort through `sdk_options.effort`, which the
Agent SDK passes as `claude --effort`. They run the bare session
`with-without.yaml` measures against — `plugins: []` and
`setting_sources: [project]` — so an advisor or a plugin in the operator's own
user settings never reaches the model under test.

`defaults.repeats` is 3 in every file, so a full run is 3 replicates per
case per model, each a real `git apply` plus the
repository's own test command (`pytest` or `pnpm exec vitest`) inside a
shallow single-commit checkout of the source repository. `GITHUB_TOKEN` or
`GH_TOKEN` must be set — the `tempdir` driver runs `pre_run` as a plain host
process, so a token exported before `coder-eval run` is what
`shared/clone-base.sh` clones with. Narrow with `TASKS=tasks/model-classes/<repo>-<pr>.yaml` for one case,
or use the `smoke`-tagged case per class (the smallest of each) to check a new
overlay cheaply before spending a full run on it.

**Building more cases.** `python3 scripts/evals-cases-from-prs.py owner/repo
[--path-prefix DIR]` scans a source's merged pull requests and appends
qualifying ones to `candidates.json`; `--select` then runs the build-time
answer-key check on the smallest candidates of each class and emits fixtures
and task YAMLs for the ones that pass, up to `--per-class` each (default 3);
`--rewrite-tasks` regenerates the selected cases' YAMLs from
`candidates.json` after a template change. The build-time check cannot tell whether the
answer key asserts only what the issue decides, so read each new case's issue
against its `tests.patch` before shipping it. A key that asserts a name, path
or wording the issue leaves open fails a model that did exactly what was asked;
`--exclude owner/repo#N=reason` takes such a case out for good and deletes its
fixture.

Where only a few assertions overreach, trim the key instead. **A trim
removes requirements the source issue does not decide, and nothing else.** An
exact-output assertion may be replaced by a weaker behavioural one that keeps
the diagnostic or safety contract the issue requires. A trim never adds a
product requirement, never removes a required behaviour, and is never tuned
to a model's output. Apply the full key to a checkout of the base SHA, delete the
assertions or tests the issue leaves open, and diff against the base SHA
(`git add -N` any new file first); the result replaces the case's
`tests.patch`. `--trim-key owner/repo#N=reason` records each replacement and
its source-contract rationale on the candidate, and a trimmed case refuses a rebuild from the pull
request's diff. `--verify-case owner/repo#N` then runs the build-time check
on the committed key: it must fail on the base SHA and pass on the merge SHA,
both applied through `shared/apply-tests.sh`, and the manifests must match it.
An `unlabelled` candidate — one whose closed issue carries no `## Model
class` section — needs `--class-override owner/repo#N=mechanical` (or
`implementation`) before it can be selected; four shipped cases carry one,
reviewed by hand against `skills/issue-body/references/model-classes.md`'s
table. The script's own module docstring has the full usage, and its
self-tests (run offline, every invocation, against inline JSON-shaped GitHub
API fixtures) are the acceptance test for the qualifying filter, the test-file
split, the class and elapsed reads, and `task_timeout` derivation. No
standalone CI check repeats them: the builder runs them before every
invocation, so a defect in it surfaces on its next run.

`scripts/check-eval-arms.py` treats `model-classes` as a fourth arm that
owns both the `omp` and `claude-code` kinds — it measures a model, not a
harness — so the agent kind alone cannot say which arm a row belongs to; the
`model-classes` tag is what does. The checker discovers
`classes-*.yaml` experiments inside the eval suite and requires each to pin
its model. Personal Omp configuration is not an input to this check.

## Two defaults, decided on purpose

- **Telemetry is off.** `coder_eval` sends usage telemetry by default to a
  UiPath-controlled Application Insights endpoint, through a connection string
  base64-embedded in the package so that "a fresh install reports usage
  telemetry … with no configuration". It is ingestion-only and documented, and
  the base64 is explicitly not for secrecy. It is still not something a tool
  that may one day gate a merge should do without being asked. `TELEMETRY_ENABLED=false`
  lives in the Makefile so it cannot be forgotten at a prompt; pass it yourself
  if you invoke `coder-eval` directly.
- **The version is pinned**, in `CODER_EVAL_VERSION` in the Makefile.
  Pinnability is the whole reason these suites are not written for
  `claude plugin eval`; leaving the harness to float would give that reason
  away.

Two more defaults are overridden in `experiments/with-without.yaml` rather than
inherited: the agent model (`coder_eval` defaults to the stale
`claude-sonnet-4-6`) and `repeats`.

One to know about and not fix here: `coder_eval` calls
`load_dotenv(override=True)`, so a `.env` file beats your shell environment —
`ANTHROPIC_API_KEY` included. A stale `.env` in the working directory is a
surprising way to run a suite against the wrong account.

## Cost

`plan` warns on every task here that `task_timeout` exceeds `turn_timeout`.
That is deliberate and the tasks say so: `turn_timeout` is the agent's budget,
`task_timeout` is a watchdog armed before the turn and still running while the
criteria are checked, so equal values mean a turn that uses its budget is killed
as a TIMEOUT before it can be graded. The headroom is the difference.

`run_limits` caps turns and wall clock per task, but nothing caps the bill. The
64 trigger-accuracy cases are cheap: five turns each, `Skill` the only tool,
and the fire half stops the moment the skill fires. `review-depth` is not: its six fire
cases each dispatch a real reviewer panel over a real diff, five times, in the
`with-plugin` arm. The `bare` arm is cheaper but not free: it has no `review`
skill and none of the plugin's reviewer agents, but it keeps the `Agent` tool
and thirty turns, so a session that decides to review the diff by hand can
still spend. Its no-fire case pays for a panel too, on exactly the trajectory
it is trying to catch. Run one suite at a time with
`TASKS=` while iterating, and keep `make evals-plan` between edits, where the
mistakes are free.

## What is not here

CI gating. It was only ever blocked by CI having no credentials, which is a
separate decision from which harness runs the cases — so it is deferred, not
foreclosed.

`claude plugin eval`'s MCP mocking, with `expect:` frontmatter that aborts a run
on a wrong argument, has no equivalent in `coder_eval`. No suite here used it,
so this is a cost deferred rather than paid — but it is the thing to re-examine
if a suite ever needs to assert *"filed the ticket in the wrong project."*
