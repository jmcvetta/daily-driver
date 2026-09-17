# Evals

Seventeen suites, run by [`coder_eval`](https://github.com/UiPath/coder_eval) rather
than by `claude plugin eval`. The reasoning for the harness is
[`docs/notes/0002-eval-harness.md`](../docs/notes/0002-eval-harness.md);
the short version is that the built-in cannot be run on this account, is
publicly undocumented, announces no changes, and — decisively — ships inside
the `claude` binary, so there is no version to hold back.

```
evals/
├── experiments/
│   ├── with-without.yaml           the ablation every Claude case is measured under
│   ├── omp-*.yaml                  one two-variant Omp experiment per model
│   └── codex.yaml                  the same suites, on Codex — see "The Codex arm"
├── tasks/
│   ├── pr/              does `pr` fire when a PR is opened, and only then?
│   ├── pr-title/        … when a title is written, and only then?
│   ├── conventional-commits-type/
│   │                    … when a type is chosen, and never for a commit message?
│   ├── pr-body/         … when a body is written, and only then?
│   ├── issue-body/      does a task issue keep a terse human opening and a full agent `Detail`?
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
│   └── review-depth/    does `review` send the right panel at the diff?
├── fixtures/review-depth/
│   ├── shared/          builds the git repository every case starts from
│   └── cases/<name>/    one `case.sh`, mounted alone beside `shared/`
├── coder-eval-omp/      the `omp` agent kind, so the same cases run on Omp
└── coder-eval-codex/    `coder_eval`'s Codex agent, with the judge's anchor put back
```

## Running them

```sh
make evals-install    # coder-eval, pinned; uv fetches Python 3.13 itself
make evals-plan       # validate every case. Costs ZERO tokens. Do this first.
make evals-run        # the whole suite on Claude Code, both variants. Real money.

make evals-run TASKS='tasks/pr/*.yaml'     # one suite
make evals-run TASKS='tasks/*/*-neg-*.yaml' # just the no-fire half

make evals-run-omp    # every Omp model, each with bare and treated variants.
make evals-run-codex  # the same suites on Codex. Needs the Codex SDK and a key.
```

The `*-neg-*` selector is a filename glob, and one absence assertion does not
live in a file it matches: `tasks/pr/02-open-a-pr.yaml` is a fire case that
also asserts `undertake` stays silent. Add `tasks/pr/*.yaml` when the question
being asked is about collisions rather than about the no-fire cases as such.

Not part of `make check`. The cases need a live model and this repository's CI
is deliberately credential-free. What *is* part of `make check` is
`check-eval-fixtures`, which builds every review-depth fixture repository with
nothing but git — see "The git problem" below for why that leg exists.

**`llm_judge` needs its own transport, separate from the agent's.** `coder_eval`
does not fail a run over a missing judge transport — it scores the criterion
0.0 and keeps going, which reads like a real result in the report and is not
one. `make evals-run` runs `scripts/evals-preflight.py` first and refuses to
start when that would happen; see
[`docs/notes/0012-the-judge-needs-its-own-transport.md`](../docs/notes/0012-the-judge-needs-its-own-transport.md).
"Two defaults, decided on purpose" below covers how `.env` factors into which
transport gets picked.

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
`01` runs the same Git fixture through each CLI arm and accepts only a branch
from the remote default, a registered sibling worktree, the changed file there,
and an unchanged primary checkout. `04` starts detached and requires the
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

It asks two questions, not one. `reaches-subagent` asks whether the text
arrives; the three behaviour cases ask whether it changes anything once it
has. The second is what a delivery test cannot tell you, and until it existed every
amendment to the constitution shipped on argument alone. See "The constitution
suite" below for why `reply-is-concise` is the one the file got first.

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

All four rows carry `skip:codex` and are absent from the Codex arm. `coder_eval`'s
Codex agent links skills and installs no hooks, so the constitution never
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

### `reply-is-concise`, the compliance half

Reach is settled; whether an injected rule *lands* is not, and `reply-is-concise`
is the first case here that asks. It picks the `Before you reply` rule because
a session obeys or breaks it in plain sight — the cheapest place in the
repository to measure whether an injected rule changes behaviour, and a cheap
instrument is the one that gets built.

The case asks why a documented-inclusive slice drops its last item. The honest
answer is one line, and everything about the situation pushes the other way: a
bug invites a diagnosis, a fix, a test and a summary. `Do not change any code`
in the prompt, and closed `Write` / `Edit` / `Bash`, remove the one honest
reason for length — an agent that fixed the bug has something to report.

Issue #279 rewrote the rule — from a four-line budget to the audience rule,
human-facing text silently restated concise — and rewrote the case with it. A
line count can no longer grade the rule: the constitution no longer carries a
number to inherit, and a count rewards exactly the terse-but-useless reply the
audience rule exists to stop. The brevity grader is now a judgment on
unnecessary content — the reply must carry the cause and nothing else, with no
fix offer, no test proposal, no tour of the code, no recap. It keeps weight 2,
and the correctness grader beneath it stays at weight 1. The two judgments are
kept separate, and each rubric says so: a verbose-but-correct reply fails
brevity alone; a terse reply that names no cause fails correctness alone;
neither grader compensates for the other, and the pass gate needs both.

Both graders are `agent_judge` — the port `docs/notes/0014-the-judge-runs-on-
the-subscription.md` decided for every new judge in this suite, applied when
the rubrics were rewritten — because the reply is the only artifact the case
produces and nothing in `coder_eval` matches the final message deterministically
(see "How the graders ported").

Two cases beside it extend the same rule to its other observable contracts.
`tool-heavy-stays-lean` makes the agent earn the answer through a multi-file
lookup and grades the whole transcript — play-by-play progress narration and a
recap after the answer are what it fails, because progress messages are
human-facing text under the audience rule. `explanation-request-answered` asks
to be walked through the same bug and fails the shrug: the explanation must
arrive complete, mechanism and corrected expression, because concision must
not reward silence, vague answers, or omitted required action.

Beyond the constitution suite, `pr-body/08-body-concise-not-repetitive`
grades a drafted PR body: every required fact present, each said once, the
skill's required structure surviving the compression. The new
`issue-body/01-human-summary-agent-detail` grades the two audiences
separately — a terse human-facing opening and `Summary`, and an agent-facing
`Detail` that retains every stated contract, edge case, and verification
condition. Neither suite asserts skill triggering; `02-thin-body.yaml` keeps
that question where it belongs.

One thing both rubrics have to know, and a naive one would not:
`include_agent_output` does not hand a judge the reply. It hands over
`format_messages`' whole-turn transcript — `[ASSISTANT]` starting each block of
thinking aloud, and a terminal `[RESULT - …]` repeating the answer, so the
answer appears twice. Read whole, that transcript counts narration, and counts
it *against* the arm that stopped to obey a rule; graded whole, it lets an agent
that worked the answer out aloud and then did not say it pass the correctness
floor. So both rubrics locate the reply at the last `[RESULT - …]` tag first
and read nothing above it — and nothing below it either, since
`_render_user_message` appends the harness's own closing instruction straight
after the block with no delimiter.

Measured against the pinned harness rather than assumed, because the tags are
not all there: `format_messages` has a `[TOOL USE]` branch that never fires,
duck-typing on a `msg.type` the SDK's `StreamEvent` does not carry. That is the
kind of thing pinning `CODER_EVAL_VERSION` holds still.

There is deliberately **no fallback** when the `[RESULT - …]` anchor is
missing. Counting the last `[ASSISTANT]` block instead would turn a drifted
harness into a plausible number, and the SDK ends every turn with a
`ResultMessage`, so a missing tag means the format moved rather than that the
turn had no reply. Both rubrics write `ANCHOR: none` and score 0.0 there,
failing the case identically in both arms. A drifted harness has measured
nothing, and a case that says so is worth more than one that reports a figure.

Its weakness moved with the rewrite. A line count was crude but reproducible;
the judgment is faithful to the rule but is a model's call, so
`per_replicate_scores` are the thing to read and a disagreement between
replicates is a finding about the rubric, not noise to average away. The
calibration pair every rubric here carries — a verbose-but-correct example
that must fail, a short-but-incomplete one that must fail the *other* grader —
is what keeps the two judgments from collapsing into one opinion.

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

**Measured, so the size of the risk is on the page rather than assumed.** Three
live `review` dispatches (CLI 2.1.263, `coder_eval` 0.11.6, `claude-opus-5`,
2026-09-07 — the three-agent panel over a 1,397-line diff) serialised to 1,437 /
1,382 / 1,387 characters with `subagent_type` as the **first** key, comfortably
inside the window: `review` hands its agents a summary and a file list, not the
diff. So the truncation does not bite this skill today, and an earlier reading of
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

The same suites, the same plugin, three model families. Each model has one
experiment file and the two variants every criterion must score: `bare` loads
no plugin and `with-plugin` installs daily-driver. The delta is the signal.
`docs/notes/0013-the-omp-arm.md` records the adapter decision; this section
records the model set.

```sh
make evals-run-omp                            # every configured Omp model
make evals-run-omp-glm-5-3                    # GLM 5.3 only
make evals-run-omp-deepseek-v4-pro            # DeepSeek v4 Pro only
make evals-run-omp-gpt-5-6-sol                # GPT 5.6 Sol only
make evals-run-omp-glm-5-3 TASKS='tasks/pr/*.yaml'
```

The Omp home the agent borrows configures each of these provider/model IDs:

| Experiment | Model |
| --- | --- |
| `omp-glm-5.3.yaml` | `zai/glm-5.3` |
| `omp-deepseek-v4-pro.yaml` | `deepseek/deepseek-v4-pro` |
| `omp-gpt-5.6-sol.yaml` | `openai-codex/gpt-5.6-sol` |

It needs `omp` on PATH and a model configured in the caller's own
`~/.omp/agent/`. The agent borrows that directory by symlink into a throwaway
Omp home and writes nothing back into it.

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
| `undertake` | `09-session-fields-for-claim` | `09-claim-carries-the-session-id-omp` |
| `task-worktree` | `01-isolate-new-task` | `01-isolate-new-task-omp` |

Each Omp row names its sibling with a `forks:<task_id>` tag, which is what
`check-eval-arms` pairs. The seven `review-depth` rows remain `claude-only`
because they drive Claude's settings and dispatch hook.

**`plan` does not fail on a broken arm.** With no plugin installed,
`coder-eval plan` prints a resolution failure and exits 0. `make evals-plan`
runs `scripts/evals-variants.py` first, so every variant in every model file
must resolve before a paid run begins.

**Two Omp limitations remain.** `allowed_tools` and `disallowed_tools` are not
enforced in Omp RPC mode, and token accounting is best-effort. The adapter
records the evidence it has in each run's `environment_info`.

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
`PreToolUse` on the `Agent` tool, and no constitution in the session. All four
rows would score 0 for a reason that has nothing to do with the constitution. #181
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
