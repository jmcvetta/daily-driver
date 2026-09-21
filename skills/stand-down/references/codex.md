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


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `gh issue view <epic> --json comments` |
| `Read the fleet` | Read a task issue's claim and handoff | `gh issue view <number> --json comments` |
| `Write the handoff` | Read a task's pull-request state | `gh pr view <number>` |
| `Write the handoff` | Comment on a task issue or the epic | `gh issue comment <number> --body-file <path>` |
| `Stop the fleet` | Cancel a delegation | `multi_agent_v1`, one attempt per implementor — unmeasured; a refusal is a residual |
| `Cancel the watches` | — | no timer, no watcher, no subscription exists on this surface |

`--body-file` on every comment write, for the reason the other fallback
routes give: the handoff carries backticks and identifiers a shell argument
would mangle.

The fallback's worktrees follow the repository's `task-worktree` convention
and live beside the primary worktree; the handoff names the path, and the
branch carries what was pushed. Nothing else of a delegation survives it.
There is nothing to archive on this harness: a delegation is stopped and
reported, not archived — the archive call is a web-session route.


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
