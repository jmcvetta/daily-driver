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

Omp uses `extensions/daily-driver.js`. It blocks the `ask` tool, holds issue and pull-request comments and task dispatch until the session is titled, and provides session-title, reminder, session-info, and attributed GitHub-write tools. `daily_driver_gh_write` attaches live provenance — model, harness-reported provider, harness/version and session — to body-bearing `gh` writes and denies direct Bash writes that bypass it; read-only and non-body GitHub calls keep their existing routes. Explicit `embark` requests require a canonical issue read before dispatch; while startup is pending, only the documented literal title-recovery forms and bounded issue-reporting routes are admitted, and they do not release the barrier. Omp loads constitution files with `alwaysApply: true` frontmatter.

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

The [constitution](../rules/constitution.md) owns the protected-file handoff
contract. These are example user notices
after creating an owner-only file with POSIX mode `0600` outside the repository,
build contexts and published artifacts. Paths are illustrative, not deliveries.

- **Workstation, existing local access confirmed:** “On your workstation
  `atlas`, read `/home/alex/.local/state/daily-driver/github-login.txt` in your
  existing local session. Use its GitHub device-login instructions to approve
  the pending login.”
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

Omp's effective class role is the only undertaking selector. It applies the
configured model/provider and effort together, including cross-provider
assignments, from live global/project settings, CLI overlays and Roles UI
edits. Installed defaults govern only absent assignments; explicitly cleared
roles stay cleared. `dailyDriver.modelClassRoutes` no longer controls selection.
Express desired routes through Omp class roles instead; the plugin does not
rewrite existing configuration files. Helper roles and role tags remain separate.

Classed work attempts selection once before task worktree and claim. Matching
model and effort need no setters. A suffix selects effort; absent or `inherit`
preserves invoking effort, and other supported values use host semantics.
Later operator model/provider/effort choices always win. Same-issue re-entry,
resume, later role edits, retries, fallback and worker dispatch never reapply
selection. There is no atomic model-plus-effort API: pending setters cannot
promise atomicity. On failure, restore only mutations still attributable to the
selector and report the actual state if restoration fails or is unsafe.

Missing, cleared, invalid or unavailable roles, credentials, controls, rejected
switches and persistence failures are informational. The result names the
class, attempted target, failure and actual route; ordinary work continues
immediately without confirmation or repair. This does not conceal real
provider failures. Explicit abort/cancellation remains stopped. Attempted,
selected and observed model facts remain distinct and do not establish
benchmark suitability.

A new issue may start without a finish ceremony. Previous active work remains
cancellable and is not silently completed or abandoned. Finish records only
truthful completion and sends its notification once. Exact calls and status
fields are in the [undertake reference](../skills/undertake/references/omp.md).

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

Cancellation requires an exact owner from the status `owners` list, including
older active issues. It aborts and waits for owned work, retires pending handoffs
and revokes owned children without changing unrelated sessions or host-owned
authentication restrictions. Retired children cannot restart after reload.

Schema 4 separates selection history from cancellation ownership. Schemas 1–3
and legacy implementation/integration/reasoning class tokens remain readable;
resume never restores a historical route. Malformed metadata has local recovery
and cannot deny ordinary work or override cancellation tombstones.
Transcript, worktree, branch, and unfinished task state stay intact. A new
undertaking requires a fresh initial selection. Repeated cancellation with no
owner is a no-op. This command does not replace the workflow's stop handoff.

Omp creates a task worktree without relocating the live session. Git or the
user's chosen tool can create any dedicated registered non-primary worktree;
Worktrunk installation and sibling placement are not isolation requirements.
Detached non-primary file edits are allowed; recover a task branch at the
detached HEAD before committing. Coordinate same-worktree and shared-ref
writers, retain collision detection and non-force pushes, and preserve all
existing user work. Ordinary commits to `master` remain prohibited.

The extension keeps canonical primary-checkout `write`/`edit` diagnostics and
targeted primary Git rewrite protection, including detached primaries and
recognizable later Git commands after an opaque invocation. Verified
non-primary task worktrees allow expanded executables, nonliteral `eval` and
shell input. Primary/unknown directories and unplaceable Git targets remain
conservative. Arbitrary programs, eval kernels and extension code are not
filesystem-contained; this is not a sandbox.
File tools resolve against the session directory, not an earlier shell cwd;
use absolute task paths. The user-initiated `/move <path>` may move an idle
session. The [task-worktree reference](../skills/task-worktree/references/omp.md)
owns the execution route.

### Worktree protection scope and limitations

The user clarified [#1036](https://github.com/jmcvetta/daily-driver/issues/1036):
dedicated-worktree discipline and targeted ordinary-accident protection are
the intended scope. Universal OS containment is not an acceptance prerequisite.
The following earlier capability probes document existing limitations, not
regressions introduced by admitting ordinary feature commands or a merge gate.

Bounded actual-route evidence, 2026-11-24: Omp 19.1.1 on Linux
7.0.0-43-generic, x64. A disposable repository had a primary on `master`,
a dirty tracked file, an untracked user file, and an external feature worktree
whose path contained spaces. No real project primary was a mutation target.

| Actual Omp route | Observed result |
| --- | --- |
| `write` to a new disposable-primary file | Blocked with canonical primary diagnostics; no file created. |
| `bash` in the feature worktree → `python3 -c` → primary file | Created the probe file; no filesystem containment. |
| Same interpreter → child `python3` → feature symlink → primary file | Created the probe file through the symlink. |
| Python `eval` kernel → `Path.write_text` → primary file | Created the probe file; outer tool checks did not contain it. |

After the probes, the primary symbolic branch, index bytes, dirty tracked
bytes and pre-existing untracked bytes matched their initial snapshots.
Only new, named probe files were created. These are negative capability
results, not a successful prevention test. Existing differential Git cases
remain bounded parser regressions, not proof of arbitrary-program isolation.

The inspected CLI help exposes cwd/workspace/tool selection, not a filesystem
boundary switch. The installed extension API exposes `tool_call` admission,
`exec` and native file-write/delete permission-error fallback handlers.
Those fallback handlers assume an embedding host already enforces a sandbox;
they do not establish one for the Omp process, eval kernels or subprocesses.
Installing or wrapping only a shell command would leave the observed eval
route outside the boundary.

No universal boundary is claimed for native file tools, bash children, eval
kernels/subprocesses, extension operations, delegated workers, existing open
descriptors, hooks or shared refs. Dedicated worktrees do not isolate shared
Git metadata or coordinate concurrent writers by themselves. Follow task
ownership, branch recovery and user-work preservation rules.

The differential Git fixtures retain recognizable primary-rewrite prevention
assertions and explicitly exercise opaque dynamic programs as limitations.
The offline `check-omp-worktree-live.py` fixture drives actual Omp file tools
and bash through a local scripted provider, including expanded Python/pytest,
nonliteral eval, scripts, external/detached worktrees, branch recovery and
dirty-primary preservation. No live model or third-party service is used.

## Compatibility limits

- **Omp plugin-directory development:** `omp --plugin-dir <path>` loads skills but not the extension. Use `omp plugin link .` or install the plugin to exercise runtime tools and guards.
- **Claude Code plugin-directory development:** `claude --plugin-dir <daily-driver>` does not fetch marketplace dependencies. Also pass the official Worktrunk plugin directory at `worktrunk/plugins/worktrunk` when testing this route. The shared catalog installs the dependency automatically; Omp and Codex install Daily Driver alone.
- **Codex:** GitHub operations use `gh` in the shell. Codex has no durable wake mechanism or blocking check wait, so `undertake` stops its branch-update cycle at `Ready for review`. Unattended runs cannot access a session client, and `embark` uses local subagents rather than web sessions. Each skill's Codex reference describes its route and limits.

See [Repository setup](bootstrapping-a-repository.md) for installation and hook-trust requirements. See each skill's references for current tool routes; this page summarizes integration rather than replacing those contracts.
