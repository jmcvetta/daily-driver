<!-- step-names: external phase — the numbered phases named below are issue
     #35's, and are named there rather than here. -->

# The eval harness: `coder_eval`, not `claude plugin eval`

**Status:** decided, 2026-09-07; ported, 2026-09-07.
**Provenance:** chosen by an agent in
[#36](https://github.com/jmcvetta/daily-driver/pull/36), which recorded the choice
without acting on it; the port it calls for landed separately in
[#38](https://github.com/jmcvetta/daily-driver/pull/38), citing this file as already
settled. Ratified by those merges, not by a separate call from the author.
**Supersedes:** the harness assumptions in
[`0001`](0001-built-in-review-surface.md) and in `evals/README.md`, both of
which take `claude plugin eval` as given.

> **Read ["Corrected by the port"](#corrected-by-the-port) first.** Three claims
> below about what `coder_eval` can and cannot do are wrong — two about
> `command_executed` and `skill_triggered`, one about what a sandbox can be
> given — and the corrections changed how much of the old suite had to be
> redesigned. They are left in place rather than edited away: the decision was
> made on them, and what a decision was made on is the thing a decision record
> is for.

`evals/` currently holds four suites written for `claude plugin eval`
(`pr`, `pr-title`, `pr-body`, `constitution-reaches-subagent`). **None of them
can have been run on this account** — the command is early access and is not
enabled here. (Whether they ever ran elsewhere is unknown; this is an inference
from present unavailability, not a history.)

```
$ claude plugin eval . --tag review-depth --runs 1
`plugin eval` is currently in early access
```

That is the whole reason this decision came up. A test suite nobody can execute
is a design document, not a test suite — so the format was never really chosen,
it was inherited from whatever the CLI happened to offer.

## Why not `claude plugin eval`

Not because it is bad. Its embedded authoring doctrine (the ~190-line
`plugin eval init` interview prompt inside the binary) is the best writing on
eval design found anywhere during this investigation, and §"Harness findings"
of [`0001`](0001-built-in-review-surface.md) records its schema because nothing
else does. The problems are
structural:

1. **It cannot be run here.** Early access, per-organisation. Every eval in this
   repository is currently unexecutable.
2. **It is publicly undocumented.** Verified: `eval` appears nowhere in the docs
   index at `code.claude.com/docs/llms.txt`, nor on the plugins or
   plugins-reference pages, while the `plugin.json` key `experimental.evals` is
   implemented and validated in the binary and omitted from the reference page
   documenting its siblings `themes` and `monitors`. *That the omission is
   deliberate is an inference from the asymmetry, not something established.*
3. **Its changes are not announced.** Verified: the public changelog is 6,362
   lines and reaches 2.1.263; occurrences of `plugin eval`, `ablation`,
   `grader`, `judge-model` and `case.yaml` are **zero**. *That the surface
   changed during that window is inferred from its shape, not from a diff of
   past binaries — but the absence of any entry is the point either way: there
   is nothing to read.*
4. **It has already churned once.** The binary still carries a dead earlier eval
   format — `should_trigger` frontmatter, status string
   `trigger tests pending model integration` — pointed at the same `evals/`
   directory the current format uses.
5. **It cannot be pinned.** This is the decisive one. It ships inside the
   `claude` binary, so it changes when the CLI updates. There is no version to
   hold back and, per (3), nothing to read when the semantics move. For a suite
   that may later gate merges, that is the wrong shape of dependency.

`coder_eval` is Apache-2.0 on PyPI. It changes when we say so.

## What was actually verified

`coder_eval` 0.11.6 was installed (`uv tool install --python 3.13 coder-eval`)
and run against this plugin — two arms, two repeats, one task asserting the
`review` skill activates.

The ablation isolates the plugin correctly:

| | `bare` rep 00 / 01 | `with-plugin` rep 00 / 01 |
| --- | --- | --- |
| refers to the constitution² | no / no | **yes** / no¹ |
| names the `review` skill | no / no | **yes** / no¹ |
| cost, USD | 0.2171 / 0.0574 | 0.0927 / 0.0942 |

¹ Replicate 01 paraphrases the constitution's content ("code without tests is
broken") under "per the project standards" without naming it or the skill. So
the plugin signal is 1-of-2, not 2-of-2 — real, but n=2 supports no rate.

² "Refers to", not cites: no replicate names the path `rules/constitution.md`.
`with-plugin/00` says "Per the constitution, …", which is what the **yes**
records.

**The cost column supports nothing.** `bare/00`'s $0.2171 is a cold-cache
outlier (45,790 cache-creation tokens against 4,011 in `bare/01`); the arms are
not separable on two replicates. It is recorded here only so the raw numbers
are on the page.

The task itself was badly designed — a `tempdir` sandbox with no git repository,
so `review` correctly declined to fire ("there's no branch, no commit history,
nothing for the `review` skill to diff against") and `skill_triggered` scored
0.00 in both arms. A true negative from a bad case. What it establishes is that
a local plugin loads, the constitution reaches the session, and the criterion
reports honestly.

Capabilities confirmed by running it, which `claude plugin eval` does not have:

- **`coder-eval plan`** validates a suite for **zero tokens** — it checked the
  CLI was present and resolved the variants before any model call. The built-in
  has no dry run; config errors cost a paid run to discover. (The
  `task_timeout` / `turn_timeout` warning quoted in early notes comes from
  `coder_eval`'s own defaults and was observed during `run`, not `plan`.)
- **Cost and token accounting per replicate**, in USD, plus per-tool command
  stats and timings.
- **Preserved sandboxes** and `task.json` / `task.html` per replicate.
- **14 criterion types** against the built-in's 6 — the tool's own log says
  "Validated 15 criterion checkers", so treat the count as ~14–15 — including
  `skill_triggered` (which detects the `Skill` tool call, and is what 24 of the
  27 existing graders here need), `command_executed` for shell-command
  assertions,
  `agent_judge`, and an
  `llm_judge` that returns a *score* under a model of your choosing rather than
  a one-word verdict from a fixed small judge.
- **`stop_early: {decide_within: N}`** — first-class cost control, in place of
  the trick of withholding tools to cut a run short.
- **Per-criterion `weight` and `pass_threshold`.**
- **`repeats` overridable per arm**, with `per_replicate_scores` reported so
  variance is visible rather than hidden behind a pass/fail. (The default is 1,
  not 5 — set it explicitly. This run set `repeats: 2`, which is why the table
  above cannot carry a conclusion.)

## What this costs

The four existing suites must be ported. The expensive content — the prompts,
the fire/no-fire labels, the reasoning in `evals/README.md` about why negative
cases are what make the result mean anything — is portable; only syntax is
locked in for most of them. **`tool_used` on `Skill` maps to `skill_triggered`,
not to `command_executed`** — 24 of the 27 graders under `evals/` are that
shape, and `command_executed` matches shell commands off command telemetry, so
it cannot see a `Skill` call at all. The `arm: both` semantics map to
`variants`, and `file_exists` has a direct equivalent. Estimate for those 24:
about a day.

**The other three graders have no mechanical target, and they are all in
`constitution-reaches-subagent`.** Two assert on the `Agent` tool
(`a-subagent-actually-ran`, and `the-parent-did-not-supply-the-token`, which is
a negative control — `input_match` with `max: 0`). `coder_eval` has no generic
tool-call criterion; `skill_triggered` counts only `Skill` invocations, so
neither ports. The third, `subagent-reports-the-token`, is `regex` against
`last_message`, and nothing in `coder_eval` matches the agent's final message
deterministically — `file_matches_regex` needs a path and reads file content,
and only `llm_judge`/`agent_judge` see the final message, as a scored judgment
rather than a match.

That suite therefore needs **redesigning, not porting**: have the subagent write
the token to a file and assert with `file_matches_regex`, or accept a judged
criterion and lose determinism. It is the suite testing the newest feature, and
its weight-2 grader is the actual finding, so budget for it separately.

A second capability is lost beyond the generic tool-call assertion above:
`claude plugin eval`'s MCP mocking, with `expect:` frontmatter that aborts a run
on a wrong argument. Nothing in `coder_eval`
matches it. No current suite uses it, so this is a cost deferred rather than
paid — but it is the thing to re-examine if a suite ever needs to assert
*"filed the ticket in the wrong project."*

## Risks accepted

`coder_eval` is small: 122 stars, 3 forks, one backing organisation, adoption
outside UiPath unverified. It is Apache-2.0 and pinnable, which is the point —
a fragile dependency you control beats a fragile dependency that updates itself.
Its defaults also need overriding: `plan` reported a default agent model of
`claude-sonnet-4-6`, so `agent.model` was pinned explicitly for the runs above
and every preserved replicate records `claude-sonnet-5`.

**Two default behaviours worth accepting deliberately rather than discovering:**

- **Usage telemetry is on by default**, to a UiPath-controlled Application
  Insights endpoint (`westus2-2.in.applicationinsights.azure.com`), via an
  ingestion-only connection string base64-embedded in the package so "a fresh
  install reports usage telemetry … with no configuration". The code documents
  it as ingestion-only and security-approved, and the base64 is explicitly *not*
  for secrecy. Still: a tool proposed as a possible merge gate phones home
  unless told not to. Set the connection string explicitly, or disable it, and
  decide that on purpose.
- **`load_dotenv(override=True)`** — a `.env` file wins over the shell
  environment, including `ANTHROPIC_API_KEY`. Surprising if a stale `.env` is
  lying around.

Outbound calls also drew proxy 403s during this session's runs; runs completed
regardless. The 403 lines are not in the retained `experiment.log`, so treat
that as reported-not-preserved.

## Consequences

- The `review-depth` routing suite drafted for issue #35 phase 2 is **not
  shipped**. It was written for the abandoned format, and separately it graded
  the skill's announced mode line rather than which agents were dispatched —
  grading the self-report instead of the outcome. It is rebuilt in `coder_eval`,
  against dispatch, in its own change.
- The four existing suites and `evals/README.md` keep describing
  `claude plugin eval` until they are ported. They do not work today either way.
- CI gating stays out of scope for now, but is no longer foreclosed: it was only
  ever blocked by CI having no credentials, which is a separate decision from
  which harness runs the cases.


## Corrected by the port

The port (issue #37) contradicted this page three times. All three corrections
are in `coder_eval` 0.11.6, read off the source rather than inferred from the
docs.

**`command_executed` is the generic tool-call criterion.** This page says it
"matches shell commands off command telemetry, so it cannot see a `Skill` call
at all", and concludes that `tool_used` on `Agent` has no equivalent. It filters
on `tool_name` for **any** tool and, off `Bash`, matches `command_pattern`
against the JSON-serialised tool parameters; the Claude Code adapter records one
telemetry row per `tool_use` block, `Agent` included. So `tool_used` on `Agent` —
`input_match` and all — ports directly, and the constitution suite lost **one**
grader to redesign, not three. Nor is the `Skill` tool an exception to "any
tool": `command_executed` filters on `tool_name: Skill` like any other.

**`skill_triggered` is not `Skill`-only.** This page describes it as counting
`Skill` invocations. It also scans every string parameter of every tool for the
substring `skills/<name>/`, so a `Read` of `skills/pr/SKILL.md` scores as
engaging `pr` — and scores whether or not the read succeeded, because telemetry
records a `tool_use` block when it is generated, before any result. What
survives is narrower than "reads the `Skill` tool": `skill_triggered` is the
only **skill-aware** criterion, the only one that treats a `Skill` call or a
`skills/<name>/` path as engaging a *named skill*. `command_executed` can match
a `Skill` call like any other; what it cannot do is know what a skill is.

The consequence is a build rule, not a curiosity. A row expecting a named skill
NOT to fire, and holding file tools, can be failed by a path it never read
successfully — so the trigger-accuracy suites remove those tools with
`disallowed_tools`, which is the field that actually removes one
(`allowed_tools` is a permission allowlist and leaves them offered). Where a row
needs the file tools, as `review-depth`'s no-fire case does, the answer is a
second criterion that does not depend on paths in tool parameters at all:
there, an empty dispatch roster.

The `command_executed` correction is also what makes the rebuilt `review-depth`
suite possible on this harness: a criterion matching `"subagent_type": "security-reviewer"` inside
an `Agent` call grades the dispatch itself, which is precisely the thing the
dropped draft failed to grade.

That last sentence is how it was planned and not how it shipped, for a reason
worth recording. `command_executed` matches against
`json.dumps(parameters)[:2000]`, and the `Agent` tool's schema orders its keys
`description, prompt, subagent_type` — so on any diff of consequence the
`prompt` pushes `subagent_type` past the window, and the criterion reports "not
dispatched" for a dispatch that happened. `llm_judge` and `agent_judge` cannot
see it either: their tool-call summariser renders an `Agent` call as its
`description`, a three-word label the model writes. **`subagent_type` is not
observable through any criterion in 0.11.6.** The suite therefore takes the
observation with a `PreToolUse` hook wired through the task's
`claude_settings` — instrument, not plugin — which sees the tool input verbatim
and writes a roster a `file_matches_regex` criterion reads. The fix upstream
would be to make that truncation bound configurable, or to render
`subagent_type` in the judge summary.

**A sandbox can be given a git repository.** This page records a `tempdir` with
no repository as the reason the verification task scored 0 in both arms, and
issue #37 carries the shape of the repository as its main unknown.
`TaskDefinition.pre_run` answers it: a shell command run inside the sandbox
after setup and before the agent, which aborts the evaluation on a non-zero
exit. `git init`, a bare `origin` on local disk, a base branch and a pushed
topic branch are all reachable from there, and a fixture that fails to build
stops the run instead of scoring a misleading 0.

**Unchanged:** `regex` on `last_message` still has no deterministic equivalent,
and that is what forced the one genuine redesign — the subagent now writes its
answer to a file, read by `file_matches_regex`.
