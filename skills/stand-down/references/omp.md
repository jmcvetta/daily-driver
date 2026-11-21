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
| `Cancel the watches` | Cancel the backstop timer | `daily_driver_cancel_schedule`, by the trigger id the call returned |
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


The watches
===========

`daily_driver_schedule` is a managed timer cleared on session shutdown, so a
backstop armed for the wave dies with this session regardless — cancel it so
the reminder cannot fire into the last turn. A CI service started through
named `bash` with `persist` continues after the last Omp client exits. Stop
that service by its name with `write proc://<name>/kill`; it can otherwise
keep watching a pull request nobody is working. Omp has no pull-request
subscription primitive; the subscriptions row of the epic's stand-down
record is empty on this harness. A durable process does not resume the
orchestrator or perform agent work.
