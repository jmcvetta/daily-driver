# Runtime integration and compatibility

Daily Driver shares skill instructions and a marketplace catalog across Omp, Claude Code and Codex. Tool calls live in each skill's `references/` directory. Runtime adapters handle the differences between harnesses.

Claude Code repository instructions live in `.claude/CLAUDE.md`, which imports
the root `AGENTS.md`. This project context is distinct from plugin-delivered
skills and the constitution injected by runtime hooks.

## Runtime integration

Claude Code and Codex use hooks for the constitution and chat-based question
routing. Codex subagent injection is not verified: its configured
`SubagentStart` event was not observed, as the [Codex integration
note](notes/0016-three-harnesses-one-skill-tree.md#known-limits-recorded-rather-than-fixed)
records.

The constitution source is `rules/constitution.md`. Both the hooks and Omp's
rule provider deliver its complete Markdown body after removing the
`alwaysApply: true` frontmatter; they do not select individual sections.
The hook table below describes the hook routes. Omp loads the file directly
as a rule, as described below.

| Hook | Event | Purpose |
| ---- | ----- | ------- |
| `inject-constitution.py` | `SessionStart`, `SubagentStart`, and `PreToolUse` on `Agent`/`Task` | Delivers the constitution at session start; Codex subagent delivery is unverified. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Blocks the question widget and directs questions to chat. |
| `title-gate.py` | Issue-comment and session-creation events | On Claude Code cloud sessions, holds the first issue comment and dispatch until the session is titled. |

Omp uses `extensions/daily-driver.js`. It blocks the `ask` tool, holds issue and pull-request comments and task dispatch until the session is titled, and provides session-title, reminder and session-info tools. Explicit `embark` requests require a canonical issue read before dispatch. Omp loads constitution files with `alwaysApply: true` frontmatter.

The exact calls and per-skill differences live in the active harness's reference file. The [architecture notes](notes/0011-two-harnesses-one-skill-tree.md) and [Codex integration note](notes/0016-three-harnesses-one-skill-tree.md) record why the adapters differ.

## Task continuation and approval evidence

The constitution requires agents to diagnose ordinary failures, preserve
applicable approval, and finish independent permitted work before pausing.
`undertake` owns the detailed escalation contract. The rule also applies to
ordinary repository work.

On Omp, `extensions/task-state.mjs` registers `daily_driver_task_state` and
uses `session_stop` for bounded correction. Task scope, source-anchored
authorization, tool evidence and correction counts live in private,
active-branch session entries. The adapter restores a compact handoff during
context preparation and compaction. `status` returns bounded source excerpts;
`status` with a JSON `record` containing `sourceId` returns that original
source. The [Omp undertaking reference](../skills/undertake/references/omp.md#task-evidence-state)
defines the tool's records.

An unsupported unfinished stop receives at most two corrective continuations
per unchanged observed condition. Restarting the process does not renew that
allowance. Explicit cancellation and an aborted stop handler prevent further
correction. Exhaustion reports an execution failure, not completion or a new
approval requirement. Ordinary questions do not automatically activate a task.

These checks validate provenance, scope fields and referenced observations.
They do not prove that arbitrary prose grants permission, that every possible
route was exhausted, or that reported completion satisfies acceptance criteria.
The tool does not replace harness permissions. Original approval sources,
conditions and safety restrictions remain authoritative. A copied agent
handoff cannot grant approval in another session.

`scripts/check-omp-task-state-live.py` exercises the installed Omp with a local
scripted provider, persistent session resume and RPC abort. It makes no live
model request. Behavioral cases separately measure whether a model uses
approval and completes permitted actions; see [evaluation guidance](../evals/README.md).

### Hook-harness boundary

Claude Code and Codex document stop interception, but Daily Driver does not
claim the Omp adapter is enforced there:

- [Claude Code's `UserPromptSubmit`](https://code.claude.com/docs/en/hooks#userpromptsubmit)
  also receives scheduled tasks, background-agent reports and peer messages.
  Its documented event has no origin discriminator. Treating every prompt
  event as a user source would manufacture authority and could restart
  cancelled work.
- [Codex documents `Stop` and `Interrupt`](https://developers.openai.com/codex/hooks).
  Its stop continuation becomes a new user prompt, so an adapter must exclude
  its own messages from authority and retry renewal. The shared plugin hook
  manifest cannot register Codex's `Interrupt` event: Claude's strict plugin
  validator reports it as unknown and rejects the manifest.

These are integration limits, not a claim that either harness lacks a stop
hook. Their shared workflow and handoff contracts preserve approval references
and require blocker evidence. Runtime parity needs a supported transport with
verified input-origin and cancellation semantics, not guessed transcript fields
or omission of cancellation handling.

## Omp task roles and worktrees

The Omp installation defines `mechanical`, `implementation`, `reasoning` and
`frontier` task roles. Where no operator assignment exists, the extension
supplies defaults. Frontier is limited to explicitly approved, bounded research
or planning; ordinary implementation uses a non-frontier route unless the user
separately authorizes that exception. The defaults require configured
credentials. Use `/model` → Roles to assign models. Existing `omp_configs/`
files remain process overlays; assignments present at startup take precedence,
and later edits may require an Omp restart.

Omp does not relocate a live session when it creates a task worktree. Use the
verified absolute task-worktree paths for shell and file-tool operations.

Omp 18.5.0 supports the user-initiated `/move <path>` for an idle session.
The extension API does not provide direct relocation, so automatic
plugin-driven movement is not available.

The guard rejects primary-checkout and detached-worktree `write` and `edit`
calls. It also denies Git commands that rewrite the primary checkout's files.
Attached feature-worktree mutations remain available. The command parser is
conservative: it rejects unresolved commands and unterminated quotes. It does
not audit programs launched through `make`, Python or scripts, so those
programs must also stay inside the task worktree.

Use absolute task-worktree paths in file tools. Omp resolves file-tool paths
against the session working directory, not a directory change made by a shell.

## Compatibility limits

- **Omp plugin-directory development:** `omp --plugin-dir <path>` loads skills but not the extension. Use `omp plugin link .` or install the plugin to exercise runtime tools and guards.
- **Claude Code plugin-directory development:** `claude --plugin-dir <daily-driver>` does not fetch marketplace dependencies. Also pass the official Worktrunk plugin directory at `worktrunk/plugins/worktrunk` when testing this route. The shared catalog installs the dependency automatically; Omp and Codex install Daily Driver alone.
- **Codex:** GitHub operations use `gh` in the shell. Codex has no durable wake mechanism or blocking check wait, so `undertake` stops its branch-update cycle at `Ready for review`. Unattended runs cannot access a session client, and `embark` uses local subagents rather than web sessions. Each skill's Codex reference describes its route and limits.

See [Repository setup](bootstrapping-a-repository.md) for installation and hook-trust requirements. See each skill's references for current tool routes; this page summarizes integration rather than replacing those contracts.
