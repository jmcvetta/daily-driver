# Opt-in PR supervision

The accepted design for [#1038](https://github.com/jmcvetta/daily-driver/issues/1038)
is the [research report](https://github.com/jmcvetta/daily-driver/issues/1022#issuecomment-7128430156)
and its [correction](https://github.com/jmcvetta/daily-driver/issues/1022#issuecomment-7128609718).
The existing [Omp maintenance route](../skills/pr/references/omp.md) remains
authoritative unless an explicitly configured owner completes a per-PR transfer.
No real PR's ownership was transferred as integration proof.

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

## Active controller and owner tools

`scripts/pr-active-supervisor.py` shares the ledger and inbox database.
`run` holds one controller file lease, reconciles due records, and dispatches
cold owner work through a bounded worker pool. A service manager must own its
restart policy; the command does not install or enable a live service.
The configured reconciliation interval is 120 seconds. Event hints can move
the next read earlier, but cannot move the periodic outage deadline.
Missed deadlines and access failures remain durable degraded evidence.

Set `DAILY_DRIVER_PR_SUPERVISOR` to an absolute owner-only database path in an
authorized owner profile. The runtime registers PR creation/body-update results
through `daily_driver_gh_write`. For adoption or another creation route, call
`daily_driver_pr_supervisor_register` with the exact PR URL and task worktree.
Registration retains the original owner, actual task worktree, branch and task
context; another session cannot take control by registering the same identity.
It starts in shadow mode and does not replace existing maintenance.

The controller reads complete authoritative current-head inventories. It
defers updates for in-flight or unregistered CI, rereads immediately before
and after GitHub's expected-head update-branch request, and discards old-head
evidence. It never rebases, force-pushes, marks ready, closes issues or merges PRs.
A per-PR drain lock serializes a remote mutation with stop/hold; SQLite
transactions remain short so other records and heartbeats stay writable.

Changed actionable observations coalesce into one generation. The owner tool
`daily_driver_pr_supervisor_acknowledge` makes a complete authoritative GitHub
read and rechecks admission transactionally before it accepts the current
generation. Its returned `observed` evidence is the work input: the owner must
not inventory GitHub first, or act and acknowledge afterward. Rejection grants
no authority. An accepted read is not completion, independent review, green CI
or readiness; a later decision or mutation boundary still needs applicable
fresh evidence. Changed heads, stopped/held actors and superseded admissions
reject stale work. Delivery attempts and failures before admission share a
bounded retry budget; missing context or activation failures cannot spawn a new
process forever.

### Cold child recovery

The bounded `python3 scripts/probe-omp-child-resumption.py` proof uses a
disposable profile and localhost provider. Parent `--resume`, followed by a
native `write agent://ChildProof`, revives the same persisted child with its
original `sub/ChildProof` binding and a persisted native-tool acknowledgment.
An empty RPC `get_subagents` snapshot does not prevent this supported resolver.
Direct child `--resume` preserves the session ID but incorrectly binds it as
`main/Main`; the host never uses that route for a child. RPC `--restore`
requires an interactive terminal and is not this adapter's route.

The host checks both child and parent leases and refuses a held or unknown
parent. It resumes the recorded parent as a restricted dispatch carrier:
only native write to the exact recorded child and wait are admitted.
Parent and child identity, provider, model, effort, authentication route and
working context are checked before delivery. Native dispatch reads current
generation/stop/hold state, and the child rechecks admission before tools.
Credentials are used in place, never copied or forwarded from arbitrary
environment variables. Missing identity or route evidence is degraded, not
permission to use another agent.

The same command runs `scripts/probe-pr-active-supervisor.py` under an actual,
bounded transient systemd user unit with `Restart=on-failure`. The active
controller and actual child owner persist fresh-read work acknowledgments for
two fixture heads across controller restart. A stop during the resumed
parent's queued/in-flight turn prevents native child dispatch, a child
provider request and acknowledgment of the stopped generation. This is not
proof that an arbitrary already-running provider request can be undone.
The probe uses isolated `gh` response fixtures, not a real PR.
The bounded `scripts/probe-omp-child-resumption.py` proof also exercises
legacy authorization on the inbox's real SQLite connection. A current queued
or running token allows its next tool; a separate connection that stops the
record or changes its token or epoch denies the next tool boundary.

### Transfer, rollback and stop

After the authorized controller is running, use
`daily_driver_pr_supervisor_control` with operation `transfer`, the exact
identity, every owned legacy service name and the live owner-reminder IDs.
Drain queued owner work first. The tool persists rollback identity before
cancelling timers, fences old pending wakes, verifies/stops the old services,
takes fresh GitHub state and activates the new authority. A missing controller,
unknown timer, stop, hold or running admitted legacy wake prevents activation.
An incomplete transfer retains the recovery record; do not start a second owner.

Transferred and restored legacy timers carry an authority-epoch admission.
A timer that fires before transfer but delivers afterwards cannot run.
Queued legacy admissions have a 120-second lease, their original message and
a five-attempt retry budget. A managed retry rotates an abandoned queued token;
an owner restart/rebind rebuilds that retry from the private database. Old
tokens cannot start or finish replacement work. Once owner work has started,
its token does not expire by age: only completion or an explicit control fence
can release it. This does not give the old route autonomous cold activation.

The legacy wake adapter checks each supervised tool boundary with one fresh
prepared SQLite read on the inbox's existing owner connection. It verifies the
record, shadow authority, delivery token and epoch, and either a running wake
or an unexpired queued lease. Start, finish, retry, recovery and control remain
durable supervisor operations; the boundary read is not cached permission.
Already-running admitted legacy work must drain before transfer. Rollback
first fences new deliveries and drains mutations, then reads fresh state and
restores only the recorded prior services and original reminder message/deadline.
Successful timer restoration is persisted so retries do not duplicate it.
Matching structured PR/review watches are saved and stopped as part of the
same transfer. Rollback restores their state and deadline under a new watch
incarnation without clearing prior stop tombstones. A second transfer fences
that restored fallback as well.
Retransfer creates a new fenced transport incarnation from fresh evidence.
Stops and holds are never cleared by rollback or re-registration.

Use operation `stop` before any stop-time push. It fences observations,
pending admissions and queued work, drains an in-flight mutation, and stops
recorded old services. Owned cold RPC work is aborted when its deliveries
are stopped or held. Merge/close observations retain terminal evidence and
leave the due set. `release` clears an explicit hold, not a stop.
After an authorized conflict resolution is pushed, release any explicit hold
and reconcile the same identity; do not create another actor.

The old Omp route still cannot cold-resume an owner after shutdown. Rollback
reports that limitation. No machine-reboot or deployed continuous-availability
claim follows from the transient restart proof; outages remain gaps.

## Verification

The existing `make check-pr-keep-current` target covers the legacy, shadow,
inbox, active-controller and runtime-tool consumers. Coverage includes lease
expiry, concurrent registration, hints and missed deadlines, fresh ACKs,
stop/hold races, head changes, workflow-only CI, conflicts, terminal cleanup,
bounded activation failures, legacy timer restoration and retransfer.
Manual lifecycle proofs do not add recurring CI checks.

An identical deterministic trace compares the active consumer with an explicitly
configured 120-second legacy owner-timer/currency-poll model. The trace has
seven active reconciliations and three agent wakes, against five legacy polls
and five owner wakes. Two event-to-action latencies are 1/1 seconds for active
hint delivery and 119/109 seconds for the legacy timer. These are fixture
results, not production fleet metrics or a claim that every trace saves reads.

Current-head CI and independent review remain separate readiness requirements.
Claude Code and Codex retain their existing honest best-effort routes; this
implementation adds no cross-shutdown guarantee for them.
