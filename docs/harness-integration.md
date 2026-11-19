# Runtime integration and compatibility

Daily Driver shares skill instructions and a marketplace catalog across Omp, Claude Code and Codex. Tool calls live in each skill's `references/` directory. Runtime adapters handle the differences between harnesses.

## Support levels

Omp is the supported harness. The required eval arms are the `omp-*.yaml`
experiments that `make evals-run-omp` runs, and the live runtime checks in CI
cover Omp alone.

Claude Code and Codex are best effort. Their plugins, hooks and per-skill
`references/claude.md` and `references/codex.md` routes are written and
maintained on each change, and their eval arms stay in `evals/` for manual use,
but nothing gates on them. A Claude Code or Codex bug is accepted and fixed
best effort; the fix gets a targeted eval kept under `evals/experiments/` so it
can be rerun later, and that eval never joins the required set.

CI keeps its static checks: they cover the shared skill tree and the Omp and
Claude plugin manifests. The Codex manifest is not validated. The live runtime
checks remain Omp-only.

Claude Code repository instructions live in `.claude/CLAUDE.md`, which imports
the root `AGENTS.md`. This project context is distinct from plugin-delivered
skills and the constitution injected by runtime hooks.

## Runtime integration

Claude Code and Codex use startup hooks for the shared core and chat-based
question routing. Omp's rule provider loads the same core directly.

The source is `rules/constitution.md`. Each route delivers its Markdown body
without the `alwaysApply: true` frontmatter. Task-specific detail stays in its
owning skill; the [existing catalog](../skills/README.md) maps those workflows.

| Hook | Event | Purpose |
| ---- | ----- | ------- |
| `inject-constitution.py` | `SessionStart` and `SubagentStart` | Delivers the complete core without rewriting delegated prompts. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Blocks the question widget and directs questions to chat. |
| `title-gate.py` | Issue-comment and session-creation events | On Claude Code cloud sessions, holds the first issue comment and dispatch until the session is titled. |

Omp uses `extensions/daily-driver.js`. It blocks the `ask` tool, holds issue and pull-request comments and task dispatch until the session is titled, and provides session-title, reminder and session-info tools. Explicit `embark` requests require a canonical issue read before dispatch. Omp loads constitution files with `alwaysApply: true` frontmatter.

The exact calls and per-skill differences live in the active harness's reference file. The [architecture notes](notes/0011-two-harnesses-one-skill-tree.md) and [Codex integration note](notes/0016-three-harnesses-one-skill-tree.md) record why the adapters differ.

## Standing instruction delivery

The complete standing constitution is delivered directly to root and child
sessions. Task-specific workflows remain in the skill catalog.

The former `daily_driver_task_state` tool and Claude and Codex task-state
commands are removed. Work directly from the user's request and issue; use
the existing review and validation workflows to verify and report the result.
Existing private task-state records are not read or deleted.

## Sensitive handoff examples

The [constitution](../rules/constitution.md) owns the headless
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

## Omp task roles and worktrees

The Omp installation defines `mechanical`, `implementation`, `integration`,
`reasoning` and `frontier` task roles. Where no operator assignment exists, the
extension supplies defaults. Frontier is limited to explicitly approved, bounded research
or planning; ordinary implementation uses a non-frontier route unless the user
separately authorizes that exception. The defaults require configured
credentials. Use `/model` → Roles to assign models. Existing `omp_configs/`
files remain process overlays; assignments present at startup take precedence,
and later edits may require an Omp restart.

An operator's manual escalation during a failing task authorizes the
consultation. Follow `undertake`'s *Manual frontier escalation* policy: repair
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
through its model catalog to identify the family; that family mapping applies
regardless of the reference model's provider. Omp resolves the configured
class target to the same model identity in the invoking provider and family,
then retains the invoking provider. Ambiguous or unavailable targets are route
gaps. Explicit class roles remain valid only in the invoking provider and
family. The built-in OpenAI Codex entry preserves existing defaults; plugin-
installed global defaults do not establish a mapping for unrelated families.
A mapping is not measurement evidence.

An unset route configuration uses the registered default, including when Omp
clones settings for a task. An explicit empty array stays empty; malformed
explicit values are rejected rather than replaced with defaults.

Classed undertaking calls `daily_driver_route_undertaking` before worktree
creation or claim. For a mapped family, initial admission resolves the selected
class and visible automatic candidates once. It records their concrete backend,
authentication route and effort. Dispatch and observed worker checks reuse
that decision. Visible incompatible retry and prewalk candidates fail before
dispatch. Independent specialist routes remain separate.

Report the selected initial route as progress; status `selected` records
selection, not execution identity or class suitability. The runtime reserves a
routing response's whole tool batch before admitting sibling mutations. Visible
incompatible retry and prewalk candidates fail before dispatch.

Agent-initiated work remains subject to the class, frontier authorization, and
route-integrity requirements as workflow policy; the runtime does not enforce a
continuing request-route guard. Operator model, provider, and effort changes
after admission remain permitted and must not be blocked or reversed.

Provider transport can rewrite the request API model, endpoint, and headers
without changing the selected provider/model. This is distinct from the
operator's model choice; transport integrity belongs to the host/provider.
Native consultations and recovery explanations remain separate.

When the known family is absent from the class table, a prominent warning names
the family, required class, and retained provider/model. Work continues
immediately on the invoking model, provider, and effort without confirmation.
The route's execution identity can be reported separately from class suitability.
A missing or cleared class in a mapped family, unavailable or incompatible
initial target, unknown identity, or observed agent-route mismatch requires
explanation and repair; later operator selections are not route violations.
Failed preflight must permit explanation and retry without discarding an
existing valid route. Route status is `selected` after initial selection;
malformed or cancelled state can report `blocked`. Neither status alone
establishes observed execution identity or class suitability. An absent-family
result may also carry a `warning`. Frontier authorization and OAuth restrictions
remain in force. Independently configured `reviewer`, `scout`,
`security-reviewer`, and `seance` helper routes are selected separately from
issue class routing; this does not define their cancellation ownership. A
delegated worker must retain the undertaking route; otherwise work stays in the
invoking session.


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
rejected inference request or an operator model, provider, or effort change.
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
