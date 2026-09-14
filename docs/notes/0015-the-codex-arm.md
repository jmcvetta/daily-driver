# The Codex arm

**Status:** decided, 2026-09-12.
**Provenance:** the spike in
[#181](https://github.com/jmcvetta/daily-driver/issues/181#issuecomment-5646398831)
measured what this plugin loads under a real `codex` binary; this note records
the decisions taken while building the arm, in
[#185](https://github.com/jmcvetta/daily-driver/issues/185).
**Extends:** [`0013`](0013-the-omp-arm.md), which built the second arm and set
the shape this one follows, and [`0011`](0011-two-harnesses-one-skill-tree.md),
which made the skills portable in the first place.

`0013` said it for Omp and it is true again for Codex: a trigger that stops
firing on a harness reads exactly like a skill that never fires. The Claude and
Omp arms say nothing about the third harness. This arm is the measurement.

It is a much smaller piece of work than `0013` was, and the reason is the whole
first decision below.

## Decided

**The agent kind is a subclass of a built-in, not a new driver.** `coder_eval`
0.11.6 ships a `codex` kind that drives the Codex SDK, links a `plugins:` root's
skills into `<cwd>/.agents/skills/`, and records command telemetry in the
vocabulary the criteria are written in. Every bit of that is inherited.
`evals/coder-eval-codex/` adds two overrides and a record, through the same
`coder_eval.plugins` entry-point seam `coder-eval-omp` uses.

*Rejected: registering as `codex` itself.* The registry refuses two
implementations claiming one kind, so this would have to replace the built-in
rather than sit beside it — changing what `codex` means for every other
`coder_eval` user in the same environment. The distinct kind also makes the
routing readable: `scripts/check-eval-arms.py` maps a pinned `agent.type` to the
arm tag it must carry, and `codex-daily-driver` names exactly one arm.

**Two corrections, where the Omp arm needed three.** The first is the
`[RESULT - …]` transcript. `coder_eval` builds it for its Claude Code agent
alone and hands the judge `result_text` — the turn's assistant deltas joined —
from its Codex agent.
Every rubric under `evals/tasks/` locates the reply at the last `[RESULT - …]`
tag and scores 0.0 where there is none, deliberately and with no fallback, so an
arm that shipped without this would score every judged row 0.0: most of the
`references` suites, and both halves of the constitution suite had they been in
this arm at all. `coder_eval_codex/transcript.py` renders the shape, and
`scripts/check-codex-agent.py` asserts it is byte-identical to
`coder_eval_omp.rpc.render_agent_output` for one block — the two packages render
one contract and neither depends on the other, so that equality is what holds
them in step.

Tool names need no renaming: the built-in already records `commandExecution` as
`Bash` with `parameters["command"]`, which is what `command_executed` reads.

**The second is the plugin root, and it was found in review rather than
designed.** `CodexAgent._setup_skills` links each skill with
`target.symlink_to(skill_dir)`, where `skill_dir` is built from
`config.plugins[].path` exactly as written. Every experiment here writes
`path: ".."`, relative to the `evals/` directory the run targets `cd` into,
which is right for the Claude agent — `coder_eval` resolves plugin paths before
that agent is built — and wrong for the Codex one, which never reaches that
resolution.

Measured against this repository's real layout, with the experiment's own
`path: ".."` and the working directory the Makefile uses: fourteen links are
created, every body is relative, `.agents/skills/pr -> ../skills/pr` resolves
back to the link's own directory, and **not one of the fourteen has a readable
`SKILL.md`**. The treated arm would have run with no skills at all, scored 0 on
every trigger row, and cost a full `repeats: 5` sweep to say so — the silent
zero this arm exists to prevent, arriving through the arm itself.

`_setup_skills` does warn when it links nothing, and the warning does not fire
here: it counts `iterdir()` entries, and fourteen broken links are fourteen
entries. So two things changed rather than one.
`plugins.resolve_local_plugins` makes the root absolute before `start()`
delegates, and `start()` **raises** where it previously warned — an arm that
declared plugins and has no readable skill runs untreated, which is the same
judgement `coder_eval_omp`'s `_link_plugins` already makes for the same reason.

The experiments keep `path: ".."`. Making them absolute would have fixed this
one file and left the next experiment to rediscover it, and the paths are
relative in the other two arms on purpose.

**Neither correction is the one #185 asked for, and the issue was written
against a reading #181 corrected.** #185 says Codex engages a skill
through `skill://<name>`, the spelling Omp uses, which `skill_triggered` cannot
see. Both halves of that turn out to be wrong.

- #181 drove a real `codex-cli 0.154.0` and found the model is handed a skills
  table in a developer message and opens `SKILL.md` with an ordinary shell call.
  A prompt of `skill://daily-driver:pr` reached the model as that literal text,
  unexpanded.
- `coder_eval`'s `skill_triggered` already detects the read Codex actually does.
  Its regex matches `skills/<name>/` in any string tool parameter, and its own
  docstring names Codex as the agent that branch exists for. The Codex SDK types
  `CommandExecutionThreadItem.command` as `str`;
  `CodexAgent._extract_command_telemetry` puts that string in
  `parameters["command"]`; and `_setup_skills` links each skill at
  `.agents/skills/<name>/`. The substring is there to match.

Measured here rather than reasoned about: running the built-in's own
`_setup_skills` against this repository as the plugin root links all fourteen
skills, named bare — `pr`, `undertake`, `review-cycle` — which is the spelling
every row's `skill_name` already uses.

Adding a mapping would have renamed something already named, and it would have
been untestable: there would be nothing for `check-codex-agent` to drive. What
that leg drives instead is the two corrections above — including the
self-referential symlink itself, built in a temporary directory, so the
assertion is the failure rather than a description of it.

**Three arms, routed by tag, in three runs.** `0013`'s reasoning holds and the
mechanism generalises: a `coder_eval` variant applies to every task in the run,
so one invocation carrying more than one arm's rows grades one harness's routes
under another's and pays for it. `make evals-run` excludes `omp-only` and
`codex-only`; `make evals-run-omp` excludes `claude-only` and `codex-only`;
`make evals-run-codex` excludes both of the others. A `codex-only` row will name
its sibling with a `forks:<task_id>` tag, and `scripts/check-eval-arms.py` pairs
them.

*`--exclude-tags` takes ONE comma-separated value.* It is a single `str` option
that `coder_eval` splits on commas, so a second `--exclude-tags` on the same
command line replaces the first rather than adding to it. A target written the
obvious way would read correct, exclude one tag, and run the other arms' forks
at full price. `check-eval-arms` now reads the Makefile and asserts each target
passes the flag exactly once, with exactly the right set.

*An experiment must name its own arm's agent kind.* `codex.yaml` set to the
BUILT-IN `codex` passes every other guard in the repository — it is a registered
kind, so `evals-variants.py` resolves it and says so, and that script's own
docstring admits it cannot catch this — and then scores 0.0 on every judged row
of a paid run. `check-eval-arms` reads each experiment's variants against the
arm table, which is the experiment side of the same cross-check it does on the
Makefile.

**`skip:<arm>` is a new tag, because an arm tag cannot say "two of three".** An
arm tag claims exactly one arm and every arm is spelled by carrying none. A row
that runs in the Claude and Omp arms but not the Codex one has no third thing to
say, and the routing is exclusion-based, so the honest primitive is an
exclusion. `skip:codex` takes a row out of that arm and leaves it in the rest.
`check-eval-arms` asserts it names a known arm, is never combined with an arm
tag, and never takes a row out of every arm.

**`tasks/constitution/*` carries `skip:codex`, and that is the arm's biggest
hole.** `coder_eval`'s Codex agent symlinks skills and installs nothing else —
no `hooks/hooks.json`, so no `SessionStart` and no `PreToolUse` on the `Agent`
tool. The constitution never reaches the session. `reaches-subagent` measures
whether the text arrives and `reply-is-concise` measures whether it lands; both
would score 0 for a reason that has nothing to do with the constitution, which
is the exact failure `0013` built the Omp arm's `omp plugin link` to avoid.

The Omp arm's fix does not transfer. #181 measured that a real Codex session
does load `hooks/hooks.json` and does deliver the constitution as a developer
message — behind two gates it also measured: persisted **hook trust**, whose
documented escape hatch is `codex exec --dangerously-bypass-hook-trust`, and an
exactly-echoed `hookEventName`. `coder_eval` drives the Codex SDK and the
app-server, not `codex exec`, and whether the app-server honours a trust bypass
is not something this session could measure: it has no OpenAI credentials and no
`codex` binary. Building an install path on a guess about that is the
workaround the constitution forbids. So the rows are tagged out, the reason is
written on each of them, and lifting it needs a live Codex session to measure
against — which is the same thing the arm's first paid run needs.

**`review-depth` stays Claude Code only, and the third arm is why that tag
earns its keep again.** Measured: `coder-eval plan -e experiments/codex.yaml`
resolves those rows as `Variant 'codex': claude-code (gpt-5-codex)` — seven
Claude sessions inside the Codex arm, billed to it and reported as it. That is
what `0013` measured for Omp, reproduced for Codex, and it is what the
`claude-only` tag prevents.

**One Codex variant, and no bare-Codex control.** `0013`'s decision, unchanged
and for the same reason: the arm reports the treated side alone, the control is
a positive row and a negative row in one run, and a second variant doubles what
the arm costs. It is the obvious addition the day the delta is what someone is
reading.

**Ten `codex-only` rows.** Every forked row grades a route stated in a
`skills/<name>/references/*.md`, so a Codex counterpart needs a
`references/codex.md` to grade against. [#184](https://github.com/jmcvetta/daily-driver/issues/184)
wrote three of those and [#183](https://github.com/jmcvetta/daily-driver/issues/183)
the rest, both while this work was in review, so the set is complete:

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
| `undertake` | `09-session-fields-for-claim` | `09-claim-carries-the-branch-alone-codex` | branch from git, model and session recorded as absent |

None is its sibling's stem plus `-codex`, and that is the same reason `0013`
gives for seven of the Omp counterparts: the sibling's stem states Claude's
route, and on Codex the row grades the opposite.

**Three of the ten grade the same rule as their Omp counterpart**, and that is
structural rather than lazy. Codex has no GitHub tool of its own, so `pr`,
`pr-title` and `deps` resolve to the same `gh` calls Omp uses. Each still needs
a file of its own: the arms are routed by exclusion and an arm tag claims
exactly one arm, so a row cannot sit in two. Without the duplicate the Codex arm
would not measure the route at all, which is the silent gap the arm exists to
close. Each of the three says so in its own header.

**`pr-body` is the one `gh` row where the arms genuinely disagree.** Codex's
reference file prescribes `gh pr edit --body-file`; Omp's names `--body`, and
says in its own words that the hazard is `gh`'s rather than Codex's. So the
Codex row is the only one of the three arms grading the spelling that survives a
body full of backticks.

**Two of the ten grade a *stop* rather than a call**, which is new. Codex is the
first harness where the right answer to "title this session" is that the
`agent_tasks` namespace is not offered in an unattended run, and the right
answer to "wait for CI" is that nothing here can wait.

*The scope of this was put to the user twice rather than decided here*, because
picking between a coherent set later and a partial one now is a question about
the deliverable rather than about craft. The first answer was to write the three
#184 unblocked; #183 then merged, and the rest were written on the same
principle.

## Known limits, recorded rather than fixed

**`allowed_tools` and `disallowed_tools` are not enforced in this arm.** Worse
than Omp's version of the same gap, because it is not a missing feature but a
deliberate one: `CodexAgent._log_config_enforcement` logs both fields and its
own security notice says Codex runs full-access on *every* `permission_mode`,
with `coder_eval`'s per-run sandbox as the only boundary. The trigger rows use
`disallowed_tools` to stop a denied read of `skills/<name>/SKILL.md` scoring as
an engagement, and that mitigation is unavailable here — which bites harder than
on Omp, because on Codex the shell read *is* the engagement signal rather than a
near-miss for one. A no-fire row is therefore weaker in this arm than in the
Claude arms, and a no-fire row that scores badly should be read as that before
it is read as a skill firing when it should not.

`experiments/codex.yaml` therefore sets no `allowed_tools` at all, where the
other two experiments set `[Skill]`. On Codex that list would name a tool that
does not exist and omit the shell the engagement runs through, and it would be
inert either way; writing it would only mislead a reader of the file.

**The model pin is unverified.** `gpt-5-codex`, chosen so a report says which
model produced it and so the arms differ only in the harness. Nothing in this
repository has started a Codex session through the SDK, so that string has not
been resolved against an account. It is the first field to correct.

**Skill discovery is `coder_eval`'s claim, not this repository's
measurement.** That Codex auto-discovers `.agents/skills/` from the working
directory upwards is what the built-in agent's own docstring says, and #181
measured discovery through an *installed plugin* rather than through that
directory. What is measured here is one half: the linker links all fourteen
skills into it. Whether a session then sees them is what the first run answers.

**The arm has not been run.** Nothing here has touched a live Codex session, and
no paid run has happened. What is measured is:

- Both in-repo agent kinds register through the entry-point seam, and
  `coder-eval plan -e experiments/codex.yaml tasks/*/*.yaml` resolves
  `Variant 'codex': codex-daily-driver (gpt-5-codex)` on every task it applies
  to, with no resolution failure and exit 0.
- The built-in's own `_setup_skills`, driven with this repository as the plugin
  root and the working directory the Makefile uses, links all fourteen skills
  with a readable `SKILL.md` — and links fourteen unreadable ones without the
  resolution above.
- `make check` proves the transcript rendering is the shape the rubrics read and
  agrees with the Omp arm's byte for byte (`scripts/check-codex-agent.py`), and
  that the three arms' task sets and the Makefile's routing stay in step
  (`scripts/check-eval-arms.py`).

The next thing to do is one paid run of a narrow slice — non-zero on a positive
row, zero on a negative one, and a judged row scoring on its rubric rather than
on a missing anchor. It needs OpenAI credentials, which this session had none
of. The Omp arm's equivalent run is still outstanding too, and `0013` records
it.
