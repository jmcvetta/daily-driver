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

The complete standing constitution reaches root and child sessions on every
harness. Claude Code and Codex use startup hooks for the shared core and
chat-based question routing; Omp's rule provider loads the same core directly.
The source is `rules/constitution.md`, and each route delivers its Markdown
body without the `alwaysApply: true` frontmatter. Task-specific detail stays in
its owning skill; the [existing catalog](../skills/README.md) maps those
workflows.

| Hook | Event | Purpose |
| ---- | ----- | ------- |
| `inject-constitution.py` | `SessionStart` and `SubagentStart` | Delivers the complete core without rewriting delegated prompts. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Blocks the question widget and directs questions to chat. |
| `title-gate.py` | Issue-comment and session-creation events | On Claude Code cloud sessions, holds the first issue comment and dispatch until the session is titled. |

Omp uses `extensions/daily-driver.js`. It blocks the `ask` tool, holds issue and pull-request comments and task dispatch until the session is titled, and provides session-title, reminder, session-info, and attributed GitHub-write tools. `daily_driver_gh_write` attaches live provenance — model, harness-reported provider, harness/version and session — to body-bearing `gh` writes and denies direct Bash writes that bypass it; read-only and non-body GitHub calls keep their existing routes. Explicit `embark` requests require a canonical issue read before dispatch. Omp loads constitution files with `alwaysApply: true` frontmatter.

The exact calls and per-skill differences live in the active harness's reference file. The [architecture notes](notes/0011-two-harnesses-one-skill-tree.md) and [Codex integration note](notes/0016-three-harnesses-one-skill-tree.md) record why the adapters differ.

### Omp notifications

Daily Driver overrides Omp's generic `completion.notify` and `error.notify`
settings to off in each live settings scope at session start, switch, branch,
tree and before agent start. It does not edit persisted YAML. These process
overrides are not restored on refresh (`/reload-plugins`), session end or
cleanup; refresh is not removal. Reminder, asynchronous result, child report,
wait and in-app feedback behavior is unchanged. This policy does not change
other harnesses.

The explicit `daily_driver_notify` tool accepts `attention_required` for an
unresolved human action and `work_complete` for an entire completed operation.
The undertaking finish tool sends its completion automatically after
successful persistence and release. The skill references describe when to
call the tool; an ordinary completion, progress update, recoverable error or
CI wait is not a notification event.

Only a main agent with UI in TUI or RPC mode can deliver. Children and
headless sessions are suppressed, and the public Omp terminal notification
transport may apply its own suppression. The policy records a deduplication
entry on the active session branch before best-effort transport, without
storing the message. It re-reads the branch and serializes requests, so a
repeated semantic key for the same work identity and reason is not replayed,
including after a delivery error. Delivery failure is reported, not retried
as a fresh event.

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

The Omp installation defines `mechanical`, `routine`, `intermediate`,
`complex` and `frontier` task roles. Where no operator assignment exists, the
extension supplies defaults. The roles describe capability for the initial
selection; the defaults require configured credentials. Use `/model` → Roles
to assign models. Existing `omp_configs/` files remain process overlays;
assignments present at startup take precedence, and later edits may require an
Omp restart.

The Omp adapter admits explicit top-level frontier selection and native
`^provider/model` consultations as ordinary model choices. They do not change
the assigned worker or issue class. Native `^provider/model` delegation uses
the active branch's `model_mention` binding. Retry-fallback and prewalk journal
entries are automatic transitions. Omp 18.15.0 cannot identify every caller of
the top-level model setter. This adapter is not a security boundary against
arbitrary trusted extensions.

`dailyDriver.modelClassRoutes` is an array of entries with `referenceModel`
and `classes`, for example `{ referenceModel: "provider/model", classes: {
routine: "provider/variant:high" } }`. Omp resolves the reference
through its model catalog to identify the family; that family mapping applies
regardless of the reference model's provider. Omp resolves the configured
class target to the same model identity in the invoking provider and family,
then retains the invoking provider. Ambiguous or unavailable targets are route
gaps. Explicit class roles remain valid only in the invoking provider and
family. The built-in OpenAI Codex entry preserves existing defaults, and the
DeepSeek V4.1 Flash entry maps only its measured mechanical and routine
classes. Plugin-installed global defaults do not establish a mapping for
unrelated families. A mapping is not measurement evidence.

An unset route configuration uses the registered default, including when Omp
clones settings for a task. An explicit empty array stays empty; malformed
explicit values are rejected rather than replaced with defaults.

Classed work selects an initial route once, before the task worktree and
claim. For a mapped family, that selection fixes the class and effort; after
it, worker, provider, effort and fallback choices are not restricted by the
router, and independent specialist routes remain separate. When the known
family is absent from the class table, Omp warns with the family, required
class and retained model, then continues on the invoking route without
confirmation. A class omitted from a mapped family continues the same way. In
both cases class suitability stays unverified, and host-owned OAuth
restrictions remain in force. An explicitly cleared (`null`) class or an
unavailable initial target is a configuration gap that needs repair; unknown
identity and later operator selections are not. A `selected` status records
the initial selection, not the observed execution identity or class
suitability. The finish call releases ownership and sends its completion
notice; exact calls, status fields and handoff rules are in the
[undertake reference](../skills/undertake/references/omp.md).

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
Transcript, worktree, branch, and unfinished task state stay intact. A new
undertaking requires a fresh initial selection. Repeated cancellation with no
owner is a no-op. This command does not replace the workflow's stop handoff.

Omp creates a task worktree without relocating the live session. The
extension's guard rejects primary-checkout and detached-worktree `write` and
`edit` calls, and denies Git commands that rewrite the primary checkout's
files; attached feature-worktree mutations remain available. The command
parser is conservative: it rejects unresolved commands and unterminated
quotes, scans nested substitutions and unknown wrappers, and does not audit
programs launched through `make`, Python or scripts, so those programs must
also stay inside the task worktree. File tools resolve against the session's
working directory rather than a shell directory change, so use absolute
task-worktree paths. The user-initiated `/move <path>` can move an idle
session; the extension API has no automated relocation. The
[task-worktree reference](../skills/task-worktree/references/omp.md) owns the
worktree and path route.

## Compatibility limits

- **Omp plugin-directory development:** `omp --plugin-dir <path>` loads skills but not the extension. Use `omp plugin link .` or install the plugin to exercise runtime tools and guards.
- **Claude Code plugin-directory development:** `claude --plugin-dir <daily-driver>` does not fetch marketplace dependencies. Also pass the official Worktrunk plugin directory at `worktrunk/plugins/worktrunk` when testing this route. The shared catalog installs the dependency automatically; Omp and Codex install Daily Driver alone.
- **Codex:** GitHub operations use `gh` in the shell. Codex has no durable wake mechanism or blocking check wait, so `undertake` stops its branch-update cycle at `Ready for review`. Unattended runs cannot access a session client, and `embark` uses local subagents rather than web sessions. Each skill's Codex reference describes its route and limits.

See [Repository setup](bootstrapping-a-repository.md) for installation and hook-trust requirements. See each skill's references for current tool routes; this page summarizes integration rather than replacing those contracts.
