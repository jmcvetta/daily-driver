# Runtime integration and compatibility

Daily Driver shares skill instructions and a marketplace catalog across Omp, Claude Code and Codex. Tool calls live in each skill's `references/` directory. Runtime adapters handle the differences between harnesses.

Claude Code repository instructions live in `.claude/CLAUDE.md`, which imports
the root `AGENTS.md`. This project context is distinct from plugin-delivered
skills and the constitution injected by runtime hooks.

## Runtime integration

Claude Code and Codex use hooks for the constitution, per-prompt style guidance
and chat-based question routing. Codex subagent injection is not verified:
its configured `SubagentStart` event was not observed, as the [Codex integration
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
| `prompt-guidance.py` | `UserPromptSubmit` | Adds terse-style guidance unless the prompt ends with `noterse`. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Blocks the question widget and directs questions to chat. |
| `title-gate.py` | Issue-comment and session-creation events | On Claude Code cloud sessions, holds the first issue comment and dispatch until the session is titled. |

Omp uses `extensions/daily-driver.js`. It blocks the `ask` tool, holds issue and pull-request comments and task dispatch until the session is titled, and provides session-title, reminder and session-info tools. Explicit `embark` requests require a canonical issue read before dispatch. Omp loads constitution files with `alwaysApply: true` frontmatter.

The exact calls and per-skill differences live in the active harness's reference file. The [architecture notes](notes/0011-two-harnesses-one-skill-tree.md) and [Codex integration note](notes/0016-three-harnesses-one-skill-tree.md) record why the adapters differ.

## Prompt guidance

Each prompt receives this instruction, following
[`be-terse`](https://github.com/bigskysoftware/be-terse):

> respond tersely in Simplified Technical English

End a prompt with the case-sensitive suffix `noterse` to skip the addition for
that prompt. Trailing whitespace is allowed. The prompt itself is unchanged.
The next prompt receives the instruction again unless it also opts out.
This is a style request, not a reply-length limit or a guarantee of compliance.
Requested explanations, formats and essential facts still take precedence.
There is no restatement pass, judge or extra model turn.

Claude Code and Codex receive the instruction through `UserPromptSubmit`
`additionalContext`. Codex requires hook trust as described in
[Repository setup](bootstrapping-a-repository.md#codex-has-no-stanza-at-all).
These harnesses retain earlier hook context in conversation history;
`noterse` skips new guidance rather than erasing that history.

Omp adds the instruction as hidden context after the prompt in
`before_agent_start`, after slash-command and template expansion. It does not
change command arguments, images or user text. For a queued batch, the suffix
is checked on the combined expanded prompt. Synthetic prompts can also receive
the style instruction; revive events do not add it. Earlier context remains in
the conversation when a later prompt uses `noterse`.

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
`status` with a JSON `record` containing `sourceId` returns the original
authority source or retained tool evidence. Tool input/output payloads have
bounded previews, truncation metadata and a fingerprint; the adapter does not
persist a second full copy of every file written or command result.
The [Omp undertaking reference](../skills/undertake/references/omp.md#task-evidence-state)
defines the records and exact-quote limits.

An unsupported unfinished stop receives at most two corrective continuations
per unchanged observed condition. Restarting the process does not renew that
allowance. Explicit cancellation and an aborted stop handler prevent further
correction. Exhaustion persists an execution failure and shows an error
notification without scheduling another model turn. Ordinary questions do not
automatically activate a task.

Enforcement also requires an accessible task-state tool: either direct
exposure, or Omp's active `write` device route. A restricted tool selection
without either route receives a capability notice, not corrections that demand
an inaccessible tool. The adapter never enables tools or calls this a missing
user approval. Shared workflow instructions still apply.

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

An operator's manual escalation during a failing task authorizes the
consultation. Follow the constitution's *Manual frontier escalation*: repair
the plan and return the existing work to a verified eligible non-frontier
route. The escalation does not authorize frontier implementation or supervision.

`dailyDriver.modelClassRoutes` is an array of entries with `referenceModel`
and `classes`, for example `{ referenceModel: "provider/model", classes: {
implementation: "provider/variant:high" } }`. Omp resolves the reference
through its model catalog to identify the family and provider. A family entry
does not authorize a different provider. The built-in OpenAI Codex entry
preserves the existing defaults; explicit same-family class roles remain
operator assignments. Plugin-installed global defaults do not establish a
mapping for unrelated families. A mapping is not measurement evidence.

Classed undertaking calls `daily_driver_route_undertaking` alone in its
assistant tool batch before worktree creation or claim. For a mapped family it
selects the exact class within the invoking family and provider, preserving
backend and authentication route across workers and visible fallbacks. A model
or effort change remains `pending` until the next worker assistant response
confirms actual execution. Show informative status during this normal
verification, not an error; do not batch mutations with routing or start work
while pending. An already matching model and effort needs no switch.

Rejecting an inference request does not replace the selected worker's route
with a permanent blocked disposition. After restoring the selected model,
effort, and authentication route, the session can continue without a restart.
A partially applied selection whose restoration failed remains recovery-only;
an ordinary response does not verify that route.

When the known family is absent from the class table, a prominent warning names
the family, required class, and retained provider/model. Work continues
immediately on the invoking model, provider, and effort without confirmation.
The route's execution identity can be verified while class suitability remains
unverified. A missing or cleared class in a mapped family, unavailable or
incompatible target, unknown identity, or actual route violation remains a
configuration gap. Failed preflight must permit explanation and retry without
discarding an existing valid route. The public route `status` remains `pending`,
`verified`, or `blocked`; `capability` separately reports `mapped` or
`unverified`. An absent-family result may also carry a `warning`. Frontier
authorization and OAuth restrictions remain
in force. Independently configured `reviewer`, `scout`, `security-reviewer`,
and `seance` helpers retain their routes. A delegated worker must retain the
undertaking route; otherwise work stays in the invoking session.

After the pull request is ready, or answer-only research is completed and
recorded, call `daily_driver_finish_undertaking({ issue: <positive issue number> })`
before reusing the session for another issue. Do not finish stopped or
incomplete work. Selecting a different issue returns an error without replacing
the existing owner or route; finish the completed undertaking or resume the
existing one before selecting another. A finish call with the wrong issue also
returns an error without changing the existing state.

Omp prefers its extension's in-session switch. A full handoff needs a surface
that can constrain and verify the same route and has one owner. Claude's
host-side Agent SDK model setter is not an agent-callable tool; Codex's
delegation model control is unmeasured. Neither is a reason to invent a switch
tool or assume fallback and authentication constraints. Stop before ownership
when the available surface cannot establish them.

Omp does not relocate a live session when it creates a task worktree. Use the
verified absolute task-worktree paths for shell and file-tool operations.

Omp 18.5.0 supports the user-initiated `/move <path>` for an idle session.
The extension API does not provide direct relocation, so automatic
plugin-driven movement is not available.

The guard rejects primary-checkout and detached-worktree `write` and `edit`
calls. It also denies Git commands that rewrite the primary checkout's files.
Attached feature-worktree mutations remain available. The command parser is
conservative: it rejects unresolved commands and unterminated quotes. A literal
`ln` command takes pathname operands, so paths named `git` or `bash` do not
become executable candidates. Nested substitutions and later commands still
receive the normal checks. Unknown wrappers retain conservative scanning.
The guard does not audit programs launched through `make`, Python or scripts,
so those programs must also stay inside the task worktree.

Use absolute task-worktree paths in file tools. Omp resolves file-tool paths
against the session working directory, not a directory change made by a shell.

## Compatibility limits

- **Omp plugin-directory development:** `omp --plugin-dir <path>` loads skills but not the extension. Use `omp plugin link .` or install the plugin to exercise runtime tools and guards.
- **Claude Code plugin-directory development:** `claude --plugin-dir <daily-driver>` does not fetch marketplace dependencies. Also pass the official Worktrunk plugin directory at `worktrunk/plugins/worktrunk` when testing this route. The shared catalog installs the dependency automatically; Omp and Codex install Daily Driver alone.
- **Codex:** GitHub operations use `gh` in the shell. Codex has no durable wake mechanism or blocking check wait, so `undertake` stops its branch-update cycle at `Ready for review`. Unattended runs cannot access a session client, and `embark` uses local subagents rather than web sessions. Each skill's Codex reference describes its route and limits.

See [Repository setup](bootstrapping-a-repository.md) for installation and hook-trust requirements. See each skill's references for current tool routes; this page summarizes integration rather than replacing those contracts.
