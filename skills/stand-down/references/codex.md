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
| `Cancel the watches` | — | no timer, no watcher, no subscription exists on this surface |
| `Secure the work` | Cancel a delegation | `multi_agent_v1`, one attempt per implementor — unmeasured; a refusal is a residual |
| `Secure the work` | Stage and commit the worktree | `git -C <worktree> add <named files>` then `git -C <worktree> commit -m <message>` |
| `Secure the work` | Push the branch | `git -C <worktree> push` |
| `Write the handoff` | Read a task's pull-request state | `gh pr view <number>` |
| `Write the handoff` | Comment on a task issue or the epic | `gh issue comment <number> --body-file <path>` |

`--body-file` on every comment write, for the reason the other fallback
routes give: the handoff carries backticks and identifiers a shell argument
would mangle.

Inspect `git -C <worktree> status --short` before applying the shared
`Secure the work` rule. This harness has no archive operation; an unmeasured
cancellation refusal is a residual.

Read `git -C <worktree> rev-parse HEAD` and `git ls-remote origin <branch>`
separately. Include the observed remote head and any local-only commit and
worktree path when they affect recovery. Record an unavailable read only when
that uncertainty affects safe recovery; never infer the remote tip locally.


The watches
===========

**There is nothing to cancel on this harness.** No durable wake exists —
`review-cycle`'s [`codex.md`](../../review-cycle/references/codex.md)
measured that, and a stand-down inherits the finding rather than re-measuring
it — so the backstop timer has no identifier and nothing to cancel. No
pull-request subscription surface exists, and no persistent watcher process
is kept by this skill on Codex. Do not manufacture a watch residual or record
successful transient identifiers.

Provenance: `codex-cli 0.154.0`, read on 2026-09-12, through
[#181](https://github.com/jmcvetta/daily-driver/issues/181) — the same
provenance `embark`'s file records, inherited rather than re-measured.
