# `coder-eval-codex`

A `codex-daily-driver` agent kind for
[`coder_eval`](https://github.com/UiPath/coder_eval), driving the installed
[Codex CLI](https://github.com/openai/codex) so the suites in
[`evals/tasks/`](../tasks) can be measured on the same subscription and model
as the Omp arm. It is a test instrument, not part of the plugin: nothing here
ships to a user, and nothing here is imported by a skill.

```
coder-eval-codex/
├── pyproject.toml                  the `coder_eval.plugins` entry point
└── src/coder_eval_codex/
    ├── events.py                   the JSONL stream, reduced — pure, and tested
    ├── discovery.py                login and model-catalog parsing — pure, and tested
    ├── skills.py                   plugin skills linked for the CLI — pure, and tested
    ├── transcript.py               the judge's anchor — pure, and tested
    ├── plugins.py                  the plugin root, resolved — pure, and tested
    ├── agent.py                    the driver: spawn, stream, resume, record
    └── plugin.py                   register(registry)
```

## Why it is a driver rather than a subclass

`coder_eval` 0.11.6 ships a `codex` kind that drives the Codex **SDK**. The
comparison this arm exists for is the shipped **CLI** — the executable a user
runs — so the SDK is not a substitute. The SDK has its own transport,
authentication and session model, and a result from it cannot answer whether the
CLI behaves the same as Omp. `0015` records the decision; this package is the
execution path.

The kind is still registered separately from the built-in `codex`, for the
reason the SDK subclass was: the registry rejects two implementations claiming
one kind, and a distinct name makes each experiment's `agent.type` match its arm
tag.

## The turn

One process per `communicate()`:

```sh
codex exec --json --skip-git-repo-check -C <task-dir> -s workspace-write \
  -c approval_policy="never" -m <model> -c model_reasoning_effort="<effort>" -
```

The prompt is written to stdin and the process is read line by line. Later
turns resume the same thread:

```sh
codex exec ... resume <thread_id> -
```

`events.py` reduces the documented stream — `thread.started`, `turn.started`,
`item.started`, `item.completed`, `turn.completed`, `turn.failed`, `error` —
into plain values, so the parsing is testable without an authenticated binary.
`error` is not always fatal: a live run against a flaky transport emits
reconnect notices and then completes, so only a stream with no `turn.completed`
is a failed turn.

Item types map to the canonical vocabulary every criterion is written against:
`command_execution` → `Bash`, `file_change` → `Write`, `mcp_tool_call` → `Mcp`,
`web_search` → `WebSearch`. Unknown item types are recorded as a bounded sample
rather than dropped.

## Evidence before inference

`start()` asks the binary, not the account metadata:

| Field | Source |
| --- | --- |
| `codex_cli_version` | `codex --version` |
| `codex_login_status`, `codex_auth_mode` | `codex login status` |
| `codex_model_catalog_checked` | `codex debug models` |
| `codex_skills_linked` | the linked `.agents/skills` tree |
| `codex_billing_source` | `subscription` when the login is a subscription |

It fails closed when the answer contradicts the arm: no executable, an
unrecognized login, an API key in `CODEX_API_KEY`/`OPENAI_API_KEY`, or a model
the catalog does not list. A missing catalog is recorded as unchecked, not
treated as proof of absence.

Subscription usage records tokens and no cash cost. The CLI reports no charge
for allowance, and coder_eval's rate card is a list price, not a bill.

## Skills

`skills.link_skills` resolves each `plugins:` root against the process working
directory (the experiments write `path: ".."`, relative to `evals/`) and
symlinks every `skills/<name>/` into `<task dir>/.agents/skills/<name>`. The CLI
scans that directory from the working directory up to the repository root and
follows symlinks.

This replaces a measured defect from the SDK subclass: a relative root made
every link body relative, so `.agents/skills/pr -> ../skills/pr` resolved back
to its own directory. One entry per skill was created and not one had a readable
`SKILL.md`; the treated arm ran untreated and every trigger row scored 0. Here
the root is resolved before use, and a declared root with no readable skill
raises a configuration error instead of warning.

## What is tested, and what is not

`events.py`, `discovery.py`, `skills.py`, `transcript.py` and `plugins.py`
import nothing outside the standard library, so their reduction, parsing and
linking are exercised offline by
[`tests/test_codex_cli_contract.py`](tests/test_codex_cli_contract.py).

`agent.py` needs an installed, subscription-authenticated `codex` binary and
cannot run in CI. It holds the spawn/stream/settle loop and the event-to-record
mapping; the load-bearing pieces it calls are the pure modules above.

## Installing it

`make evals-install` puts the kind in the same environment as the pinned
`coder-eval` with `uv tool install --with`. The Codex SDK is deliberately not a
dependency: the CLI is installed and authenticated on the machine that runs the
arm (`npm install -g @openai/codex`, then `codex login`). There is nothing to
publish and nothing to release.
