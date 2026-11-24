# PR supervision: shadow implementation and capability evidence

Issue [#1038](https://github.com/jmcvetta/daily-driver/issues/1038) is unfinished.
The accepted design is the [research report](https://github.com/jmcvetta/daily-driver/issues/1022#issuecomment-7128430156)
and its [correction](https://github.com/jmcvetta/daily-driver/issues/1022#issuecomment-7128609718).
The existing [Omp maintenance route](../skills/pr/references/omp.md) remains
authoritative. This implementation does not transfer any PR's ownership.

## Bounded capability evidence

On 2026-11-24, installed Omp 19.1.1 completed an isolated local proof:

```sh
python3 scripts/probe-omp-cold-activation.py
```

The proof uses a disposable home, an empty sandbox, and a localhost scripted
provider. It does not inherit credentials, contact GitHub, install a watch,
or use a real PR. It starts an actual Omp RPC process, requests an actual tool
acknowledgment, verifies that acknowledgment in the saved session, terminates
the process, and starts another process with `--resume <same-session-file>`.
The resumed process persists a second acknowledgment. It also checks the
supported `omp session lease --json` route while each session is live. The
first run exposed an incorrect probe assertion about `type` versus
`customType`; correcting that assertion produced the two persisted records.

This proves a cold CLI activation primitive and durable tool acknowledgment,
not a working PR delivery adapter. The scripted acknowledgment does not claim
that a real owner read GitHub or accepted a supervisor generation.

### What the supported APIs establish

The exact installed-version manuals are the source, not the absence of a
service file:

- [RPC, v19.1.1](https://github.com/can1357/oh-my-pi/blob/v19.1.1/docs/rpc.md)
  defines commands on a process's stdin and results on its stdout. `prompt`,
  `follow_up`, and `switch_session` control that process. A prompt scheduling
  response is not completion. `get_session_lease` and the CLI lease command
  report held/unknown sessions; they do not return a delivery endpoint.
- [SDK, v19.1.1](https://github.com/can1357/oh-my-pi/blob/v19.1.1/docs/sdk.md)
  exposes in-process session construction/resumption and explicitly assigns
  process lifecycle to the embedder. It does not restart a stopped embedder.
- [Extensions, v19.1.1](https://github.com/can1357/oh-my-pi/blob/v19.1.1/docs/extensions.md)
  provides `pi.sendMessage` for the bound live session. Managed timers are
  unreferenced and cleared on `session_shutdown`. They are not a restart host.

These APIs support a real bridge; they do not need a preinstalled adapter.
`extensions/pr-supervision-inbox.mjs` now binds an opt-in SQLite inbox to the
actual live Omp owner. `scripts/pr-inbox-host.py` uses the native lease probe
before exclusively cold-resuming an owner with its recorded session and route.
A held or unknown session is not opened by the host. An expected-session guard
rejects a fork or replacement before delivery. The extension checks admission
fences again at delivery and before tool calls.

The bounded `python3 scripts/probe-pr-inbox.py` proof uses an actual transient
systemd user service with `Restart=on-failure`, not an installed watch. It
delivered generation 1 to the already-live owner, then automatically restarted
the controller and resumed the same saved owner for generations 2 and 3.
Duplicate/older generations retained their receipt; generation 4 was stopped
before delivery and caused no provider request. Only the localhost scripted
model ran. The probe also exercises dropped-receipt redelivery.

This resolves the basic host/live-owner delivery primitive, not active PR
supervision. `daily_driver_pr_inbox_receipt` records transport receipt only;
it is not the accepted fresh-GitHub work acknowledgment, readiness, or CI.
The bridge must still be integrated with authoritative PR reconciliation,
atomic transfer and stop-time actor cancellation. No live service is installed
or enabled; no real PR is changed by either capability proof.

### Explicit receipt transport

Initialize an owner-only inbox with `scripts/pr-inbox.py --database <path>
enqueue <identity> --session <id> --generation <n> --context <nonsecret-json>`.
Opt a session into that inbox with `DAILY_DRIVER_PR_INBOX=<path>` and the
explicit `--extension <plugin>/extensions/pr-supervision-inbox.mjs` option.
This is separate from the shadow ledger; do not enqueue real work without its
task authority or use it as a second wake owner beside existing maintenance.

The host command is `scripts/pr-inbox-host.py --database <path>`; `--once`
performs one bounded pass. It holds an exclusive file lock across host work.
The extension registers owner metadata, refreshes its route/heartbeat, admits
one generation, and retries an unreceived delivery at most five times with
bounded exponential backoff. Duplicate and older generations do not reset
that budget. A newer generation fences the old admission. `stop`, `hold` and
`release` are explicit inbox controls; stops cannot be cleared by release.
On graceful shutdown the owner metadata remains for cold recovery. The host
reuses configured credentials in place and never copies them.

Neither transport receipt nor a heartbeat proves a continuous healthy agent.
Exhausted retries, missing owner context or an unavailable lease/activation
route retain a durable diagnostic. The isolated proof demonstrates process
restart, not machine-reboot availability or deployed continuous coverage.

## Opt-in read-only ledger

`scripts/pr-supervisor.py` is an explicit shadow consumer. It uses Python's
standard SQLite library and `gh api --method GET`. Its command surface has no
update, wake, subscription, readiness, cutover, rollback, or stopped-record
resume operation. Registering a PR here does **not** register active supervision.

Use an owner-only directory outside Git for the database and nonsecret task
context. Context contains references such as issue, branch, worktree and Omp
session ID; do not copy credentials, prompts, or protected instructions into it.
For an independently authorized shadow observation, the command form is:

```sh
python3 scripts/pr-supervisor.py --database /absolute/private/shadow.sqlite register \
  --host github.com --repository owner/repository --number 123 \
  --owner github-login --context /absolute/private/task-context.json
python3 scripts/pr-supervisor.py --database /absolute/private/shadow.sqlite reconcile
python3 scripts/pr-supervisor.py --database /absolute/private/shadow.sqlite list
```

`reconcile` makes one pass over due records and exits. There is no installed
scheduler: the stored next-observation time is 120 seconds, **not** a guarantee
that a process will run then. Restarting this command enumerates due records.
Missed deadlines and failed observations retain an outage interval; successful
recovery closes the interval without claiming uninterrupted coverage.

Registrations normalize host/repository case and retain the original owner and
context. Concurrent registrations adopt the same record. An immediate SQLite
transaction leases each observation writer; a monotonic fencing epoch rejects
late results after expiry, takeover, hold, stop or terminal PR cleanup. Network
reads occur outside the database transaction. The database refuses nonprivate
files and final-component symlinks. Store schema version is 1; unknown schemas
fail rather than resetting state.

Each observation reads the PR's actual head and base, all paginated check runs,
status history, matching workflow runs, and conversation/review feedback. A
second PR read rejects a moved head/base or terminal transition during the
inventory walk. Malformed, denied, incomplete or empty inventory never means
green. Matching workflows can defer a proposed currency update even when no
check run registered. Newer status contexts and current workflow attempts
supersede their older history.

Normalized evidence includes CI identities/states and feedback fingerprints,
not feedback bodies. Only conversation prose attributed to the registered
owner session is ignored; a human using the same login and another session's
review remain visible. The latest proposed action and changed-observation
generation are persisted. A proposal is **not** a pending delivery or an
acknowledged owner action. Neither periodic unchanged observations nor event
hints activate an agent: there is no delivery adapter in this shadow consumer.

`hold <identity> --reason <reason>`, `release <identity> --reason <reason>` and
`stop <identity> --reason <reason>` affect this ledger only. Holds survive reopen
and re-registration. Release clears a hold but cannot clear a stop. Stop fences
in-flight shadow reads and clears proposals. Merged/closed PRs retain terminal
evidence, fence the writer and leave the due set. These controls do not cancel
the existing authoritative maintenance route; use that route's stop procedure
before a stop-time push. Never use a shadow stop as evidence that live actors
were stopped.

## Verification and remaining acceptance

The existing `make check-pr-keep-current` gate also runs
`scripts/test-pr-supervisor.py` and `scripts/test-pr-inbox.py`. Offline consumer tests cover concurrent
registration, identity isolation, lease exclusion/expiry, stale observations,
restart gaps, failed reads, hold/stop races, duplicate observations, terminal
cleanup, paginated inventories, workflow-only pending CI, changed heads,
masked currency, feedback and conflict-recovery proposals. Inbox tests cover
coalescing, stale/duplicate generations, holds, stops, receipt retry bounds,
missing context and refusal to open held or unknown owners. The existing CI
filter includes these product sources/tests. The manual capability probes do
not become recurring CI checks.

Still unfinished: active registration of every created/adopted PR, integration
of the proved restart/delivery primitives with the PR supervisor, fresh-read
work acknowledgment, event validation/coalescing, fenced GitHub mutation,
stop-time cancellation of all queued owner work, active conflict resumption,
and ownership transfer/rollback. Full delivery race coverage and identical-trace
active wake/latency comparisons must exercise that integrated actor. Shadow's
zero agent deliveries are a safety property, not measured fleet savings.
No baseline fleet metrics or continuous-operation claim are made.

Keep both the issue and PR unfinished. Do not weaken the acceptance criteria,
mark the PR ready, or enable an active mode based on this shadow evidence.
Claude Code and Codex retain their existing best-effort routes; this work adds
no cross-shutdown guarantee for them.
