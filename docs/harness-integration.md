# Runtime integration and compatibility

Daily Driver shares skill instructions and a marketplace catalog across Omp, Claude Code and Codex. Tool calls live in each skill's `references/` directory. Runtime adapters handle the differences between harnesses.

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

## Core delivery and workflow retrieval

The always-loaded core retains production and dangerous-command prohibitions,
approval authority, cancellation, isolation, evidence, and execution boundaries.
Coding, testing, script and commit discipline live in `provenance`. Validation
and recurring CI policy live in `pr`. Delegation, manual frontier return and
unfinished-stop detail live in `undertake`'s execution policy. Policy-only reads
do not create an issue or PR. `task-worktree` and `issue` retain their existing
isolation and bug-reporting responsibilities. The core and skill descriptions
require retrieval before action, including ordinary work without slash commands.
Reuse context still present; reassess after transitions, resume and compaction.
Delegated workers retrieve their own required workflows.

`SubagentStart` supplies standing context on both hook harnesses. The obsolete
`PreToolUse` prompt rewrite is removed; it duplicated Claude child context and
did not reach the former Codex delegation route. Native Codex 0.160.0 child
delivery is now observed with a local scripted Responses provider. Its function
call uses `namespace: "multi_agent_v1"` and `name: "spawn_agent"`.

### Measured limits

The delivery suite bounds the rendered core to 9,000 UTF-8 bytes. Do not raise
that budget or lengthen the core without a new installed-runtime proof of
complete delivery. Reintroducing a preview is not a context saving. Restore or
relocate any control needed by a failing comparison; do not weaken the rubric.
Dated delivery measurements — the initial and reconciled baselines, the
compact-core captures, and the adapter proofs — live in
[runtime-integration-measurements.md](runtime-integration-measurements.md);
link to its latest applicable checkpoint instead of inlining new experiments.

Retrieval is not free: read only the relevant policy when the issue sequence is
not needed, retain retrieved context instead of repeating reads, and report
actual returned context, truncation and repeated reads in behavioral records.

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
- Optional criterion `verification`: `{kinds, toolName, input, subject}`.
  Supported kinds are `command`, `check`, `judgment`, `approval` and `report`.
  `subject` declares `{kind: "repository", root}` or
  `{kind: "artifact", path}`. For command or check evidence, `toolName` is
  nonblank and `input` is the exact tool input object, not a command string.
  For example, use `{kinds: ["command"], toolName: "bash", input: {command:
  "make check", cwd: "/path/to/task-worktree"}, subject: {kind: "repository",
  root: "/path/to/task-worktree"}}`. Bash supplies command evidence, not check
  conclusions. Ground the selector after selecting the execution worktree and
  before the operation runs. An unknown verification contract cannot pass.

Unknown fields are `null`. They do not mean empty, approved or fulfilled.
Initial capture retains the request as criterion `request`. Ground the
remaining fields and criteria in the issue/request version actually read.
Keep the original request criterion when adding detailed issue acceptance.
The issue's observation fingerprint identifies the captured version; a later
issue read is another source, not a replacement for that contract. A failed
initial grounding that replaced the auto-captured request criterion recovers
without new approval: retain `request`, append sourced acceptance criteria,
populate the unknown fields, and declare each criterion's verification before
execution. Replacing or removing `request` still requires the later applicable
original user decision. A contract revision after execution requires newly
bound evidence under the revised contract.

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
- `authorization`: `{id, kind: "user" | "workflow", operation, target,
  source: {sourceId, quote}, limits, conditions, expiresAt?, supersedes?,
  revokes?, freshConfirmation?}`. The source must resolve to original user
  input or workflow instructions of the same kind.
- `blocker`: `{operation, target, kind: "external" | "authorization" |
  "safety" | "execution", evidence: [{sourceId, quote}], authorizationIds: [],
  routes: [{route, disposition: "failed" | "prohibited" | "unavailable",
  evidence: {sourceId, quote}}], externalContribution,
  independentWork: {pending: [], completed: []}, resume}`.
- `evidence`: `{id, taskId, criterionId, contractRevision, subject, source,
  kind, result, judgment?, requirement?, supersedes?}`. `source` is a retained
  observation reference. Copy `subject` from its execution binding, not from
  the current head. Results are `passed`, `failed` or `unresolved`.
  A judgment carries `{reviewer, rationale, artifacts}`. An approval also
  names its contract `requirement`. An explicit supersession retains the old
  evidence for audit and replaces only the same criterion, kind and subject.
- `receipt`: renders current criterion dispositions, supporting references,
  artifact identities, unknowns, decisions, risks and outstanding approvals.
  Rendering does not publish, approve or complete the task.
- `complete`: `{summary}`. Requires current evidence for every criterion and
  declared evidence/review/approval requirement. It records `verified-complete`
  only when evidence accounting passes. It does not prove arbitrary semantics.

References establish provenance, not the meaning of arbitrary approval prose.
Read the original scope, conditions, revocations, expiry and fresh-confirmation
requirements before acting. The records do not replace harness permissions or
safety restrictions.

On Omp, read `xd://daily_driver_task_state` for the action records, defaults,
source discovery, exact-quote limits and an example sequence. Tool
input/output payloads have bounded previews, truncation metadata and a
fingerprint; the adapter does not persist a second full copy of every file or
command result.

Execution bindings capture task, session, contract revision and subject before
the operation starts. A late result retains that binding. Repository evidence
names the exact worktree root, commit and dirty-state distinction; executing
in a different checkout cannot establish evidence for the selected worktree.
Dirty repository evidence cannot establish completion. File artifacts use
SHA-256 content identities.
Contract revisions and changed subjects make old evidence stale without
deleting it. Check responses must include actual conclusions and the exact
checked `headRefOid`, or `artifactDigest` for a file. A successful tool
transport is not a check pass. Commands require a native exit status; shell
output that merely prints a success claim is not an exit status.

Subjective acceptance uses attributed judgments with rationale and inspected
artifact references retained in the review observation. Each artifact reference
must contain the captured commit or content digest. An agent cannot invent
attribution or rationale that the source does not contain. Attribution and
prose sufficiency still need review against that observation. Agent reports
remain a separate evidence kind and cannot establish a pass. Receipt consumers
must distinguish these kinds and redact sensitive commentary and local paths.
Do not publish retained source quotes. Reuse the receipt inside existing
PR details and handoffs instead of maintaining a second evidence ledger.

`status` with a source ID can recover a truncated Omp observation from its
existing native tool-result entry when the full-output fingerprint matches.
It does not replay the tool or create another transcript store. If the native
entry or decisive result is unavailable, the criterion remains unresolved.
Hook ledgers retain bounded observations and cannot recover omitted bytes.

The native stop gate also rejects omitted completion calls. A summary or
printed “done” does not settle a task. Rejected completion leaves it active.
The existing two-correction bound still applies. Explicit cancellation, abort,
an evidenced external wait and correction exhaustion remain possible without
recording verified completion. Historical `reported-complete` records retain
their original status; they are never upgraded by migration.

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
copied prose. On Claude Code the mod reads the engine's `parentId`, so a
nested child adopts its direct parent's revision and still resolves the root
session's original sources; Codex children use the root session's ledger. An
Omp `task` call strips contract tags from model-written input, and a child
adopts a contract only from exactly one tag. An Omp handoff retains native session/source locators; a source
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
`classic.SessionStart`, `classic.SubagentStart`, `classic.Stop` and
`turn.complete.isAborted`. Native classic handlers return `additionalContext`
arrays or a `block` reason, not settings-hook response envelopes. A settings
`UserPromptSubmit` hook alone cannot distinguish user, scheduler and peer
input. The adapter does not use that unsafe classification.
SDK-host requests can create interpreted contracts, but are not user approval.

Codex uses `.codex-plugin/plugin.json` to load the common hooks and
`hooks/task-state-codex.json`. Only the Codex file registers `Interrupt`.
Claude never parses that event. The model receives a task-state command bound
to its native session and actor; it supplies `{action, record}` on stdin.
That command carries `--tool`, which accepts only `{action, record}` and
rejects hook events. The hook entry rejects actions. A command hook cannot
prove its caller, so this split protects the advertised route only. A model
with unrestricted shell access to `task-state.py` or the private ledger is
outside this boundary.
The model's own task-state calls are bookkeeping, not task evidence. A
controller answer exits 0 even when it reports `isError`, so a call can never
register as a failed tool result, reset the correction allowance or support an
execution blocker. Only protocol and runtime faults exit nonzero. Each Codex
call also records a receipt: a digest of its exact output in the private
ledger. `PostToolUse` drops a non-failing result whose output equals a pending
receipt and consumes that receipt. Nothing parses the shell command, so a call
chained with other work, or wrapped in other output, stays ordinary evidence.
Codex sends a Bash `PostToolUse` result as the captured output string, with no
exit status (`codex-rs/core/src/tools/context.rs`,
`ExecCommandToolOutput::post_tool_use_response`). A Codex shell observation
therefore never records a failure: a failed command does not change the
correction condition and cannot support an `execution` blocker on Codex. The
two-correction bound still applies to an unchanged condition.
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

Codex app-server clients must request the supported lifecycle explicitly:
`thread/start` with `sessionStartSource: "startup"` (Python SDK
`session_start_source=ThreadStartSource.startup`). The default `None` source
can execute model and tool requests without these lifecycle hooks, even when
`hooks/list` reports trusted definitions. A bounded native app-server run
with the startup source observed root and child hooks.

### Installed-runtime capability checkpoint

The bounded checkpoint on 2026-11-02 used no external model:

| Harness | Registration and local response route | Observed native events |
| --- | --- | --- |
| Omp 18.15.0 | Installed/linked extension, scripted loopback provider, RPC | The live task-state probe passed original approval/tool-source recovery, two-correction bounds and native abort. A separate shipped-extension run retained equal parent/child contracts, zero child user sources, criteria and correction counts through native compaction and process resume. |
| Claude Code 2.1.316 | Task-private npm installation; shipped `--plugin-dir` mod; local `turn.step` response fixture and loopback compaction provider | Genuine terminal `composer` input and a separate plugin's non-user input remained distinct. The shipped tool ran. Actual process resume and `/compact` preserved the contract and criterion IDs. Esc cancelled a pending correction with `turn.complete.isAborted: true`; cancellation and count 2 persisted. |
| Codex CLI 0.160.0 | Task-private native marketplace/plugin installation and private CLI hook fixtures; local Responses provider | The unchanged shipped manifest captured one original user source and stopped at two corrections after three local requests. The shipped-controller lifecycle run exercised native tool access, child delegation with zero child user sources, SIGINT/`Interrupt`, process resume and `/compact`; contract, criteria, cancellation and count 2 survived. |

On 2026-11-07 a Claude Code 2.1.319 cloud session loaded the shipped mod
unchanged as a session dev mod and exercised delegation with genuine runtime
events. A `composer` prompt became the only `user` source; a
`task-notification` and the subagent's `peer` hand-back stayed
`interpretation`. One `agent.spawn` gave the child the same contract ID,
revision and criterion IDs in a separate private ledger with zero `user`
sources. The child's authorization citing the parent's user source was
rejected, and the parent recorded no authorization.

The workstation's Claude Code 2.1.267 is too old for the mod route. The
task-private 2.1.316 install did not change shared configuration or credentials.
A separate Codex 0.160.0 app-server checkpoint used trusted hooks and the
explicit startup source. Six local Responses requests exercised
`SessionStart`, `UserPromptSubmit`, `PreToolUse`, `SubagentStart` and `Stop`.
The earlier default-source attempt omitted lifecycle hooks; it did not
establish an unsupported capability.

These native-event observations establish the adapter route. Offline
controller/adapter regressions run in the existing `check-omp-extension`
suite. They do not replace installed-runtime evidence or prove that a model
will honor arbitrary approval prose.

### Completion-evidence scenarios

The optional `--completion-harness` mode of the existing live task-state
script exercises the installed runtime with a private HOME, local Git
fixture and loopback scripted provider. It makes no external inference or
GitHub fixture requests. Each process has a 120-second deadline and a
24-request bound. It does not add a recurring CI job or install a shared
runtime.

```sh
python3 scripts/check-omp-task-state-live.py --completion-harness omp
WORKTRUNK_PLUGIN_ROOT=/path/to/installed/worktrunk-plugin \
  python3 scripts/check-omp-task-state-live.py --completion-harness claude
python3 scripts/check-omp-task-state-live.py --completion-harness codex
```

Claude loads the unchanged shipped manifest and its declared Worktrunk
dependency. Omitting that dependency can omit Daily Driver's tool while an
unrelated fixture plugin still loads. Codex installs the unchanged plugin
through a private local marketplace. Its fixture explicitly permits the
reviewed local hooks through the CLI's automation hook-trust option; it does
not bypass the task completion gate. The private Codex configuration sets
`tool_output_token_limit = 20000` so the native status response is not
truncated before the scripted provider can read it. A truncated status is
not evidence of a controller pass.

Observed on 2026-11-10:

| Harness | Local provider requests | Completion and abort result |
| --- | --- | --- |
| Omp 18.18.6 | 16 | Rejected summary-only completion and a failed check inside successful transport. Current check evidence plus a source-backed scripted judgment completed. A dirty subject reopened the task; correction count stopped at two. The existing live suite also exercised native RPC abort without completion. |
| Claude Code 2.1.321 | 18 | The same completion and dirty-subject cases passed. A second process received SIGINT during corrective request 1. It stopped without completion or another provider request; its private task remained `active`. |
| Codex CLI 0.160.0 | 18 | The same completion and dirty-subject cases passed. SIGINT during corrective request 1 stopped further requests and persisted `cancelled`, without completion. |

Claude print-mode SIGINT did not persist a cancellation record in this
scenario. Do not describe that state as cancelled or completed. Its unfinished
contract remains available for a supported resume. The native mod's
`turn.complete.isAborted` route and the shared explicit-cancellation tests
remain separate coverage.

These fixtures establish runtime transitions and evidence-kind accounting.
Their scripted judgments do not establish independent semantic correctness.
The existing runtime suite also covers missing, unrelated, truncated, stale,
wrong-task, changed-revision and non-code-artifact evidence, required approvals,
contradictory results, exact native-source recovery and historical reports.

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
through its model catalog to identify the family and provider. A family entry
does not authorize a different provider. The built-in OpenAI Codex entry
preserves the existing defaults; explicit same-family class roles remain
operator assignments. Plugin-installed global defaults do not establish a
mapping for unrelated families. A mapping is not measurement evidence.

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
