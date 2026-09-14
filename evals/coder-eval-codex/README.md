# `coder-eval-codex`

A `codex-daily-driver` agent kind for
[`coder_eval`](https://github.com/UiPath/coder_eval), so the suites in
[`evals/tasks/`](../tasks) can be run against
[Codex](https://github.com/openai/codex) as well as Claude Code and Omp. It is a
test instrument, not part of the plugin: nothing here ships to a user, and
nothing here is imported by a skill.

```
coder-eval-codex/
├── pyproject.toml                  the `coder_eval.plugins` entry point
└── src/coder_eval_codex/
    ├── transcript.py               the judge's anchor — pure, and tested
    ├── plugins.py                  the plugin root, resolved — pure, and tested
    ├── agent.py                    the built-in agent, subclassed
    └── plugin.py                   register(registry)
```

## Why it exists, and why it is so small

`coder_eval` 0.11.6 already ships a `codex` kind. It drives the Codex SDK, links
a `plugins:` root's skills into `<cwd>/.agents/skills/`, and records command
telemetry in the vocabulary the criteria are written in. This package inherits
all of it. What it adds is two corrections and a record — and each correction
is a silent zero rather than an error if it is missing.

**The judge must find the reply.** Every judge rubric under `evals/tasks/`
locates the reply at the last `[RESULT - …]` tag and scores 0.0 where there is
none — deliberately, so a drifted harness reports nothing rather than something
plausible. `coder_eval` builds that tagged transcript for its Claude Code agent
only; its Codex agent hands the judge `result_text`, the turn's assistant
deltas joined and nothing else. `transcript.render_agent_output` emits the
tagged shape, so one rubric reads the same on all three harnesses.

**The plugin root must be absolute before the built-in sees it.**
`CodexAgent._setup_skills` links each skill with `target.symlink_to(skill_dir)`,
where `skill_dir` is built from `config.plugins[].path` exactly as written. The
experiments here write `path: ".."`, relative to the `evals/` directory the run
targets `cd` into — which is right for the Claude agent, because `coder_eval`
resolves plugin paths before that agent is built, and wrong for the Codex one,
which never goes through that resolution.

Measured against this repository's real layout: a relative root makes every link
body relative too, so `.agents/skills/pr -> ../skills/pr` resolves back to the
link's own directory and points at itself. Fourteen entries are created and not
one of them has a readable `SKILL.md`; the treated arm runs with no skills and
every trigger row scores 0, at full price. `_setup_skills`'s own "0 skills
linked" warning counts `iterdir()` entries, so it stays silent on it.
`plugins.resolve_local_plugins` makes the root absolute in `start()` before
delegating, and `start()` then raises — rather than warning — when plugins were
declared and no readable skill arrived.

Both raises are `coder_eval`'s typed `AgentConfigError`, never a bare
`RuntimeError`. Measured: `coder_eval` categorises a bare `RuntimeError` as
`agent_api_error`, which carries three retries at 5/10/20s with the Codex client
re-spawned each time, and a mistyped plugin root retried three times is a
mistyped plugin root three times over, finally reported as a network problem.
`AgentConfigError` is routed by `isinstance` to `agent_config_error`, whose
retry count is zero.

**It is registered as a new kind, not as a replacement for `codex`.** The
registry rejects two implementations claiming one kind, so shadowing the
built-in would change what every other `coder_eval` user's `codex` means. The
distinct kind also makes the routing readable: `scripts/check-eval-arms.py` maps
a pinned `agent.type` to the arm tag it must carry.

## The normalisation that is not here

Issue #185 asked for a second one: a mapping of `skill://<name>`, the URL Omp
engages a skill through, so `skill_triggered` could see it. Codex does not use
that spelling, and the criterion already sees the one it does.

The spike in [#181](https://github.com/jmcvetta/daily-driver/issues/181)
measured both halves. Codex has no skill tool: the model is handed a skills
table in a developer message and opens `SKILL.md` with an ordinary shell call,
and a `skill://` mention in a prompt reaches the model as literal text. On the
other side, `coder_eval`'s `skill_triggered` matches `skills/<name>/` in any
string tool parameter — its own docstring names Codex as the agent that branch
was written for. `CodexAgent._setup_skills` links each skill at
`.agents/skills/<name>/`, the Codex SDK types `CommandExecutionThreadItem.command`
as `str`, and `_extract_command_telemetry` puts that string in
`parameters["command"]`. The substring is there to match, with nothing to
rename.

## What it records

`0013`'s rule for the Omp arm holds here too: a red arm and an arm whose plugin
never arrived must not read alike. One field lands in each run's
`environment_info`, beside the routing keys the built-in already records.

| Field | What it answers |
| --- | --- |
| `codex_skills_linked` | the skills with a readable `SKILL.md` under `.agents/skills/` after `start()` |

`codex_skills_linked` is read from the directory, not from the session. The
Codex app-server exposes no query for the skills it discovered, so unlike the
Omp arm's `omp_skills_loaded` this says what was *offered* rather than what was
taken up. It requires a readable `SKILL.md` rather than counting directory
entries, which is what makes it an answer: fourteen broken symlinks are fourteen
entries.

**Only one field, and that is a constraint rather than a choice.** `coder_eval`
merges `get_environment_info()` into the result once, during setup, right after
`start()` and before any turn runs. So a counter incremented in `communicate()`
would always be recorded as zero — a field that says nothing while looking like
a measurement. `codex_skills_linked` is recordable precisely because `start()`
fills it.

The drift that a counter would have alarmed on is logged where it happens
instead: the first turn to arrive already carrying the `[RESULT - …]` anchor
warns, once per session. Under the pinned `CODER_EVAL_VERSION` that never
happens; when it starts happening the built-in has begun rendering the
transcript itself and this package is a no-op worth deleting.

## What is tested, and what is not

`transcript.py` and `plugins.py` import nothing — not `coder_eval`, not the
Codex SDK — and `scripts/check-codex-agent.py` drives both in `make check`. That
leg asserts the rendered shape is byte-identical to
`coder_eval_omp.rpc.render_agent_output` for one block, which is what keeps one
rubric readable on both harnesses without either package depending on the other;
and it builds the self-referential symlink a relative root produces, so the
assertion is the failure itself rather than a description of it.

`agent.py` cannot be reached without a `coder-eval` install and the Codex SDK,
and CI here has neither. What it holds is the subclass: two overrides, a
directory read, and the calls into the two modules above.

## Installing it

`make evals-install` does it, with `uv tool install --with`, so the kind lands in
the same environment as the pinned `coder-eval`. The Codex SDK comes with it —
this package depends on `coder-eval[codex]`, because the built-in agent imports
`openai_codex` inside `start()` and fails at run time without it. There is
nothing to publish and nothing to release.
