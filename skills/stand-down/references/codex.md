# Codex routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in [`claude.md`](claude.md)
and Omp's in [`omp.md`](omp.md); Omp carries the same subagent fallback as
this one, on a surface measured further.


What this surface has not been measured to do
=============================================

**The delegation namespace has never been driven.**
[#181](https://github.com/jmcvetta/daily-driver/issues/181) could not reach
the `multi_agent_v1` path — the finding `embark`'s
[`codex.md`](../../embark/references/codex.md) records — and nothing since
has measured it. Stopping is therefore specified against the namespace
rather than against its tools, the way dispatch is: a Codex session
attempting the cancellation route below uses whatever the namespace
resolves, takes the one bounded retry `SKILL.md` allows, and reports what
it could not stop as a residual. A fleet member left running is named in
the epic's stand-down record — that is the recovery path, and it is
worth more than a loop pretending to stop what it cannot reach.

**What secures the work is this session, not the delegation.** Once the
cancellation attempt above has been made — reached or not — the fallback
worktree is this session's to commit and push directly, exactly as it is on
Omp. The commit and the push do not depend on the delegation namespace being
driven; they are ordinary Git calls this session already has.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `gh issue view <epic> --json comments` |
| `Read the fleet` | Read a task issue's claim and handoff | `gh issue view <number> --json comments` |
| `Secure the work` | Cancel a delegation | `multi_agent_v1`, one attempt per implementor — unmeasured; a refusal is a residual |
| `Secure the work` | Stage and commit the worktree | `git -C <worktree> add <named files>` then `git -C <worktree> commit -m <message>` |
| `Secure the work` | Push the branch | `git -C <worktree> push` |
| `Write the handoff` | Read a task's pull-request state | `gh pr view <number>` |
| `Write the handoff` | Comment on a task issue or the epic | `gh issue comment <number> --body-file <path>` |
| `Cancel the watches` | — | no timer, no watcher, no subscription exists on this surface |

`--body-file` on every comment write, for the reason the other fallback
routes give: the handoff carries backticks and identifiers a shell argument
would mangle.

**`Stop the fleet` has nothing left to do on this harness.** The cancellation
attempt, the commit, and the push all happened at `Secure the work`, before
the handoff was written; this step is a no-op for every fallback fleet
member.

**The commit and push follow `SKILL.md`'s work-in-progress rule**: named
files staged (never `git add -A` or `git add .`), a message that marks the
commit plainly as unfinished stand-down work, no hook and no test skipped, no
pull request opened. `git -C <worktree> status --short` first decides
whether there is anything to stage; a worktree with nothing to commit is
still pushed, so a branch already committed but not yet pushed still reaches
origin. A worktree that will not stage, commit, or push is a residual for the
banner rather than a retried operation.

The fallback's worktrees follow the repository's `task-worktree` convention
and live beside the primary worktree; the handoff names the path, and the
branch — pushed at `Secure the work` rather than left for a resumed session
to find — carries whatever was in progress. There is nothing to archive on
this harness: a delegation is stopped and reported, not archived — the
archive call is a web-session route.


The watches
===========

**There is nothing to cancel on this harness.** No durable wake exists —
`review-cycle`'s [`codex.md`](../../review-cycle/references/codex.md)
measured that, and a stand-down inherits the finding rather than re-measuring
it — so the backstop timer has no identifier and nothing to cancel. No
pull-request subscription surface exists, and no persistent watcher process
is kept by this skill on Codex. The watches step on this harness is empty
by measurement, not by omission, and the epic's stand-down comment records
"none" where another harness would record identifiers.

Provenance: `codex-cli 0.154.0`, read on 2026-09-12, through
[#181](https://github.com/jmcvetta/daily-driver/issues/181) — the same
provenance `embark`'s file records, inherited rather than re-measured.
