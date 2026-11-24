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

The remaining unproved operation is to recover durable PR records after the
controller/host disappears and deliver exactly one fenced generation to the
right owner, including an owner already running in another process. A new RPC
process and its private stdio do not reattach to an arbitrary existing TUI or
RPC owner. The inspected public APIs do not document a session-ID-to-live-input
endpoint. The local user service inventory had no Omp or Daily Driver unit;
that is installation evidence only, not proof that systemd or hosting cannot
work. No blanket claim that Omp lacks cold resumption is justified.

A viable resolution is a supported lifecycle host for a durable controller,
plus a verified live-owner inbox/extension bridge (or a host-owned RPC channel)
and cold activation using the proved CLI primitive. That integration must
preserve the owner session, model/authentication route and task context, refuse
unknown/held ownership instead of creating a second writer, acknowledge only
after a fresh owner read, and prove restart, stop, duplicate delivery and
credential failure in isolation. The existing APIs are useful building blocks;
this implementation does not claim that integration exists. Do not install a
live watch to test it. Any separate host integration must respect the accepted
design's authorization boundary.

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
`scripts/test-pr-supervisor.py`. Offline consumer tests cover concurrent
registration, identity isolation, lease exclusion/expiry, stale observations,
restart gaps, failed reads, hold/stop races, duplicate observations, terminal
cleanup, paginated inventories, workflow-only pending CI, changed heads,
masked currency, feedback and conflict-recovery proposals. The manual cold
probe is not added as a recurring CI check.

Still unfinished: active registration of every created/adopted PR, a supported
restarting host, live-owner reattachment, generation delivery/acknowledgment
and bounded redelivery, event validation/coalescing, fenced GitHub mutation,
stop-time cancellation of queued owner work, active conflict resumption, and
ownership transfer/rollback. Full dropped/duplicate/out-of-order event and
acknowledgment coverage and identical-trace active wake/latency comparisons
must exercise that real adapter. Shadow's zero agent deliveries are a safety
property, not measured savings against an active fleet. No baseline fleet
metrics or continuous-operation claim are made.

Keep both the issue and PR unfinished. Do not weaken the acceptance criteria,
mark the PR ready, or enable an active mode based on this shadow evidence.
Claude Code and Codex retain their existing best-effort routes; this work adds
no cross-shutdown guarantee for them.
