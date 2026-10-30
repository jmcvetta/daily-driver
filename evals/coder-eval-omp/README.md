# `coder-eval-omp`

An `omp` agent kind for [`coder_eval`](https://github.com/UiPath/coder_eval), so
the suites in [`evals/tasks/`](../tasks) can be run against
[Omp](https://omp.sh) as well as Claude Code. It is a test instrument, not part
of the plugin: nothing here ships to a user, and nothing here is imported by a
skill.

```
coder-eval-omp/
├── fixtures/
│   └── agent_end_usage.json       redacted live Omp 18.4.3 frame
├── pyproject.toml                 the `coder_eval.plugins` entry point
├── prices.json                    hand-maintained USD/Mtok rates — see `Cost`
└── src/coder_eval_omp/
    ├── rpc.py                     the command builder and frame reduction — pure, and tested
    ├── pricing.py                 prices.json lookup — pure, and tested
    ├── home.py                    borrowed provider files and the private routing merge — pure
    ├── agent.py                   the process, the events, and what loaded
    └── plugin.py                  register(registry)
```

## Why it exists

`coder_eval` ships five agent kinds and `omp` is not one of them. It does ship
a bring-your-own-agent seam — an entry point in the `coder_eval.plugins` group
whose target is a `register(registry)` callable — and `coder_eval` registers its
own built-ins through that same group, so the path cannot silently rot.

Three things this adapter must get right, and each one is a silent zero rather
than an error if it does not. A fourth, the row's tool lists, is a boundary
rather than a score.

**A skill engagement must be visible to `skill_triggered`.** That criterion
detects a skill by the substring `skills/<name>/` in a tool parameter, or by a
canonical `Skill` call. Omp engages a skill by reading the URL `skill://<name>`,
which is neither. Left alone, every positive row in the Omp arm scores 0 —
indistinguishable from a plugin that never loaded. `rpc.canonical_tool_call`
maps that read to a `Skill` call, the way `coder_eval`'s own OpenCode agent maps
OpenCode's skill tool.

**The judge must find the reply.** Every `llm_judge` rubric under
`evals/tasks/` locates the reply at the last `[RESULT - …]` tag and scores 0.0
where there is none — deliberately, so a drifted harness reports nothing rather
than something plausible. `coder_eval` builds that tagged transcript for its
Claude agent only; its OpenCode and Codex agents hand the judge bare text.
`rpc.render_agent_output` emits the tagged shape, so one rubric reads the same
on both harnesses.

**The plugin must load whole.** `docs/notes/0011` puts the constitution in
`rules/*.md` behind Omp's rule provider and the session tools in
`extensions/daily-driver.js`. Omp reads both from an *installed* plugin, so a
skills-only mapping would leave the constitution out of the treated arm and
score `tasks/constitution/*` zero for the wrong reason. The agent installs each
`plugins:` root with `omp plugin link`, into a throwaway Omp home built beside
the task — the route `scripts/check-omp-plugin.py` measures as loading the
skills, the extension and the manifest together.

**The throwaway home inherits provider files only.** A run needs a model, so
`models.yml` (custom providers), `agent.db` with its `-wal` and `-shm`
siblings (settings and auth storage) and `secrets.yml` (secrets `models.yml`
can reference) are symlinked from the real `~/.omp/agent/`. Nothing else is:
`mcp.json` would bring a person's MCP servers, which Omp enables whatever
`--tools` says, and `AGENTS.md`, `SYSTEM.md`, `SYSTEM_TEMPLATE.md`,
`PERSONALITY.md` and `RULES.md` would load a person's own instructions into
the bare arm. The list is `coder_eval_omp/home.py`'s `PROVIDER_FILES`.

**A row may restrict the route to one upstream.** `vercel_gateway_only:
[deepseek]` requires `model` to be a `vercel-ai-gateway/<model>` selector, and
`home.restrict_model_upstreams` merges the allowlist into a private
`models.yml` as `providers.vercel-ai-gateway.modelOverrides.<model>.compat.
vercelGatewayRouting.only`. Omp turns that into the request's
`providerOptions.gateway.only`, so an unavailable upstream fails instead of
falling back. The merge preserves every other provider and setting, replaces
rather than unions the selected allowlist, drops the model's `order`
preference, and replaces the borrowed symlink instead of writing through it.
Because Omp's catalog transport for these models (`anthropic-messages`) never
serializes the routing block, a restricted model also selects
`api: openai-completions`, the transport that applies
`providerOptions.gateway`. A malformed file, an empty or invalid allowlist, a
non-Vercel selector, or a model that names a compaction or context-promotion
fallback is refused. The
agent also clears `PI_CONFIG_DIR` and `OMP_PROFILE` for the child: either
would relocate Omp's configuration root away from the throwaway home.

**A row's tool lists must hold.** `tools.select_tools` maps a row's
`allowed_tools` and `disallowed_tools` to Omp's tool names, and the agent
passes the result as `omp --tools=<list>`, or `--no-tools` for an empty allow
list. A row with no allow list gets the Omp twins of Claude Code's default
tools, never Omp-only tools such as `github` or `eval`. A tool the arm cannot
map fails the task before Omp starts. One exception: an allowed `Skill` keeps
`read` on even where the row denies `Read`, because Omp engages a skill by
reading `skill://<name>`. The agent logs it for each task.
`docs/notes/0013-the-omp-arm.md` records what `--tools` does not restrict.

**File tools stay within declared inputs.** `read`, `grep` and `glob` can read
the task root and the linked treatment's `skills/`, `rules/`, `docs/`,
`HAIKU.md` and `README.md`. A bare session gets only the task root.
`skill://` access also requires a skill in the running session's registry.
Canonical paths and descendant symlinks are checked before execution. A tree
with an escaping symlink is refused as a whole.

Use existing files, line selectors and `;`-joined targets. Searches support
ordinary `*` and `?` globs. Missing targets, ambiguous forms and brace or
character-class globs fail closed instead of reaching runtime path recovery.
Provider files, sibling results and host evaluation definitions are not inputs.
The adapter sets `CODER_EVAL_OMP_READ_POLICY`; do not supply it from an experiment.
This is a file-tool guard, not OS isolation. A row granting Bash can still read
the host through the shell. Concurrent filesystem mutation is not isolated.

**A thinking suffix is a separate RPC setting.** Experiments name a model as
`provider/model:level`, but Omp's `set_model` accepts only the provider and
model id. `rpc.model_commands` strips a recognized level such as `:high` and
sends it with `set_thinking_level`; an unknown suffix stays in the model id.
The RPC commands keep the model selection and thinking-level settings separate,
without requiring a model call.

## What it records

Issue #173 asks that a red arm be distinguishable from an arm whose plugin
never arrived. The agent therefore asks the running session what it got and
puts the startup answer in each run's `environment_info`:

| Field | What it answers |
| --- | --- |
| `omp_skills_loaded` | the skills the session offers, read from its own command registry |
| `omp_linked_plugins` | the roots `omp plugin link` installed |
| `omp_extension_errors` | every `extension_error` frame — the constitution rides on the extension |
| `omp_tools` | the Omp built-in tools the row's lists granted |

The captured `agent_end` frame in `fixtures/agent_end_usage.json` settles token
usage. It came from a minimal live Omp 18.4.3 RPC session on 2026-09-29; prompt
and reply content are redacted. Its assistant message sits in `messages` and
carries `usage.input`, `usage.output`, `usage.cacheRead`, and
`usage.cacheWrite`. The same assistant message appears first on `message_end`,
so `rpc.py` accepts both delivery paths and de-duplicates the recorded
`timestamp` when the message has no `responseId`, before recording the token
totals and price.

Tool-call argument keys remain unsettled. The reducer keeps its compatible
spellings and records the one a run sees; this capture made no tool call.
On every exit of an attempt, the adapter atomically writes the observed key
union to `omp-protocol-observations.json` in the task sandbox. The exits are a
completed turn, an async handoff, an early stop, maximum turns, a timeout, a
provider failure, EOF, an unexpected exception and an external cancellation.

The same file carries `omp_settlement_evidence` (version 1): one bounded record
per attempt in the agent session, so a failed retry keeps the earlier record.
Each record holds the attempt ordinal and iteration, the recognized-frame count
and last recognized frame kind, elapsed monotonic seconds, the tool calls still
pending when the attempt ended, counts of terminal, non-terminal and
async-awaiting `agent_end` frames, the last 16 of them with an offset and the
raw `isTerminal` and `awaitingAsyncWork` flags (`null` where the frame omitted
the field), an overflow count, whether async settlement was enabled and taken,
cancellation success, failure and timeout counts, and a fixed `exit_reason`.
It never holds RPC messages, prompts, tool arguments or error text.

This tells a missing handoff from an adapter failure: no `agent_end` observed
means Omp never sent one, while an observed non-terminal end with
`awaiting_async_work` true under `settle_on_async_handoff: false` means the
adapter chose to wait. It does not hold full RPC frames, so a run without this
record cannot be diagnosed after the fact. A write failure never replaces an
attempt's timeout, crash or cancellation. On an otherwise normal attempt it
fails the attempt as a crash.

`omp-glm-5.3.yaml` reads that file through its experiment-default `post_run`
command. Its stdout is each task's durable `post_run_results` evidence. A task
with no completed turn reports the explicit empty observation instead. These
fields do not appear in `environment_info`, because `coder_eval` snapshots
that object before the first turn. `get_sdk_options` is not a workaround:
`resolve_agent_settings` prefers it over `agent_config` and would blank the
report's Agent Settings.

## Task-dispatch evidence

A row that grades which issues an orchestrator assigned sets
`record_task_dispatches: true` (default off). After the subject stops, on every
exit path including a timeout or crash, the adapter atomically replaces
`omp-task-dispatches.json` (`dispatch.py`, version 1). Before sending each
prompt, it exclusively creates an `omp-task-dispatches.json.pending` directory.
The grader rejects evidence while that guard exists. The adapter removes it
only after successful atomic publication and temporary-file cleanup. Failed
writes, replacement, cleanup or process interruption leave the guard in place;
no diagnostic write is needed. If the guard cannot be created, the prompt
does not run. An existing guard blocks retries, including a fresh adapter
that cannot recover the interrupted attempt's calls. Keep failed sandboxes
for audit; use a fresh sandbox for a new run, not manual guard removal.
The artifact holds one record per attempted `task` call, retries included: the
call and attempt identity, the arguments after their final update (`tasks[]`,
requested agent and shared context), the outcome, and the raw result with its
structured details. An argument-less start followed by an update is one call.
Other tools' results are not kept, no field is truncated, and past the 8 MiB
limit the file becomes an explicit instrumentation error that no grader can
score as a pass. The normal telemetry is unchanged and no `Agent` call is
synthesized.

`evals/fixtures/fix-daily-driver-bugs/shared/check_dispatch.py` grades it with
the supported `run_command` criterion, one assignment per `tasks[]` entry,
using only each entry's `task` text. It requires a complete list of distinct
jobs after the successful `Spawned N background agents using <agent>.` header.
It accepts the observed Omp `Coordinate` paragraph only in its captured form
and with a count matching the launch. Other suffixes, or extra launch-like
lines after it, stay unknown and cannot pass. Captured dispatch examples live
under `fixtures/fix-daily-driver-bugs/dispatch-evidence/`.

## Cost

`pricing.py` prices a run from `prices.json`, a hand-maintained table of USD
per million input/output tokens keyed by model identifier — the same spelling
`omp_configs/*.yml` and an experiment's `agent.model` use
(`vercel-ai-gateway/zai/glm-5.3`, not a bare model name). Nothing fetches a
price at run time: the table is a dated snapshot, sourced from
`@oh-my-pi/pi-catalog@18.4.2`'s bundled model catalog, of the models the
current `evals/experiments/omp-*.yaml` files actually run. A model with no row
prices `total_cost_usd` as `None` (`coder_eval`'s own "unreported", not
`0.0`) — adding a new Omp model to an experiment means adding its row here
too. `pricing.py` is pure, like `rpc.py`; it prices recorded token usage without
a `coder_eval` install.

## What is tested, and what is not

`rpc.py`, `pricing.py`, `home.py` and `tools.py` import nothing — not
`coder_eval`, not `omp`. They hold the protocol, pricing, borrowed-home and
tool-list behavior described above, including token-usage and cost math and the
private model-routing merge.

`agent.py` cannot be reached without a `coder-eval` install and an `omp`
binary, and CI here has neither. What it holds is process lifecycle and the
event protocol, both copied from `coder_eval`'s OpenCode agent and from
`scripts/check-omp-plugin.py`, which drives a real `omp --mode rpc` today.

The agent lifecycle includes an early-stop settle path: a replicate that
early-stops on `skill_triggered` must not final-score 0 on that same criterion,
because the abort settle emits frames it had been swallowing. The lifecycle
depends on `coder-eval` and the real `omp --mode rpc` interface.

## Installing it

`make evals-install` does it, with `uv tool install --with`, so the plugin
lands in the same environment as the pinned `coder-eval`. There is nothing to
publish and nothing to release.
