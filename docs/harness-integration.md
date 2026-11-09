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

### Initial measurement (superseded)

Offline installed-runtime captures used Omp 18.15.0, Claude Code 2.1.267, and
Codex 0.160.0. Providers listened on loopback only and used disposable homes
with no external credentials. Scripted replies exercised actual native tools
and request construction; they do not establish model compliance or behavioral
parity.

The recorded base is `42b5bddb42cffffeab14678b446eed52a3c6bb23`.
UTF-8 byte counts, not tokenizer counts, are used:

| Complete source/delivery unit | Base | Candidate |
| --- | ---: | ---: |
| Constitution file, including frontmatter | 13,913 | 8,429 |
| Omp body, excluding frontmatter | 13,883 | 8,399 |
| Rendered hook core, including standing-authority header | 14,197 | 8,713 |

Actual delivery differs from the complete-source comparison:

- Omp main and native child requests each contained one complete core in both
  arms. Candidate native task completion, task transition, manual RPC compaction,
  and a new resumed process were observed. The resumed request retained the
  complete core and executed the CI-policy read.
- Claude baseline startup supplied a roughly 2 KB preview of a persisted hook
  output, not the full core. Its startup hook wrapper occupied 2,532 UTF-8 bytes
  in the recorded request; candidate complete delivery occupied 8,770 bytes.
  Baseline child requests carried a full prompt-prepended core plus another
  startup preview. Candidate child requests carried one complete core and the
  original delegated prompt without a rewrite. Startup delivery grows when the
  missing safety instructions are restored; source reduction does not satisfy
  a literal decrease in actual startup bytes.
- Codex baseline main and child requests each carried one truncated hook block
  of 10,107 bytes. Candidate main and child requests each carried the complete
  8,713-byte core once. Its default `additionalContext` threshold is 2,500
  approximate tokens; the manifest explicitly uses a finite 5,000-token budget.

The delivery suite bounds the rendered core to 9,000 UTF-8 bytes. Do not raise
that budget or lengthen the core without a new installed-runtime proof of
complete delivery. Reintroducing a preview is not a context saving. Restore or
relocate any control needed by a failing comparison; do not weaken the rubric.

### Reconciled measurement — 2026-11-07 (superseded)

The current baseline is `f053d4ce63b97ee51abec43da0a86d1df4f8bc6a`.
The reconciled candidate retains the baseline's headless execution, protected
handoff, CI-scope, and bounded-experiment requirements. Measurements use UTF-8
bytes, not estimated tokens. The earlier measurements above remain historical.
That reconciled candidate core has SHA-256
`39075eb1cd25647ebc32b84f94ceb10e46251f16a37f263199991ea25ccb1076`.

| Delivered unit | Current base | Reconciled candidate |
| --- | ---: | ---: |
| Constitution file | 18,502 | 8,761 |
| Omp core body, main and child | 18,474 | 8,733 |
| Claude raw startup hook wrapper | 2,564, preview only | 8,955, complete |
| Codex startup/child hook block | 10,107, truncated | 8,880, complete |

Loopback providers and disposable credential-free homes exercised Omp 18.18.0,
Claude Code 2.1.267, and Codex CLI 0.160.0. Candidate captures contain one
complete core on main and native child subject requests, task switching, and
Omp/Claude resume after compaction. Codex resume retains two complete hook
blocks (17,760 bytes); after native compaction both remain. Baseline Codex also
accumulates two truncated blocks. This is actual repeated delivery, not a
single-copy measurement. Summarizer and skill-preparation requests are not
subject-core delivery. Scripted providers prove delivery and workflow access,
not autonomous compliance; their fabricated usage counters are not inference
cost evidence.
Task-private `disclosure_omp_probe.py`, `disclosure_claude_probe.py`, and
`disclosure_probe.py` produced the captures under ignored `evals/runs/`.
The candidate runs used 35, 11, and 12 local provider requests respectively.
Their main, child, switch, compact, and resume phases completed. These are
request-construction experiments, not inference-cost or model-behavior results.

The opt-in `codex-daily-driver` adapter was also exercised through its actual SDK
and bundled Codex 0.154.0, with reviewed native hook trust. Its five parent/child
requests each contained one complete 8,880-byte core. Read-only and
workspace-write confinement, blocked network access, and disabled shell/child
tools were observed. Injected HTTP errors and broken streams each produced a
crashed partial record rather than a false success. Native zero-retry provider
settings made one request per injected failure, but the unchanged runner made
four HTTP-error attempts and three broken-stream attempts. Its maximum is six
communication attempts for rate-limit errors, not an API-request cap.
The final task-private proof is
`evals/runs/disclosure-codex-adapter-final-core-isolated/proof-evidence.json`;
earlier overlapping-home captures are preserved but excluded.

At that checkpoint, the hook payload had 120 bytes below the 9,000-byte ceiling.
Claude's raw startup grew when the missing safety core was restored. The literal
startup-decrease criterion was not met. Those captures remain historical; the
later relocation below addresses the original criterion without an amendment.


### Compact delivery — 2026-11-07

The final relocated core has SHA-256
`ba084cdc07418d019805603a536431e1a0d5f4f286480802248ea7dd7d6c169b`.
The baseline remains `f053d4ce63b97ee51abec43da0a86d1df4f8bc6a`.
Counts are UTF-8 bytes from actual request strings, not token estimates:

| Delivered unit | Base | Compact candidate |
| --- | ---: | ---: |
| Constitution source | 18,502 | 2,473 |
| Omp main/child core body | 18,474 | 2,445 |
| Claude PATH CLI 2.1.267 startup wrapper | 2,568, preview | 2,557, complete |
| Claude SDK CLI 2.1.273 startup wrapper | 2,570, preview | 2,557, complete |
| Codex CLI 0.160.0 / SDK 0.154.0 startup/child block | 10,107, truncated | 2,482, complete |
| Codex CLI 0.160.0 resumed/compacted blocks | 20,214, truncated | 4,964, complete |

The Claude startup reduction is small, but the candidate delivers the full core.
The earlier baseline wrapper was 2,564 bytes; the candidate is also smaller
than that capture. Persisted-output paths affect preview overhead. Both controlled
Claude sandboxes are empty Git repositories; native system text is identical in
length. Do not count an inherited repository's conflict status as an instruction
saving.

New credential-free loopback captures are `disclosure-{omp,claude,codex}-release-proof`
under ignored `evals/runs/`. They exercised startup, native children, task
switching, compaction and resume on Omp 18.18.0, Claude Code 2.1.267 and Codex
CLI 0.160.0. They used 35, 11 and 12 local requests. Subject requests retain
one complete core, except Codex resume's two observed blocks. Omp preparation
and summarizer requests, and Claude/Codex summarizer/title requests, are not
subject delivery. These captures prove access, not autonomous policy compliance.

The actual Claude subject SDK selects its bundled 2.1.273 binary, not PATH's
2.1.267. A separate loopback lifecycle capture used that binary with the SDK's
empty system-prompt and project-setting options: 11 candidate requests and ten
baseline requests. Candidate subject requests, including native children and
post-compaction resume, retained one complete core. The captures are
`disclosure-claude-sdk-proof-{base,cand}` under ignored `evals/runs/`.

The actual Codex SDK/bundled 0.154.0 baseline was also measured with reviewed
frozen hooks: five parent/child requests each contained one 10,107-byte truncated
block, not its complete 18,786-byte rendered core. Its proof is
`disclosure-release-20261107/codex-preparation/base-sdk-parent-child-delivery/`.

Retrieval is not free. Current full source sizes are 8,493 bytes for `provenance`,
8,033 for `pr`, and 82,361 for `undertake`. Read only the relevant policy when
the issue sequence is not needed; retain retrieved context instead of repeating
reads. Report actual returned context, truncation and repeated reads in behavioral
records. Lower always-loaded bytes do not establish lower total cost or better
reliability. Scripted usage counters are not inference-cost evidence.

The [valid Omp comparison retrieval record](progressive-disclosure-retrieval.json)
contains all 36 slots, their input hashes, returned bytes, tool duration and task
wall time. It counts successful skill results, including repeated reads and
returned wrappers, not complete source files or hidden preparation:

| Across nine cases and two replicates per arm | Base | Candidate |
| --- | ---: | ---: |
| Successful skill reads | 20 | 45 |
| Returned UTF-8 bytes | 416,941 | 631,617 |

Some `undertake` results were truncated. The increased explicit retrieval is
not hidden by the smaller standing core; these counts establish no total-cost
or latency improvement. Per-slot token usage and separate judge usage remain
in the linked behavioral records.

The actual SDK/bundled Codex 0.154.0 adapter also delivered the 2,482-byte core
once in each of five parent/child loopback requests. Two containment requests
confirmed read access and denied writes and shell network access. All 16 invalid
reviewed-payload cases failed as non-retryable configuration errors before any
provider request. Unrelated host hooks and MCP processes stayed absent, without
requiring a native-home `hooks.json` or changing shared configuration.
The frozen `bd089b6` proof is under
`disclosure-release-20261107/codex-preparation/compact-core-adapter-proof-bd089b6/`
in ignored `evals/runs/`. It does not prove Git-write capability or model behavior.

The later Omp discovery repair was exercised through the actual `omp/18.18.0`
RPC executable: nine native traversal cases and 68 guarded cases passed
(27 admitted, 41 refused), including a real virtual environment. This supersedes
module-only traversal evidence from a separately installed 18.13.3 package.
The proof is `omp-executable-discovery-proof-cerftbik/evidence.json` under ignored
`evals/runs/`. Link names are directory metadata, not permission to read targets.

A later Codex adapter proof exercised the official runner's `DIRECT_WRITE`
layout with the opt-in owned fixture envelope. Native Worktrunk created an
initially absent sibling, staged a named file, committed it, and ran the
canonical verifier. The scripted run passed its two deterministic criteria.
The native home configuration stayed byte-identical and no hook file appeared.
The exact-cwd project trust is derived per thread; this prevents native
workspace-write startup from persisting project trust to the shared account
configuration. Inherited permission-profile additions fail before inference.
The owned-envelope and trust proof used adapter SHA-256
`20e3a3c5c165785486db8660d6c5c05366c0d4ab0db4cd70fdc8eef11852e99c`.
Proofs are under
`disclosure-release-20261107/codex-preparation/task-trust-repair-report.json`
and `official-runner-task-trust-fixed/` in ignored `evals/runs/`.
These credential-free scripted proofs establish integration behavior, not
model compliance or inference cost.

The subsequent native comparison exposed genuine visible-tool caps despite
upstream deterministic `SUCCESS` statuses. The adapter now marks capped partial
output with an `ERROR` result anchor; it does not erase the cap or change the
criteria. A replay through the changed wrapper checked preserved capped and
completed records without starting a native runtime. The adapter SHA-256 is
`78d93eff434f44bb3928c0139f6b031688603a90df1f59b0ea0166c0eae53ab5`.
The [native attempt inventory](progressive-disclosure-native-attempts.json)
keeps the original statuses and per-slot context/latency limits.

The Omp adapter now supplies `--session-dir` inside its private home by
default, while honoring explicit separated and inline options. This avoids
native startup failure when the encoded task path exceeds one directory
component. The actual Omp 18.18.3 executable returned ready and state frames
for all three forms at a long cwd, without a model turn or provider request.
The proof is `disclosure-omp-private-session-proof-20261109/report.json` under
ignored `evals/runs/`; its Omp adapter SHA-256 is
`fe414c50222423c3bbb9fcacf68e9b6f12741fa4da35369448817ac3d6205334`.

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

Before the next ordinary prompt, Omp restores the admitted worker model and
effort automatically. The target must still match the admitted backend and
authentication route and have available credentials. No manual cancellation,
model selection, request replay or autonomous inference is required. Pending
workers still need a successful admitted response before task work.
Cancellation and newer selections invalidate a waiting restoration.
Model selection may refresh metadata and apply host effort defaults.
Restoration compares the admitted origin, not object identity, then reapplies
the admitted effort.

A disposable Omp 18.18.3 loopback proof rejected late model drift without an
unauthorized HTTP request. The next user prompt completed on the admitted
worker without manual recovery, both before and after process resume.
Unavailable targets or credentials remain explicit recovery failures, not
permission to select a replacement route.

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
