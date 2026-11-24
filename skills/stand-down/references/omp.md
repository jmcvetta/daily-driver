# Omp routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

Omp uses harness-local subagents. Cancellation by dispatch handle is
unconfirmed; the shared `Secure the work` rule governs concurrent-write risk.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `gh issue view <epic> --json comments` |
| `Read the fleet` | Read a task issue's claim and handoff | `issue://<number>`, comments included |
| `Read the fleet` | Read a background task's job state | `read proc://<job-id>` using the job ID returned by `task` |
| `Cancel the watches` | Stop the embark backstop | `daily_driver_watch({action: "stop", key: <embark key>})` |
| `Cancel the watches` | Stop a persistent CI service | `write proc://<name>/kill`, by the service name review-cycle started |
| `Secure the work` | Inspect changes | `git -C <worktree> status --short` |
| `Secure the work` | Cancel a subagent | `write proc://<job-id>/kill`, using that same job ID |
| `Secure the work` | Commit named files when needed | `bash`, `git -C <worktree> add <named files>` then `git -C <worktree> commit -m <message>` |
| `Secure the work` | Push the branch | `bash`, `git -C <worktree> push` |
| `Write the handoff` | Read a task's pull-request state | `pr://<number>` |
| `Write the handoff` | Comment on a task issue or the epic | `daily_driver_gh_write({ args: ["issue", "comment", <number>, "--body-file", <path>] })` |

The wrapper appends provenance to the supplied comment body; do not format or
include a block in the body file.

For each member, inspect status, request cancellation, commit named files when
needed, and push even when there is no new commit. Do not poll for
cancellation. A job no longer listed by `proc://` is retired, not cancelled.
Record failed cancellation, staging, commit, or push as residuals under
`SKILL.md`; the handoff names the worktree and branch.

Read `git -C <worktree> rev-parse HEAD` for the local tip and
`git ls-remote origin <branch>` for the observed remote tip. Record failures
as unknown, and preserve any local-only commit and worktree path in the task
handoff. A failed or unconfirmed cancellation remains a fleet residual.


The watches
===========

Explicit stand-down input immediately stops active embark records; call `stop`
for the known backstop key as well and report any failure as a residual.
Cancel an exact known legacy backstop `triggerId` separately if it was not
migrated; do not cancel unrelated requested reminders or claim an unknown ID
was cancelled. Stop before securing work. A stale wake does not restart work,
clear a hold, or authorize a fresh registration.

A CI service started through named `bash` with `persist` continues after the
last Omp client exits. Stop that service by its name with
`write proc://<name>/kill`; it can otherwise keep watching a pull request
nobody is working. Omp has no pull-request subscription primitive. Record an
exceptional live watcher and failed cancellations in the epic handoff, not
successful timer identifiers. A durable process does not resume the
orchestrator or perform agent work.
