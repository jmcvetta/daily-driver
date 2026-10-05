# daily-driver

Daily Driver is a plugin that provides shared development workflows for
[Claude Code][cc], [Omp][omp] and [Codex][codex].

[cc]: https://claude.com/claude-code
[omp]: https://omp.sh
[codex]: https://github.com/openai/codex

This is a personal toolkit, published without a license. The author recommends
against using it. Read [ANTI-LICENSE.md](ANTI-LICENSE.md) before proceeding.

## Installation

Install the plugin once per machine, or once per cloud environment. Each
harness stores and loads its own installation. Repository configuration can
reference the plugin but does not install it.

The Claude Code marketplace installation also enables the official Worktrunk
plugin as `worktrunk@daily-driver`; it does not install the separate `wt` CLI.
Cloud Setup provisions the CLI before the session.

If you already installed `worktrunk@worktrunk`, migrate it before installing
or updating Daily Driver. Disable and uninstall it at every scope where it is
installed or enabled, then install Daily Driver at that same scope. For a
user-scope installation:

```sh
claude plugin disable worktrunk@worktrunk --scope user
claude plugin uninstall worktrunk@worktrunk --scope user
claude plugin install daily-driver@daily-driver --scope user
```

Repeat the disable and uninstall commands with `--scope project` or
`--scope local` where the legacy identity exists. A managed installation must
be migrated by its administrator. Restart or reload Claude Code after the
migration, then confirm `claude plugin list` shows `worktrunk@daily-driver`
enabled and no `worktrunk@worktrunk` identity enabled.

On desktop, `task-worktree` installs `wt` on demand when repository-changing
work needs isolation and the CLI is missing. It uses Homebrew or Cargo in user
scope and verifies the binary before continuing. You can install it ahead of
time with Worktrunk's documented [Homebrew or Cargo
installation][worktrunk-install]:

```sh
brew install worktrunk
# or: cargo install --locked worktrunk
```

[worktrunk-install]: https://worktrunk.dev/#install

To synchronize this repository from a linked worktree, install Worktrunk's
shell integration and run `wt sync`. It switches the calling shell to the
primary worktree, pulls `master`, and uses Worktrunk to offer safe cleanup of
branches deleted upstream:

```sh
wt config shell install
wt sync
```

### Claude Code

```sh
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install daily-driver@daily-driver
```

### Omp

Omp uses the same marketplace catalog as Claude Code:

```sh
omp plugin marketplace add jmcvetta/daily-driver
omp plugin install daily-driver@daily-driver
```

Run `omp plugin list` to confirm installation.

### Codex

Codex uses the same marketplace catalog, but its installation command is
`plugin add`, not `plugin install`:

```sh
codex plugin marketplace add jmcvetta/daily-driver
codex plugin add daily-driver@daily-driver
```

Run `codex plugin list` to confirm installation. The following limitations
were verified with `codex-cli` 0.154.0:

- **Installation state is stored in `$CODEX_HOME/config.toml`**, in the
  `[marketplaces.…]` and `[plugins."…"]` tables. There is no separate
  installation manifest. Preserve these tables when editing the file;
  replacing the file removes plugin registrations.
- **Hooks require persisted trust.** Without it, Codex silently skips
  constitution injection and question-widget blocking.
  For automation that has already vetted the source, `codex exec` provides
  `--dangerously-bypass-hook-trust`.

The shared catalog also lists Worktrunk's official Claude plugin as a Claude
Code dependency. Installing Daily Driver in Omp or Codex does not install that
Claude-only dependency.

### Claude Code cloud environments

In Claude Code cloud environments, install Worktrunk and the plugins in the
environment's **Setup script**, which runs before the plugin scan. The
environment dialog is behind the cloud icon above the message box at
[claude.ai/code][web].

[web]: https://claude.ai/code

```bash
#!/bin/bash
set -euo pipefail
# CACHEBUST: 1
# Setup is cached by script text; bump CACHEBUST only to force a rerun.
# Each Setup run installs current Cargo; new releases do not trigger a rerun.
cargo install --locked --root /usr/local worktrunk
wt --version

claude plugin marketplace add jmcvetta/daily-driver
claude plugin install --yes daily-driver@daily-driver

# Verify each plugin is cached at a version and registered as enabled.
for plugin in daily-driver worktrunk; do
  grep -qF "\"${plugin}@daily-driver\"" "$HOME/.claude/plugins/installed_plugins.json"
  compgen -G "$HOME/.claude/plugins/cache/daily-driver/${plugin}/*/.claude-plugin/plugin.json" >/dev/null
done
claude plugin list --json | python3 -c '
import json, sys
enabled = {plugin["id"] for plugin in json.load(sys.stdin) if plugin.get("enabled")}
expected = {"daily-driver@daily-driver", "worktrunk@daily-driver"}
missing = expected - enabled
if missing:
    raise SystemExit(f"plugins not enabled: {sorted(missing)}")
'
```

Keep installation failures fatal: a setup script that exits successfully after
a failed installation caches that failure. Each setup run builds the latest
published Worktrunk release through Cargo. A reused environment keeps its
installed binary and does not update it when a session resumes. Change
`CACHEBUST` only when you need setup to run again.

After setup, start a session and verify that the plugins loaded:

> Without reading any file, say what the constitution tells you about
> production systems. Then list the skills available to you whose names begin
> `daily-driver:`. Then list the enabled plugins `daily-driver@daily-driver`
> and `worktrunk@daily-driver`, and run `ls
> ~/.claude/plugins/cache/daily-driver/`.

Installation alone does not prove that a plugin loaded. Use the session's
response to check that the rules and skills are available.

See [Repository setup](docs/bootstrapping-a-repository.md) for the
`.claude/settings.json` configuration that enables the plugin for a repository.

**The supplied repository configuration is for Claude Code.** With
`codex-cli` 0.154.0, `codex doctor` reports `$CODEX_HOME/config.toml` as the only
loaded configuration file. A project `.codex/config.toml` does not enable the
plugin. Configure Codex at user scope through the tables described above.

## Usage

Skills activate from supported slash commands, natural-language requests and
relevant tool calls. For example, ask the assistant to review a pull request
or update a README. Each skill's `SKILL.md` describes its activation rules.

| Skill | Purpose |
| ----- | ------- |
| `conventional-commits-type` | Selects the Conventional Commits type from the change's effect on users. |
| `deps` | Upgrades dependencies through package managers, checks CI and reports major upgrades for review. |
| `embark` | Coordinates task sessions for an epic, monitors pull requests and merges completed tasks. |
| `epic` | Plans work that spans multiple pull requests as task issues under an epic. |
| `issue` | Creates or updates GitHub issues, including their bodies, labels and relationships. |
| `issue-body` | Writes issue bodies and implementation-ready task handoffs. |
| `issue-deps` | Records and reads blocking dependencies, sub-issues and pull-request closing references. |
| `issue-labels` | Assigns issue kinds and readiness labels. |
| `judgement-call` | Resolves standard engineering choices and asks the user when intent or a material trade-off requires their decision. |
| `pr` | Creates a draft pull request or updates the existing pull request for the current branch. |
| `pr-body` | Writes pull request summaries, blockers, issue references and reviewer details. |
| `pr-title` | Writes concise Conventional Commits titles. |
| `provenance` | Records model, harness and session provenance in GitHub writes and commits. |
| `readme` | Writes READMEs focused on what a project does and how to use it. |
| `review-cycle` | Reviews a pull request, assesses findings and determines when another review is needed. |
| `session-title` | Sets concise session titles, including the issue number when applicable. |
| `stand-down` | Stops epic coordination and records task handoffs. |
| `task-worktree` | Isolates repository changes in a feature branch and sibling worktree before research begins. |
| `undertake` | Takes a task from its description to a review-ready pull request and keeps the branch current. |

## Development rules

[`rules/constitution.md`](rules/constitution.md) applies to every session and
subagent. It defines the following requirements:

| Section | Requirements |
| ------- | --------------- |
| Voice | Simplified Technical English for prose written in your own voice. |
| Before you reply | Keep human-facing text concise and agent-facing handoffs complete. |
| Non-negotiables | Do not access production systems. Isolate repository changes, test application code and fix failures rather than hide them. |
| While you write code | Read the manual first, prefer simple designs and existing libraries, and prioritize correctness. |
| When you hit a wall | Stop on errors, reassess failing approaches, clarify intent and report confirmed Daily Driver defects. |
| Before you commit | Document new exported symbols, make focused commits and stage named files. |
| Before you call it done | Use the project's CI gates to verify completion. |
| Dependencies | Add and pin dependencies through the package manager. |
| Delegation | Plan before delegating and run independent work in parallel. |

## Runtime integration

Claude Code and Codex use hooks to load the constitution and require questions
in chat rather than in a multiple-choice widget:

| Hook | Event | Purpose |
| ---- | ----- | ------- |
| `inject-constitution.py` | `SessionStart`, `SubagentStart`, and `PreToolUse` on `Agent`/`Task` | Delivers `rules/constitution.md` to the session and every subagent. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Blocks the multiple-choice widget and directs the assistant to ask in chat. |

Omp uses `extensions/daily-driver.js` instead of hooks. The extension blocks the
`ask` tool and provides session-title, reminder and session-info tools:
`daily_driver_set_session_title`, `daily_driver_schedule`,
`daily_driver_cancel_schedule` and `daily_driver_get_session`. Omp's rule
provider loads the constitution from `rules/*.md` with `alwaysApply: true`.

### Omp task roles

The Omp installation provides three task-class roles and matching agents:
`mechanical`, `implementation` and `reasoning`. At session start, the extension
adds runtime selectors for roles without an effective assignment. It adds
visible role tags without replacing operator metadata.

The default selectors require configured OpenAI Codex credentials. Use
`/model` → Roles to assign models. Existing `omp_configs/` files remain process
overlays. Assignments present at startup take precedence; later YAML or overlay
edits may require an Omp restart because runtime overrides shadow disk reloads.
Model capabilities are not considered verified until class evaluations report
them.

### Worktree isolation

Omp does not relocate a live session when the agent creates a task worktree.
Use the verified absolute task paths for file tools and shell work. Omp 18.5.0
offers the user-initiated `/move <path>` for an idle session; the extension API
does not provide direct relocation, so automatic plugin-driven relocation is
outside this plugin's scope.

The extension blocks direct `write` and `edit` calls in the primary checkout
or a detached worktree. Rejections report the target paths, tool working
directory, containing worktree, primary worktree and branch state. Use these
details to correct the file-tool path.
Omp resolves file-tool paths against its session cwd, so a relative edit
header still targets the session root after a bash `cd`. Use the verified
absolute task-worktree path in each write target, edit header, and move
destination. Git commands that rewrite the primary checkout's working tree
are also denied — `checkout`, `switch`, `reset --hard`, `restore`, `stash`,
`merge`, `rebase`, `pull`, `apply`, `am`, `cherry-pick`, `revert`, `clean`,
`rm`, `mv`, `bisect`, `sparse-checkout` and `submodule`. The test is whether
the command rewrites tracked files, not whether it moves HEAD, so harmless
forms stay available: `git reset --soft`, `git restore --staged`, `git stash
list`, `git apply --check` and `git clean --dry-run` all pass. Attached
feature-worktree mutations, worktree creation, branch attachment in a
detached worktree — the primary included, where that is the only way out, and
for the attach itself rather than every form of `checkout` and `switch` —
non-Git paths, and synthetic devices remain available. Git-command denials
retain their generic recovery guidance.

**Shell command parsing is conservative.** The guard must identify every
command in a `bash` call before allowing it. It rejects commands it cannot
resolve, including variable-based executable names and unterminated quotes.
Use literal command names when a call is rejected.

**The guard does not audit programs.** It parses shell command strings,
including literal `bash -c` operands, but does not inspect script contents.
A program started through `make`, `python3` or a shell script can still modify
the primary checkout. The `task-worktree` rules apply to those programs too.

## Compatibility and local development

All three harnesses use the same skills and marketplace catalog. Claude Code
and Codex share the hooks in `hooks/`; Omp uses `extensions/daily-driver.js`.
Each skill's `references/` directory contains the tool calls for each harness.

**Claude Code inline development needs both plugin directories.** A
`claude --plugin-dir <daily-driver>` invocation does not fetch marketplace
dependencies. When testing this route, also pass the official Worktrunk plugin
directory from `worktrunk/plugins/worktrunk`. The shared catalog dependency is
installed automatically only through the marketplace route; Omp and Codex
continue to install Daily Driver alone.

**Omp's `--plugin-dir <path>` loads skills but not the extension.** Use it to
edit skills directly from a checkout. To exercise the runtime adapter, install
the plugin or run `omp plugin link .`. Without the installed extension, the
`ask` guard and `daily_driver_*` tools are unavailable. This behavior was
verified with Omp 18.1.17.

**Codex has additional workflow limitations.** GitHub operations use `gh` in
the shell, as they do on Omp. Codex has no durable wake mechanism or blocking
check wait, so `review-cycle` cannot wait and `undertake` stops its branch-update
cycle at `Ready for review`. Unattended runs cannot access a session client,
so `session-title` reports that limitation and `embark` uses local subagents
instead of web sessions. Each skill's `references/codex.md` documents these
limitations.

## Documentation

- [Repository setup](docs/bootstrapping-a-repository.md): installation,
  repository configuration and plugin loading.
- [Harness architecture](docs/notes/0011-two-harnesses-one-skill-tree.md) and
  [Codex integration](docs/notes/0016-three-harnesses-one-skill-tree.md):
  shared skills and harness-specific behavior.
- [Question handling](docs/notes/0009-deny-the-question-widget.md):
  chat-based questions and the `judgement-call` skill.
- [Evaluation guide](evals/README.md): live-model evaluation suites.
- [Repository infrastructure](infra/github/README.md): OpenTofu configuration.
- [GitHub MCP configuration](docs/github-mcp.md): tool selection and usage.
- [CI workflow](.github/workflows/ci.yml) and [Makefile](Makefile):
  validation jobs and development commands.
- [Archived components](attic/README.md): retained components that are not loaded.

## License

No license is granted. This toolkit is intended for its author's personal use;
the author recommends creating your own instead. See
[ANTI-LICENSE.md](ANTI-LICENSE.md) for the full notice.
