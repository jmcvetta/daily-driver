# Omp routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

**Omp has no session-opening client, so the fleet on this harness is
harness-local subagents** — one per task, dispatched as one concurrent
`task` batch, exactly as `embark`'s
[`omp.md`](../../embark/references/omp.md) records. There is nothing to
interrupt and nothing to archive: a subagent is cancelled by its dispatch
handle, and the cancellation is immediate and unconfirmed. **What secures
the work is this session, not the subagent**: once cancelled, this session
commits and pushes the worktree directly, on the same best-effort footing as
the cancel itself. An unconfirmed cancel does not guarantee the subagent has
stopped writing, so a collision — a concurrent git process holding
`.git/index.lock`, a file mid-write — is possible in the narrow window
between the two. A git failure from that collision is a residual like any
other failed stage, commit, or push, caught by the same check below; it is
not retried, and it is never read as a silent success. The recovery a
replacement picks up is whatever did reach origin, which is why the handoff
names the worktree too.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `gh issue view <epic> --json comments` |
| `Read the fleet` | Read a task issue's claim and handoff | `issue://<number>`, comments included |
| `Read the fleet` | Read a background task's job state | `read proc://<job-id>` using the job ID returned by `task` |
| `Secure the work` | Cancel a subagent | `write proc://<job-id>/kill`, using that same job ID |
| `Secure the work` | Stage and commit the worktree | `bash`, `git -C <worktree> add <named files>` then `git -C <worktree> commit -m <message>` |
| `Secure the work` | Push the branch | `bash`, `git -C <worktree> push`
| `Write the handoff` | Read a task's pull-request state | `pr://<number>` |
| `Write the handoff` | Comment on a task issue or the epic | `gh issue comment <number> --body-file <path>` |

| `Cancel the watches` | Cancel the backstop timer | `daily_driver_cancel_schedule`, by the trigger id the call returned |
| `Cancel the watches` | Stop a persistent CI service | `write proc://<name>/kill`, by the service name review-cycle started |

`--body-file` on every comment write, for the reason the other skills'
routes give: the handoff carries fenced blocks, backticks and identifiers,
and a double-quoted shell argument substitutes them before `gh` sees them.

`write proc://<job-id>/kill` returns without confirming the job stopped; that is the current route. Do not poll. This session commits and pushes after the cancellation request. A job ID no longer listed by `proc://` has finished on its own and is recorded as retired, not cancelled.

**`Stop the fleet` has nothing left to do on this harness.** The cancel, the
commit, and the push all happened at `Secure the work`, before the handoff
was written; this step is a no-op for every harness-local fleet member.

**The commit and push follow `SKILL.md`'s work-in-progress rule**: named
files staged (never `git add -A` or `git add .`), a message that marks the
commit plainly as unfinished stand-down work, no hook and no test skipped, no
pull request opened. `git -C <worktree> status --short` first decides
whether there is anything to stage; a worktree with nothing to commit is
still pushed, so a branch already committed but not yet pushed still reaches
origin. A worktree that will not stage, commit, or push — a detached HEAD, a
lock file left by the cancelled subagent, a rejected push — is a residual for
the banner rather than a retried operation.

**The worktree is the state that survives, and now the branch does too.** A
cancelled subagent's worktree stays on disk beside the primary checkout, and
its branch — pushed at `Secure the work` rather than left to a resumed
session to find — carries whatever was in progress. The handoff names both;
the resumed `embark` re-dispatches on the same branch and picks the worktree
up from there.


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
