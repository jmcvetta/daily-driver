# Claude Code routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md) and
Codex's in [`codex.md`](codex.md); both carry the harness-local subagent
fallback, for different reasons each states.

**The fleet on this harness is web sessions.** `embark`'s Claude route opens
one per task with `create_session`, and this file secures, stops and
archives exactly what that route opened. A Claude Code session runs no
fallback wave, so it has no subagents to cancel — a fleet member that is not
a web session here is not a member this skill dispatched.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `mcp__github__issue_read`, `method: get_comments` |
| `Read the fleet` | Read a task issue's claim and handoffs | `mcp__github__issue_read`, `method: get` and `get_comments` |
| `Read the fleet` | Read a task's pull-request state | `mcp__github__pull_request_read` |
| `Secure the work` | Load the messaging tools, once per session | `ToolSearch`, `select:ListAgents,SendMessage` |
| `Secure the work` | Stop a session's current turn | `mcp__Claude_Code_Remote__interrupt_session` |
| `Secure the work` | Name the session as an address | `ListAgents` |
| `Secure the work` | Send the wrap-up | `SendMessage`, to that name |
| `Secure the work` | Read whether the turn has ended | `mcp__Claude_Code_Remote__get_session`, `status_bucket` |
| `Write the handoff` | Comment on a task issue or the epic | `mcp__github__add_issue_comment` |
| `Stop the fleet` | Retire a session | `mcp__Claude_Code_Remote__archive_session` |
| `Cancel the watches` | Cancel the backstop | `mcp__Claude_Code_Remote__delete_trigger`, by the `trigger_id` the wake slot holds |
| `Cancel the watches` | Drop a pull-request subscription | `mcp__github__unsubscribe_pr_activity`, one call per subscription |

**Addressing a session is the same route `embark`'s `Recover a session`
uses**, named in that skill's [`claude.md`](../../embark/references/claude.md).
`ListAgents` and `SendMessage` are deferred tools, not in the tool list
until `ToolSearch` loads them; call it once, before the first send this
step makes, and both are then callable for the rest of the batch.
`ListAgents` lists this account's cloud sessions, matched against the fleet
member, and `SendMessage`'s `to` takes the name that row prints — never the
`session_01AbC…` identifier the muster roll records, which does not resolve
as an address. A member the listing does not name cannot be reached at all;
it is not sent a wrap-up, and it is named as a residual at `Secure the work`
rather than retried.

**The wrap-up message** tells the session, in words: commit everything in
progress to the task branch, push it, and end the turn without starting
anything else — stage named files, skip no hook and no test, open no pull
request, mark nothing ready. It is one message, sent after the interrupt, to
every web-session fleet member in the same parallel batch.

**The wait is bounded by one shared deadline: three minutes from when the
batch of wrap-up messages is sent**, not three minutes per session. Poll
`get_session`'s `status_bucket` for each addressed session — `working` means
the turn has not ended — until every one has left `working` or the deadline
passes, whichever comes first; this is the one wait `SKILL.md`'s speed
constraint carves out; nothing else in this skill polls. A session the
deadline outlasts, and a session `ListAgents` never named, are both recorded
as a residual for that implementor at this step, and are archived anyway at
`Stop the fleet` — securing the work is attempted once, not guaranteed.

**`Stop the fleet` archives without reading status again.** The interrupt and
the wrap-up wait already happened at `Secure the work`; archiving does not
wait on `status_bucket` a second time, and `SESSION_STATUS_RUNNING` — which
covers a session still working and one merely stuck alike — is not consulted
here. If the archive call refuses a session it believes is still running,
the one bounded retry happens after the interrupt's result is in; a second
refusal is a residual for the banner. A session the archive call has already
retired is skipped, which is what makes a re-run of the stops safe.


The watches
===========

The backstop is a `send_later` trigger held by the identifier its arming
call returned — the one wake slot [`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md)
records. `delete_trigger` takes that identifier; a trigger id the session
no longer holds is read from the epic's stand-down comment, where
`Write the handoff` records the watch inventory — and a first stand-down
has no earlier comment of that shape, so the id is then the one the wake
slot holds. Each pull-request subscription is dropped
by the same call that opened it, and where a PR Steward watches the pull
request instead, the call still succeeds — dropping this session's
subscription is the point, and the steward is unaffected.

**There is no persistent CI watcher on this harness** — the hub process
route is Omp's — and a `send_later` trigger is the only wake the watch
arms. The route table above is the whole watch inventory.


What is lost, and what is not
=============================

**A wrap-up that lands secures the work before the archive**, so the common
case is no loss at all: the session commits and pushes on its own branch,
`Secure the work`'s wait confirms the turn ended, and the archive that
follows destroys nothing origin does not already have. What the session
pushed, the branch carries; what its pull request reports, GitHub carries;
and the claim comment `undertake` posted names the branch a replacement
reuses.

**Loss is possible only where the wrap-up did not land in time** — the
session missed the three-minute deadline, or `ListAgents` never named it to
begin with. There, whatever that session held and never pushed is gone at
the archive, exactly as before this route existed. `Secure the work` records
it as a residual the moment the deadline or the listing fails, so the banner
and the handoff both say so before the archive happens, rather than after.
