# Omp routes — pr

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

- **Checking whether a pull request already exists for the branch.**
  `gh pr view` (or `gh pr list --head <branch>`) finds it.
- **Opening a new pull request.**
  `gh pr create --draft --title "<title>" --body-file <path>`, for the initial
  state this skill requires.
- **Updating an existing pull request as a whole** — title and body
  together. `gh pr edit`, called once both are decided (`pr-title`,
  `pr-body`).


Base currency checkpoint
========================

After `gh pr create` or `gh pr edit`, read the resulting pull request:

```sh
gh pr view <number> --json state,baseRefName,headRefName,mergeStateStatus,headRefOid,statusCheckRollup
```

The PR's `baseRefName` is authoritative; do not assume `master`. Merged or
closed PRs need no update. `DIRTY` is a conflict stop. `CLEAN` and `UNSTABLE`
need no currency write. `BEHIND`, `DRAFT`, `BLOCKED`, and `UNKNOWN` require a
currency attempt unless current-head CI is in flight. `DRAFT`, `BLOCKED`, and
`UNKNOWN` can mask branch currency, so the update call itself tests and settles
them.

Before an update, inspect the PR's current head through `review-cycle`'s
three-source CI read: the check-run inventory, commit statuses, and matching
workflow runs. If any source shows a current-head run in flight, leave the
branch alone and state that condition; do not call an old green result current.
Otherwise run `gh pr update-branch <number>`. Do not replace this with a local
merge, rebase, force-push, or prose about a future check.

After the call, read `state,baseRefName,headRefName,mergeStateStatus,headRefOid`
again. If `headRefOid` changed, read the check-run inventory, commit statuses,
and matching workflow runs for that new SHA before assessing the PR further.
Old-head checks and readiness evidence do not apply to it. Report a failed
update or conflict as unfinished work. An already-up-to-date response is a
valid no-op; it does not mark the PR ready or complete.

For an open PR without a conflict, after the checkpoint start or reuse the
detached watch below even when draft or CI deferred the update. Merged,
closed, or user-stopped PRs start no watch. A conflict waits for resolution
before restart. `undertake` retains its own gate, not a second currency watch.

The watch is a detached Omp service
===================================

Start the loaded plugin's `scripts/pr-keep-current.sh` after PR creation or
update. Resolve its absolute path from the loaded `skills/pr/SKILL.md` path,
not from an unrelated target repository. Use Bash service mode with `name`
`keep-current-<number>` and `cwd` set to the task checkout of the repository
that owns the PR. The command is
`printf 'keep-current-started\n'; exec bash <absolute-script-path> <number>`
and `ready` is `{"log": "keep-current-started"}`. Omit `async` and `timeout`.
The marker proves launch only, not a successful update.

Read `proc://<name>` before starting. Reuse a running watch; restart an exited
one only after inspecting and fixing its reported failure. Immediately after
launch read it again. If it exited, report its logs and exit status. Otherwise
write `detached` to `proc://<name>/mode` and read it back to confirm
`detached=true`. On mode failure or missing confirmation, kill the service
and report the failure. Never claim durability without confirmation.

The script ticks every two minutes, defers in-flight CI, and uses
`gh pr update-branch` for behind or draft-masked currency. It never judges CI,
reviews, or readiness. Exit 0 means merged or closed; exit 3 means a conflict
needs the owner. After resolving and pushing it, restart the watch. Thirty
consecutive failed reads exit 2 and require investigating access before a
restart. When the user stops maintenance, kill `proc://<name>` and do not
restart it on a stale wake. Stop any separate CI watcher through
`review-cycle`'s route.

`daily_driver_schedule` is not durable: its timers are cleared on shutdown.
Do not use it for this cadence. The detached watch starts while draft, but
does not replace `review-cycle`'s bounded CI watcher or resume the owner.

The catch-up look
-----------------

A stale wake after a user stop does no work. Otherwise every owner turn
returning to the PR first reads `proc://keep-current-<number>` and runs the
`Base currency checkpoint`. Then assess current-head CI through
`review-cycle`'s three-source read and bounded wait. Report failed checks or
missing evidence as unfinished work. A durable service preserves mechanical
updates, not autonomous review; name the owner-resume requirement when no
owner turn is available.

For an undertaking, continue its review, ready gate, and milestone through
[`undertake`'s route](../../undertake/references/omp.md). A direct PR has no
undertaking claim or first-readiness report to publish.
