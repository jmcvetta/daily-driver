# Claude Code routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md) and
Codex's in [`codex.md`](codex.md); both carry the harness-local subagent
fallback, for different reasons each states.

**The fleet on this harness is web sessions.** `embark`'s Claude route opens
one per task with `create_session`, and this file stops and archives exactly
what that route opened. A Claude Code session runs no fallback wave, so it
has no subagents to cancel — a fleet member that is not a web session here
is not a member this skill dispatched.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `mcp__github__issue_read`, `method: get_comments` |
| `Read the fleet` | Read a task issue's claim and handoffs | `mcp__github__issue_read`, `method: get` and `get_comments` |
| `Read the fleet` | Read a task's pull-request state | `mcp__github__pull_request_read` |
| `Write the handoff` | Comment on a task issue or the epic | `mcp__github__add_issue_comment` |
| `Stop the fleet` | Stop a session's current turn | `mcp__Claude_Code_Remote__interrupt_session` |
| `Stop the fleet` | Retire a session | `mcp__Claude_Code_Remote__archive_session` |
| `Cancel the watches` | Cancel the backstop | `mcp__Claude_Code_Remote__delete_trigger`, by the `trigger_id` the wake slot holds |
| `Cancel the watches` | Drop a pull-request subscription | `mcp__github__unsubscribe_pr_activity`, one call per subscription |

`get_session` reports a session's status, but `Stop the fleet` never reads
it before acting: `SESSION_STATUS_RUNNING` covers a session that is working
and one that is stuck alike, and polling it would be a wait. The order is
interrupt, archive, move on — the interrupt ends the turn, and the archive
follows it without a status check between them.

**Archive after stop, and only once.** If the archive call refuses a
session it believes is still running, the one bounded retry happens after
the interrupt's result is in; a second refusal is a residual for the
banner. A session the archive call has already retired is skipped, which is
what makes a re-run of the stops safe.


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

**A cloud session's workspace dies at the archive.** Whatever the session
never pushed is gone, and the handoff on the task issue says so before the
archive happens — that is `SKILL.md`'s accepted-loss rule, restated here
because it is this route that makes it true. What the session pushed, the
branch carries; what its pull request reports, GitHub carries; and the
claim comment `undertake` posted names the branch a replacement reuses.
