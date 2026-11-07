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

## Sensitive handoff examples

The [constitution](../rules/constitution.md#non-negotiables) owns the headless
default and protected-file handoff contract. These are example user notices
after creating an owner-only file with POSIX mode `0600` outside the repository,
build contexts and published artifacts. Paths are illustrative, not deliveries.

- **Workstation, existing local access confirmed:** “On your workstation
  `atlas`, read `/home/alex/.local/state/daily-driver/github-login.txt` in your
  existing local session. Use its GitHub device-login instructions to approve
  the pending login. I have not opened a terminal window.”
- **Cloud, existing SSH access confirmed:** “On remote host `builder-7`,
  read `/home/alex/.local/state/daily-driver/openai-login.txt` through your
  existing authorized SSH connection as `alex`. Use its OpenAI device-login
  instructions to approve the pending login. This path is on `builder-7`,
  not your laptop.”
- **No existing delivery route:** “The protected file is
  `/home/agent/.local/state/daily-driver/github-login.txt` on remote host
  `worker-9`. No existing authorized channel gives you access to that
  filesystem, so the handoff is not delivered. I need an authorized way for
  you to read that file. Independent permitted engineering continues.”

These notices disclose neither credentials nor device codes. Device approval
is the user's authentication action; it does not renew task approval.

## Task continuation and approval evidence

The constitution requires agents to diagnose ordinary failures, preserve
applicable approval, and finish independent permitted work before pausing.
`undertake` owns the detailed escalation contract. The rule also applies to
ordinary repository work.

On Omp, `extensions/task-state.mjs` registers `daily_driver_task_state` and
uses `session_stop` for bounded correction. Task scope, source-anchored
authorization, tool evidence and correction counts live in private,
active-branch session entries. The adapter restores a compact handoff during
context preparation and compaction. Read `xd://daily_driver_task_state` in Omp
for the action records, source discovery, exact-quote limits and examples.
`status` returns bounded source excerpts; retrieval by source ID returns the
original authority source or retained tool evidence. Tool input/output
payloads have bounded previews, truncation metadata and a fingerprint; the
adapter does not persist a second full copy of every file or command result.

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

The Omp adapter admits explicit top-level frontier selection without changing
the assigned worker, issue class, approval record, or verification state.
Consultation tools remain available, including reporting while the worker is
pending or recovery-only. This is not implementation authorization.

Native `^provider/model` delegation uses the active branch's `model_mention`
binding. The spawn hook pins that exact model despite model overrides; each
child request must retain its model, backend, and authentication route.
The binding does not authorize unrelated children or automatic fallback.
Rewind removes branch-local permission; a resumed consultation retains its
saved exact-model constraint without becoming an undertaking worker.

Retry-fallback and prewalk journal entries remain automatic transitions, not
operator approval. Agent-controlled undertaking selection and observed worker
dispatch still require the configured class and bounded frontier approval.
Omp 18.15.0 cannot identify every caller of the top-level model setter.
This adapter is not a security boundary against arbitrary trusted extensions.

`dailyDriver.modelClassRoutes` is an array of entries with `referenceModel`
and `classes`, for example `{ referenceModel: "provider/model", classes: {
implementation: "provider/variant:high" } }`. Omp resolves the reference
through its model catalog to identify the family and provider. A family entry
does not authorize a different provider. The built-in OpenAI Codex entry
preserves the existing defaults; explicit same-family class roles remain
operator assignments. Plugin-installed global defaults do not establish a
mapping for unrelated families. A mapping is not measurement evidence.

An unset route configuration uses the registered default, including when Omp
clones settings for a task. An explicit empty array stays empty; malformed
explicit values are rejected rather than replaced with defaults.

Classed undertaking calls `daily_driver_route_undertaking` before worktree
creation or claim. For a mapped family, admission resolves the selected class
and visible automatic candidates once. It records their concrete backend,
authentication route and effort. Dispatch and observed worker checks reuse
that decision. Visible incompatible retry and prewalk candidates fail before
dispatch. Independent specialist routes remain separate.

Call routing alone and report pending verification as normal progress. These
are workflow instructions, not conversation-wide runtime failures. The runtime
still reserves a routing response's whole tool batch before admitting sibling
mutations. A selected model or effort change stays `pending` until a successful
response follows an admitted request from that worker. Rejected requests,
consultations, error responses and cancelled responses do not verify it.

Omp 18.16.0 exposes expanded child patterns at `before_subagent_spawn`. It does
not expose a veto before every retry or prewalk model transition. The adapter
therefore retains a final request guard for transitions that dispatch cannot
guarantee. Agent-definition prewalk targets and later configuration changes
also require this guard. It rejects unauthorized inference, not host controls.
Local inspection, cancellation and model restoration do not require worker
verification.

A disposable loopback-provider experiment on Omp 18.16.0 distinguished the
selected route, the resolved retry fallback and actual HTTP requests. The host
reported `retry_fallback_applied` for an incompatible model; its request never
reached the provider. Local `get_state`, `abort` and `set_model` remained
available. A restored turn and a reloaded session completed on the original
route. This is boundary evidence, not evidence of model-class suitability.

Rejecting a request does not replace the stored selected route with a blocked
disposition. A partially applied selection whose restoration failed remains
recovery-only; an ordinary response cannot certify it.

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

### Local undertaking recovery

Omp registers `/undertaking status` and `/undertaking cancel <issue>` as host
commands. They do not send a model request. They remain available after a
rejected inference request or a saved-route restoration error.

Status separates configured model and effort from the host selection and
last observed execution identity. It reports the authentication route category,
ownership, state, and last rejection reason without credential identities.
If a malformed record has no recoverable issue, status reports
`cancelOwner: invalid`; `/undertaking cancel invalid` explicitly cancels that
record in the current session.

Cancellation requires the exact current owner. It aborts and waits for local
work before releasing only the undertaking's OAuth lease. It retires pending
handoffs and revokes owned children. Running children retain their restrictions
until shutdown and cannot resume after reload. Other sessions and operator-owned
leases remain unchanged.

Cancellation writes a schema-2 `cancelled` lifecycle record, not a completion
record. Existing schema-1 active and completed records remain readable.
Transcript, worktree, branch, approval evidence, and unfinished task state stay
intact. A new undertaking requires normal admission. Repeated cancellation with
no owner is a no-op. This command does not replace the workflow's stop handoff.


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
