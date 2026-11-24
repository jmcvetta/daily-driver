# Omp routes — pr

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

An opt-in [read-only shadow ledger](../../../docs/pr-supervision.md) can record
observations without taking this route's ownership. It is not a replacement
supervisor: no update, agent wake, subscription, or cutover is enabled. Keep the
existing service and owner continuation authoritative. Isolated proofs cover
cold CLI resumption, live-owner inbox receipt and transient controller restart;
they do not establish integrated active PR supervision or ownership transfer.

- **Checking whether a pull request already exists for the branch.**
  `gh pr view` (or `gh pr list --head <branch>`) finds it.
- **Opening a new pull request.** `daily_driver_gh_write({ args: ["pr", "create", "--draft", "--title", <title>, "--body-file", <path>] })`, for the initial
  state this skill requires.
- **Updating an existing pull request as a whole** — title and body
  together. `daily_driver_gh_write`, called once both are decided (`pr-title`,
  `pr-body`).


Base currency checkpoint
========================

After `gh pr create` or `gh pr edit`, read the resulting pull request:

```sh
gh pr view <number> --json state,baseRefName,headRefName,mergeStateStatus,headRefOid
```

The PR's `baseRefName` is authoritative; do not assume `master`. Merged or
closed PRs need no update. `DIRTY` is a conflict stop. `CLEAN` and `UNSTABLE`
need no currency write. `BEHIND`, `DRAFT`, `BLOCKED`, and `UNKNOWN` require a
currency attempt even when current-head CI is in flight. `DRAFT`, `BLOCKED`,
and `UNKNOWN` can mask branch currency, so the update call itself tests and
settles them.

Run `gh pr update-branch <number>`. Do not replace this with a local merge,
rebase, force-push, or prose about a future check. GitHub authors the
update-branch merge commit and its API does not accept a custom message. Do not
claim an agent-supplied trailer on that server-authored commit; keep this
server-side route.


After the call, read `state,baseRefName,headRefName,mergeStateStatus,headRefOid`
again. If `headRefOid` changed, read the check-run inventory, commit statuses,
and matching workflow runs for that new SHA before assessing the PR further.
Old-head checks and readiness evidence do not apply to it. Report a failed
update or conflict as unfinished work. An already-up-to-date response is a
valid no-op; it does not mark the PR ready or complete.

For an open PR without a conflict, after the checkpoint start or reuse the
detached watch below, including when CI is in flight. Merged, closed, or
user-stopped PRs start no watch. A conflict waits for resolution before
restart. `undertake` retains its own gate, not a second currency watch.

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

The script ticks every two minutes and uses `gh pr update-branch` for behind or
draft-masked currency, including while CI is in flight. It never judges CI,
reviews, or readiness. Exit 0 means merged or closed; exit 3 means a conflict
needs the owner. After resolving and pushing it, restart the watch. Thirty
consecutive failed reads exit 2 and require investigating access before a
restart. When the user stops maintenance, kill `proc://<name>` and do not
restart it on a stale wake. Stop any separate CI watcher through
`review-cycle`'s route.

The detached service supplies mechanical updates across client exits. It does
not replace `review-cycle`'s bounded CI watcher or the owner continuation below.

The owner continuation
=======================

**Keep one structured owner continuation alongside the detached service.**
Register with `daily_driver_watch({action: "register", key: <key>,
delaySeconds: 120, state: <state>})`, using
`pr:<host>/<owner>/<repo>#<number>` with lowercase host and repository. State
uses workflow `pr`, host, repository, PR number, branch and worktree, optional
ownerIssue, nextAction, authorityRefs, holds, workers, services and
observations. Record service names, CI head, window and deadline, and the
exact values compared below in named observations. Keep references to original
authority, not policy dumps, private source quotes or credentials. State is
reference data, not new authority. Explicit user holds persist until released.

Use `get` for the latest state. After relevant current reads or permitted work,
`checkpoint` the updated state and effective delay; an unrelated question or
event alone is not reconciliation. Registration maintains the fallback without
rearming on each turn, and a native service result can consume a coincident
timer after reconciliation. `review-cycle` borrows this same `pr:` record,
not a second review record. A standalone review owns its own record.

For live cutover cancel the exact known legacy owner `triggerId` first with
`daily_driver_cancel_schedule`; if cancellation fails, retain that owner,
report the failure and do not register another. An unknown trigger ID is not
silently migrated. Never cancel unrelated requested reminders. If an
authoritative #1038 supervisor is present, use it instead of registering a
second PR fallback.

**An unchanged look is silent and backs off.** Compare the PR's head SHA,
base currency, state, draft flag, labels, requested reviewers, check states,
review threads and comments, and service state with the exact observations
recorded at the previous look. With no change or available action, emit no
chat, toast, repeated GitHub status comment or "still watching" message, and
checkpoint at double the previous delay, capped at 1800 seconds. A changed
value, action taken, or missing comparison resets the delay to 120 seconds.
While current-head CI is pending or unregistered, retain 120 seconds. A
backed-off look can delay reporting a service conflict by up to the cap.
Meaningful progress, a changed required human contribution and whole-operation
completion may be reported concisely; always answer direct user questions.

Store waits as conditions and the next unmet action, not permanent instructions
to keep the PR draft. Completed preparation remains complete unless its
evidence is invalidated. Reconcile earlier state with current evidence and user
instructions; a satisfied condition no longer holds readiness.

If the detached service exits 3 for a conflict, inspect its recorded output
and the local task worktree. For a plain mechanical conflict, finish the base
merge locally in that worktree; do not ask the user to commit it. Start from
the PR's actual base with a clean index. Leave unrelated unstaged work in place:
do not stage, reset, stash, restore, or commit it. Resolve only the mechanical
conflict already established by the existing policy, and stage each resolved
path explicitly with `git add -- <path>` — never use `git add .`, `git add -A`,
or `git commit -a`. Before committing, confirm no unmerged paths remain and
the index contains only the conflict resolutions. If unrelated staged work
appeared, preserve it and coordinate rather than committing or resetting it.
Once all conflict paths are resolved and staged, prepare the intended merge
message with `daily_driver_commit_message` as described by
[`provenance`](../../provenance/references/omp.md#commits). Pass the
substantive merge body as `body`, read `result.details.body`, and write a
private message file containing the merge subject, a blank line, and that
prepared body. Run `git commit --file <message-file>` to conclude the
in-progress merge, then remove the temporary file. This is the narrow exception
to Omp's selective-commit helper, which refuses commits during an in-progress
merge. Do not skip hooks or signing. Push the task branch normally, restart the
maintenance watch, and send the changed content through `review-cycle`.
A resolved merge is a content change: it still requires current-head CI and
review.

Runtime timers stop on session shutdown; same-session resume restores journaled
deadlines, but no watch runs across shutdown. If registration or checkpoint
fails, diagnose and report the exact continuation gap; do not claim an armed
owner. Keep supervising an existing CI service where possible.

On merge, close, completion, a genuine human-only stopping point, or user stop,
stop the matching `daily_driver_watch` record and owned services. Stop before
a stop-time push. A stale wake cannot clear a hold, do work or register again.
A stopped key stays stopped; only a later explicitly authorized invocation may
use the canonical key plus `:run:<uuid>` for a fresh run.

The catch-up look
-----------------

Check user interruptions before catch-up: answer a direct question from known
evidence before tools, and obey a stop through the workflow's stop procedure.
A stale wake after a user stop does no work.

Before resuming PR work, read `proc://keep-current-<number>` and inspect
failures, then run the `Base currency checkpoint`. Assess current-head CI
through `review-cycle`'s three-source read and renewable bounded wait. Reuse
these results in the ready gate in the same turn; do not start another
catch-up look merely because the next action is marking ready.

Continue from the first unmet condition, not the start of the workflow.
Retain completed acceptance and runtime evidence with its artifact, head,
configuration and other relevant inputs. Rerun it only when those inputs
change or the evidence is incomplete, failed, expired under its contract, or
contradicted. Dynamic GitHub state still needs current reads: a changed head
needs its own CI, and new checks, comments, threads or blockers need assessment.
Do not edit an accurate PR body merely to narrate a gate pass or refresh
watch state; such edits can trigger new checks.

Known-running CI retains the structured owner continuation or supervised wait;
a detached service alone is not an owner continuation. Checkpoint only after
actual reconciliation, not merely because a turn occurred.

For an undertaking, continue its review and ready gate through
[`undertake`'s route](../../undertake/references/omp.md). A direct PR has no
undertaking claim.
