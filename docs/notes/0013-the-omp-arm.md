# The Omp arm

**Status:** decided, 2026-09-11.
**Provenance:** the spike in
[#153](https://github.com/jmcvetta/daily-driver/issues/153#issuecomment-5635896243)
established that the harness can take the arm; this note records the decisions
taken while building it, in
[#173](https://github.com/jmcvetta/daily-driver/issues/173).
**Extends:** [`0011`](0011-two-harnesses-one-skill-tree.md), which made the
skills portable to Omp, and [`0002`](0002-eval-harness.md), which chose the
harness.

`0011` made every skill portable to Omp. The only proof was a live manual
scenario per skill: the evals prove skill triggering on Claude Code and said
nothing about the second harness, so a trigger that stopped firing on Omp read
exactly like a skill that never fires. This arm is the measurement.

## Decided

**The agent kind is a `coder_eval` plugin, and it lives in this repository.**
`coder_eval` 0.11.6 ships five agent kinds, `omp` is not one of them, and it
ships a bring-your-own-agent seam: an entry point in the `coder_eval.plugins`
group whose target is a `register(registry)` callable. `coder_eval` registers
its own built-ins through that same group, so the seam cannot silently rot.
The package is `evals/coder-eval-omp/`, and `make evals-install` installs it
beside the pinned harness with `uv tool install --with`.

*Rejected: its own repository.* It is a test instrument for these suites, it is
never published, and a second repository would be a second thing to keep in
step with a `CODER_EVAL_VERSION` that lives here.

**`omp --mode rpc`, not `omp -p`.** `-p` answers one prompt and exits, with no
machine-readable tool-call events. Ninety-five of the criteria under
`evals/tasks/` read tool telemetry, so `-p` is a smoke check rather than an
arm. RPC mode carries the frames the contract needs and holds the session open,
so the agent starts one process per task and writes one `prompt` command per
turn — where `coder_eval`'s OpenCode agent, the template, invokes its CLI once
per turn and replays a session id.

**The plugin root is installed, not mapped as a skills directory.** `0011` puts
the constitution in `rules/*.md` behind Omp's rule provider and the session
tools in `extensions/daily-driver.js`, and Omp reads both from an *installed*
plugin's manifest. `scripts/check-omp-plugin.py` measured that split: the
`--plugin-dir` route finds the skills and never loads the extension, and only
the install route loads both. A skills-only mapping — all the OpenCode agent
does — would leave the constitution out of the treated arm, and
`tasks/constitution/*` would score 0 for a reason that has nothing to do with
the constitution. So the agent runs `omp plugin link` into a throwaway Omp
home built beside the task.

*The spike said `--extension` / `-e`.* That was not carried forward: this
repository's own measurement says the extension comes from an installed
manifest, and `omp plugin link` is the route it measured.

**The throwaway home borrows the real one's providers.** Every file in
`~/.omp/agent/` is symlinked into it, except the config the agent writes, which
carries Omp's defaults plus skill commands. A run needs a model, and the
provider configuration is where it lives; the laptop's own installed plugins
and settings stay out, which is the isolation `coder_eval`'s Claude agent gets
from `setting_sources: []`. Nothing is written into the real home.

**Three normalisations at the agent boundary, each one a silent zero if it is
missing.**

`skill_triggered` detects a skill by the substring `skills/<name>/` in a tool
parameter or by a canonical `Skill` call. Omp engages a skill by reading the
URL `skill://<name>`, which is neither, so every positive row in the arm would
score 0 — indistinguishable from a plugin that never loaded. The agent maps
that read to `Skill` with `parameters={"skill": name}`, exactly as the OpenCode
agent maps OpenCode's own skill tool, and carries `bash` → `Bash` and
`task` → `Agent` for the `command_executed` rows.

Every `llm_judge` rubric under `evals/tasks/` locates the reply at the last
`[RESULT - …]` tag and scores 0.0 where there is none — deliberately, and with
no fallback, so a drifted harness reports nothing rather than something
plausible. `coder_eval` builds that tagged transcript for its Claude agent
alone; its OpenCode and Codex agents hand the judge bare text. An arm that did
the same would score every judged row 0.0 in both arms, which is most of the
`references` suites. So the agent renders the tagged shape itself. This was not
in the spike's list, and it is the finding that would have voided the arm's
first run.

**The forked rows are routed by tag, in two runs.** Ten rows cannot be graded
identically on both harnesses. A `coder_eval` variant applies to every task in
the run, so one invocation carrying both sets would grade Omp's routes under a
Claude arm and pay for it. Each of the ten is therefore two files: the Claude
one tagged `claude-only`, the Omp one tagged `omp-only`, with `-omp` on the
`task_id`. `make evals-run` excludes `omp-only`; `make evals-run-omp` excludes
`claude-only`. Each Omp row names its sibling with a `forks:<task_id>` tag —
`coder_eval` accepts a namespaced tag, so the pairing needs no field of its own
— and `scripts/check-eval-arms.py` pairs them by it in `make check`. Inferring
the pair from the filename would not work: seven of the ten counterparts are
deliberately not the sibling's stem plus `-omp`, because that stem names
Claude's route and on Omp the row grades the opposite.

**`review-depth` is Claude-only, with no counterpart.** Its seven rows pin
`agent.type: claude-code` and drive Claude's own settings and its dispatch
hook, so they have no Omp form. Measured while building this: `coder-eval plan`
resolved them under the Omp experiment as `Variant 'omp': claude-code`, which
would have run seven Claude sessions inside the Omp arm and reported them as
Omp results. They carry `claude-only`, and `check-eval-arms` now fails any task
that pins an agent kind its arm tag does not match.

*The issue said eleven rows in three groups; there are ten.* Seven grade a
route that is renamed on Omp, three grade a rule that `0011` makes Claude Code
only. The spike's own list named three in that second group while calling it
four.

**One Omp variant, and no bare-Omp control.** `evals/README.md`'s rule is that
every criterion is scored in both arms, because a fire row's delta is the whole
signal. This arm has no delta of its own: it reports the treated Omp arm alone.
The control the issue chose instead is within the arm — a positive row and a
negative row in one run, which together say whether the plugin loaded and
whether the skill normalisation works. A bare-Omp variant doubles what the arm
costs per run, and it is the obvious addition the day the delta is what someone
is reading.

**`plan` cannot guard the arm, so a guard runs in front of it.** Measured: with
`agent: {type: omp}` and no plugin installed, `coder-eval plan` printed
`Variant 'omp': resolution failed - No agent registered for type 'omp'`, then
`All tasks are valid!`, and exited 0. `scripts/evals-variants.py` asks the
installed `coder_eval` which kinds it has — under the interpreter
`coder-eval`'s own shebang names, the way `evals-preflight.py` asks about the
judge transport — and `make evals-plan` depends on it.

## Known limits, recorded rather than fixed

**`allowed_tools` and `disallowed_tools` are not enforced in this arm.** Omp's
RPC mode has no per-session tool allowlist. The trigger rows use
`disallowed_tools` to stop a denied read of `skills/<name>/SKILL.md` scoring as
an engagement, so a no-fire row is weaker on Omp than on Claude Code. The agent
warns once per task rather than letting a row believe it constrained anything.

**Two protocol questions are open, and the arm answers them by running.** Omp's
`docs/rpc.md` shows `toolName` on `tool_execution_start` without showing the
arguments, and places token accounting in "telemetry fields on `agent_end`"
without naming them. The adapter reads every plausible spelling and records the
one that answered, in `omp_argument_keys_seen` and `omp_usage_keys_seen` on the
run's `environment_info`. Until a live run names them, `require_token_telemetry`
defaults to false — the opposite of the OpenCode agent's default — because a
missing count is a gap in this adapter rather than proof of a broken turn.

**The arm has not been run.** Nothing here has touched a live `omp` binary, and
no paid run has happened. What is measured is:

- `make evals-install` installs the agent kind, and `make evals-plan` resolves
  `Variant 'omp': omp` on every task it applies to, with no resolution failure
  and exit 0 — the issue's first acceptance criterion.
- `make check` proves the frame reduction maps skills, tools, text and usage
  the way the criteria read them (`scripts/check-omp-agent.py`), and that the
  two arms' task sets stay in step (`scripts/check-eval-arms.py`).

The second acceptance criterion — one paid run of a narrow slice, non-zero on a
positive row and zero on a negative one — is the next thing to do. It needs
`omp` on PATH and a provider configured, which this session had neither of.
