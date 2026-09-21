# Omp routes — stand-down

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

**Omp has no session-opening client, so the fleet on this harness is
harness-local subagents** — one per task, dispatched as one concurrent
`task` batch, exactly as `embark`'s
[`omp.md`](../../embark/references/omp.md) records. There is nothing to
interrupt and nothing to archive: a subagent is cancelled by its dispatch
handle, and the cancellation is immediate and unconfirmed. What survives it
is the recovery: the subagent's worktree and branch are state on this
machine, which is why the handoff names both.


The fleet
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the fleet` | Read the epic's muster rolls | `gh issue view <epic> --json comments` |
| `Read the fleet` | Read a task issue's claim and handoff | `issue://<number>`, comments included |
| `Read the fleet` | Read the live dispatch handles | `hub jobs` over the dispatch batch's job ids |
| `Write the handoff` | Comment on a task issue or the epic | `gh issue comment <number> --body-file <path>` |
| `Stop the fleet` | Cancel a subagent | `hub cancel`, `ids:` the dispatch job ids |
| `Cancel the watches` | Cancel the backstop timer | `daily_driver_cancel_schedule`, by the trigger id the call returned |
| `Cancel the watches` | Stop a persistent CI watcher | `hub stop`, by the process name the watch started |

`--body-file` on every comment write, for the reason the other skills'
routes give: the handoff carries fenced blocks, backticks and identifiers,
and a double-quoted shell argument substitutes them before `gh` sees them.

`hub cancel` returns at once and never confirms the job died — that is the
route, not a limitation to work around. `SKILL.md`'s no-poll rule is what
the surface delivers. A job id the `hub jobs` read no longer lists is one
that finished on its own; it is recorded as retired, not cancelled.

**The worktree is the state that survives.** A cancelled subagent's worktree
stays on disk beside the primary checkout, and its branch holds whatever was
pushed. The handoff names both; the resumed `embark` re-dispatches on the
same branch and picks the worktree up from there.


The watches
===========

`daily_driver_schedule` is a managed timer cleared on session shutdown, so a
backstop armed for the wave dies with this session regardless — the cancel
runs anyway, so a reminder cannot fire into the last turn. A CI watcher
started through `hub start` with `persist: true` does **not** die with the
session: it is stopped by name here, or it outlives the stand-down and keeps
watching a pull request nobody is working. Omp has no pull-request
subscription primitive; the subscriptions row of the epic's stand-down
record is empty on this harness, and the route table above is the whole
watch inventory.
