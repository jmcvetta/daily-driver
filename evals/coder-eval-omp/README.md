# `coder-eval-omp`

An `omp` agent kind for [`coder_eval`](https://github.com/UiPath/coder_eval), so
the suites in [`evals/tasks/`](../tasks) can be run against
[Omp](https://omp.sh) as well as Claude Code. It is a test instrument, not part
of the plugin: nothing here ships to a user, and nothing here is imported by a
skill.

```
coder-eval-omp/
├── pyproject.toml                 the `coder_eval.plugins` entry point
└── src/coder_eval_omp/
    ├── rpc.py                     the frame reduction — pure, and tested
    ├── agent.py                   the process, the events, and what loaded
    └── plugin.py                  register(registry)
```

## Why it exists

`coder_eval` ships five agent kinds and `omp` is not one of them. It does ship
a bring-your-own-agent seam — an entry point in the `coder_eval.plugins` group
whose target is a `register(registry)` callable — and `coder_eval` registers its
own built-ins through that same group, so the path cannot silently rot.

Three things this adapter must get right, and each one is a silent zero rather
than an error if it does not.

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

## What it records

Issue #173 asks that a red arm be distinguishable from an arm whose plugin
never arrived. The agent therefore asks the running session what it got and
puts the startup answer in each run's `environment_info`:

| Field | What it answers |
| --- | --- |
| `omp_skills_loaded` | the skills the session offers, read from its own command registry |
| `omp_linked_plugins` | the roots `omp plugin link` installed |
| `omp_extension_errors` | every `extension_error` frame — the constitution rides on the extension |

The two protocol questions use a later capture. Omp's `docs/rpc.md` shows
`toolName` on `tool_execution_start` without showing the arguments, and places
token accounting in "telemetry fields on `agent_end`" without naming them.
After each completed turn, the adapter atomically writes the sorted observed
key union to `omp-protocol-observations.json` in the task sandbox:

```json
{"omp_argument_keys_seen":["args"],"omp_usage_keys_seen":["inputTokens","outputTokens"]}
```

`omp-glm-5.3.yaml` reads that file through its experiment-default `post_run`
command. Its stdout is each task's durable `post_run_results` evidence. A task
with no completed turn reports the explicit empty observation instead. These
fields do not appear in `environment_info`, because `coder_eval` snapshots
that object before the first turn. `get_sdk_options` is not a workaround:
`resolve_agent_settings` prefers it over `agent_config` and would blank the
report's Agent Settings.

## What is tested, and what is not

`rpc.py` imports nothing — not `coder_eval`, not `omp` — and
`scripts/check-omp-agent.py` drives it against recorded frames in `make check`.
That is where the three things above live, and it is why they live there.

`agent.py` cannot be reached without a `coder-eval` install and an `omp`
binary, and CI here has neither. What it holds is process lifecycle and the
event protocol, both copied from `coder_eval`'s OpenCode agent and from
`scripts/check-omp-plugin.py`, which drives a real `omp --mode rpc` today.

One part of that lifecycle carries its own acceptance test:
`scripts/check-omp-agent-settle.py` (`make check-omp-agent-settle`) drives the
real `communicate` against a fake `omp --mode rpc` and asserts the
early-stop invariant the first live run violated — a replicate that
early-stops on `skill_triggered` cannot final-score 0 on that same criterion,
because the abort settle emitted the frames it had been swallowing. It needs
the `coder-eval` install (`make evals-install`), so it is not a `make check`
leg, and it needs no network, so it is cheap to run whenever `agent.py`
changes.

## Installing it

`make evals-install` does it, with `uv tool install --with`, so the plugin
lands in the same environment as the pinned `coder-eval`. There is nothing to
publish and nothing to release.
