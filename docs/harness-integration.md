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

## Task contracts, continuation and approval evidence

`extensions/task-state.mjs` owns task transitions for all three harnesses.
`extensions/task-contract.mjs` owns the versioned contract representation.
Adapters bind native input, persistence, tools, compaction and cancellation to
that controller. They do not implement separate approval policies.

Clear repository work captures a contract without asking for approval again.
An ordinary question creates none. User requirements, workflow instructions,
tool observations and agent interpretations remain separate source classes.
An issue body, a delegated prompt or a copied approval is not user authority.

### Contract and execution state

Schema version 1 contains:

- `contractId`, `taskId` and monotonic `revision`.
- `objective`, `scope`, `exclusions` and `constraints`.
- `criteria`, each with a stable `id`, `description` and original `sourceRefs`.
- `requiredEvidenceKinds`, `requiredReviewKinds` and `approvalRequirements`.
- `sourceRefs` with the retained `sourceId`, exact quote, canonical source
  class, native origin and captured source version or observation fingerprint.

Unknown fields are `null`. They do not mean empty, approved or fulfilled.
Initial capture retains the request as criterion `request`. Ground the
remaining fields and criteria in the issue/request version actually read.
Keep the original request criterion when adding detailed issue acceptance.
The issue's observation fingerprint identifies the captured version; a later
issue read is another source, not a replacement for that contract.

`contractHistory` retains each prior revision, its change and applicable
source references. `plan` is separate mutable execution state. Updating a plan,
retrying or compacting does not create a contract revision. Material amendments
require a later applicable original user decision. Removing a criterion also
requires its ID and the user-authorized reason. An issue edit alone cannot
delete an unmet criterion.

The first explicit `begin` may bind execution labels to the captured request.
It does not infer unknown scope. A later `begin` cannot rewrite that binding or
the contracted scope. Starting another task requires `newTask: true` and a
fresh original user source. `resume` selects an existing contract by
`contractId` when needed and preserves its correction allowance.

### Task-state operations

All routes accept `action` and an optional JSON-string `record`. `status`
returns current state, retained task identities and bounded source previews.
`status` with `{sourceId}` retrieves the retained original source or bounded
tool observation. It does not recover omitted tool-output bytes.

- `contract`: `{expectedRevision, change, sourceRefs, contract: {...}}`.
  Supply only changed contract fields. A material amendment also supplies
  `authoritySource`. A removal supplies `removedCriteria: [{id, reason}]`.
  Changing bound `operation` or `target` belongs to this amendment, not `begin`.
- `plan`: `{summary, ...executionDetails}`. This changes no contract revision.
- `handoff`: returns the contract, history, current plan, unresolved criterion
  IDs, authority locators and correction identity/count. It grants no approval.
- `resume`: `{source: {sourceId, quote}, contractId?}`. A cancelled task needs
  fresh original user input. Resume does not renew an exhausted allowance.
- `authorization`, `blocker` and `complete` retain the
  [existing evidence record fields](../skills/undertake/references/omp.md#task-evidence-state).
  `complete` remains a report. It does not verify acceptance.

References establish provenance, not the meaning of arbitrary approval prose.
Read the original scope, conditions, revocations, expiry and fresh-confirmation
requirements before acting. The records do not replace harness permissions or
safety restrictions.

### Persistence and delegation

Omp uses private, active-branch native session entries. Claude Code and Codex
use `hooks/task-state.py` and `hooks/task-state.mjs` with the same controller.
Their private ledgers live under `CLAUDE_CONFIG_DIR` or `CODEX_HOME`, falling
back to `~/.claude` or `~/.codex`, in `daily-driver-task-contracts/`.
Directory and ledger permissions are private. Native session/actor identities
select separate ledgers. A process lock serializes updates; staged writes,
`fsync` and atomic replacement preserve concurrent updates and crash recovery.
No ledger or transcript is written to the repository.

Native child adapters inherit contract identity, revision, criterion IDs and
authority locators. Delegated input remains an interpretation. Hook-harness
children resolve original sources from the parent's private ledger, not from
copied prose. An Omp handoff retains native session/source locators; a source
unavailable on the child's branch remains `source-unavailable`, not approved.
The existing workflow handoffs carry those locators across sessions. Never
publish private quotes in a GitHub handoff.

Legacy Omp records migrate explicitly on first access. Existing ledger entries,
authorizations, cancellation and correction history remain. Missing contract
fields stay unknown until sourced. Historical completion stays reported, not
verified.

An unsupported unfinished stop receives at most two corrective continuations
per unchanged observed condition. Process restart, duplicate native events,
record relabelling, plan changes and delegation do not renew that allowance.
Cancellation suppresses corrections. Exhaustion records an execution failure
without another model turn. A missing task-state tool is a capability limit,
not missing user approval; adapters do not expand tool permissions.

### Hook-harness boundary

Claude Code requires native mods support: terminal version 2.1.287 or later.
The measured version is 2.1.316. `.claude-plugin/plugin.json` adds
`hooks/task-state-claude.json`; Claude still loads common `hooks/hooks.json`.
The mod uses engine-stamped `prompt.submit.origin`, native tool registration,
`classic.Stop` and `turn.complete.isAborted`. A settings
`UserPromptSubmit` hook alone cannot distinguish user, scheduler and peer
input. The adapter does not use that unsafe classification.
SDK-host requests can create interpreted contracts, but are not user approval.

Codex uses `.codex-plugin/plugin.json` to load the common hooks and
`hooks/task-state-codex.json`. Only the Codex file registers `Interrupt`.
Claude never parses that event. The model receives a task-state command bound
to its native session and actor; it supplies `{action, record}` on stdin.
The implementation requires Python 3, POSIX process locks and Node.js.
Trust the installed hooks through Codex's supported hook review.

In the measured Codex CLI 0.160.0, a blocked `Stop` creates another model
request and retains `stop_hook_active`, but does **not** emit
`UserPromptSubmit`. The adapter does not read unstable transcript fields.
Native delegated prompt events carry `agent_id`/`agent_type` and retain the
root `session_id`; they are interpretations, not fresh user authority.
After compaction, the documented `SessionStart(source: compact)` route
restores the contract before the next request. `PostCompact` has no supported
additional-context output and is not used as a substitute.

### Installed-runtime capability checkpoint

The bounded checkpoint on 2026-11-02 used no external model:

| Harness | Registration and local response route | Observed native events |
| --- | --- | --- |
| Omp 18.15.0 | Installed extension, scripted loopback provider, RPC | Original request and approval, bounded corrections, process resume and abort; `scripts/check-omp-task-state-live.py` passed. |
| Claude Code 2.1.316 | Task-private npm installation; `--plugin-dir` mod; local `turn.step` response fixture | Terminal `composer` input, a separate plugin's non-user input, retained source/criterion after actual process resume, registered tool execution, and Esc aborting a pending stop correction with `turn.complete.isAborted: true`. |
| Codex CLI 0.160.0 | Reviewed task-private hooks; local Responses provider; `exec` and `exec resume` | Original prompt, real tool execution, Stop-generated request without a prompt-source event, SIGINT during a pending Stop firing `Interrupt`, and process resume retaining cancelled state and correction count 2. |

The workstation's Claude Code 2.1.267 is too old for the mod route. The
task-private 2.1.316 install did not change shared configuration or credentials.
The Codex app-server route executed model/tool requests but did not execute
these hooks in this environment, even when `hooks/list` reported them trusted.
That route is not claimed as proven. CLI hook registration is the measured
route.

These native-event observations establish the adapter route. Offline
controller/adapter regressions run in the existing `check-omp-extension`
suite. They do not replace installed-runtime evidence or prove that a model
will honor arbitrary approval prose.

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
