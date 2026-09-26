# Omp routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

Two clients share the work. The built-in `github` tool reads and writes what it
covers; `gh` covers the rest, and every read is also available as an `issue://`
or `pr://` internal URL, which resolves from the same cache the `github` tool
writes to.


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `github.search_issues`, or `gh search issues` |
| `Open the issue` | Open one, labelled | `gh issue create --label task` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `issue://<number>`, comments included |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> -b "…"` |

**Before `Claim the issue`, check the session title.** Read `sessionName` from `daily_driver_get_session`, which the claim already needs for its model and session id. Format the expected title as `#{number} {shortened issue title}` using `session-title`'s forty-character budget and shortening rules. If it differs, call `daily_driver_set_session_title({ title })` before `gh issue comment`; if it already matches, do not rename it. If the title surface is unavailable, report that limitation and continue without an alternate route, as `session-title` requires.

**`issue://<number>` carries the comments**, so the read in that row is one
call and returns the handoff content `SKILL.md` asks for. Where a cache miss
or a truncated resource leaves them out, `gh issue view <number> --json
comments` is the read that returns them — the same call the readiness report
makes further down this file.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/omp.md` says why `--add-label` needs no
read-first and the Claude route does.

For a `task`, read the `Model class` section and assess the current session
against [`issue-body`'s guidance](../../issue-body/references/model-classes.md)
before its claim or repository change. A suitable stronger session implements
directly. An unsuitable or unassessable session reports the mismatch; it does
not delegate merely to change cost.


The implementor
===============

No route, and that is the rule rather than a gap. `SKILL.md`'s `Implement`
owns it: the session running the sequence writes the code itself, so `task`
dispatches no implementor here. Omp has the route and it belongs to `embark`,
which uses it to run several task issues at once. The one dispatch inside this
sequence is `review-cycle`'s briefed subagent at `Verify the fix delta`, named
in that skill's own reference file.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/omp.md` owns them |
| `The gate` | Read the review record | `gh pr view <number> --json comments` — the round's own `Review` and `Review verification` comments |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |
| `The milestone` | Read the readiness state | `gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `gh pr comment <number> --body-file <path>` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/omp.md` names the reviewer task, durable
record, and bounded delta-pass contract.


The session
===========

**The claim reads the model and the session id from
`daily_driver_get_session`**, the tool `extensions/daily-driver.js` registers.
It answers this session's own id (`ctx.sessionManager.getSessionId()`), its
name, and the id of the model serving it. The claim records both verbatim —
`Model: <model>` and `session: <id>`, one line each, no note about where the
values came from. Omp has no web URL for a session, so the id goes in bare
rather than linked.

The branch comes from the task worktree's Git state:
`git branch --show-current` runs in that worktree. `OWNER/REPO` for the branch
link comes from the remote `task-worktree` resolved, never from an assumed
`origin`.


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it.

**The readiness state is one read:**

    gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid

`isDraft` false and `mergeable` `MERGEABLE` are two of the answers the report
needs, and neither is sufficient alone. `mergeStateStatus` answers the rest,
and here — after the draft is cleared — `CLEAN` is the only yes: `BEHIND` is
a base the branch does not carry, `UNSTABLE` a check that is no longer green,
`DIRTY` a conflict, and `UNKNOWN` and `BLOCKED` are states `SKILL.md` rules
out as readiness outright. Each is a wait, not a milestone. **`The gate` reads
the same field for less**, because a draft reports `DRAFT` or `BLOCKED` there
whatever its branch and checks are doing: only `BEHIND`, `DIRTY` and `UNKNOWN`
are that read's, and CI at the gate comes from `statusCheckRollup` instead.
`headRefOid` is the SHA the report binds to.

**The start is the claim comment's `createdAt`.** `issue://<issue>` carries
the comments, so `Read the issue and its edges` already has them; `gh issue
view <issue> --json comments` is the same read where that resource is not to
hand. The claim is the comment carrying the branch link and the `Model:` and
`session:` lines. Take its `createdAt`;
where more than one comment carries that shape, the earliest of them is the
start — a later claim does not restart the clock. A resumed session finds
the start with the read it makes anyway. An issue with no recoverable claim
leaves the timing `n/a`, per `SKILL.md`.

**The report posts as a pull-request comment** — a pull request's comments
are issue comments, so the write is the claim's own:

    gh pr comment <number> --body-file <path>

`--body-file` for the reason `Claim the issue`'s row gives: the report
carries backticks, a SHA, and timestamps, and a double-quoted shell argument
substitutes the backticks before `gh` sees them.

**Read the existing comments before posting** — `gh pr view <number> --json
comments` again, the report found by its opening line, `First-readiness
report`, the marker `SKILL.md` fixes; a resumed sequence that finds it posts
nothing.

**The provenance** comes from the sources `The session` names:
`daily_driver_get_session` for the model and the session id, the harness's
own statement of the serving model where the tool has none. The harness line
names Omp, with the version the harness itself reports — `omp --version`
where it answers. A version no surface in the session reports is `n/a`,
never a guessed one.


The watch is a detached Omp service
===================================

**The merge is mechanical, so the watch that runs it can be too.** Omp's
named Bash service owns the process lifecycle. Start the plugin's
`scripts/pr-keep-current.sh` with `bash` service mode, `name`
`keep-current-<number>`, its script path and pull-request number as the
command, and `cwd` set to a checkout of this repository. Service mode rejects
`async` and `timeout`; do not supply either field. Read `proc://<name>` before
starting so a resumed session does not restart an existing loop.

After the service reports ready, request `detached` through
`write proc://<name>/mode` with content `detached`, then confirm
`read proc://<name>` reports `detached=true`. Detached mode lets the process
survive broker shutdown and Omp exits. If the mode write fails or the status
does not confirm it, stop the service with `write proc://<name>/kill` and
report the exact failure; do not claim the watch is durable.

The script runs every two minutes. It reads the pull request's state, merge
status, and check rollup; skips the tick while a run on the head is in flight;
merges the base branch in when the branch is behind; and logs each move to
`proc://<name>`. Read that status and output with `read proc://<name>`.

Its exits are `Keep it current`'s three, and nothing narrower. It exits 0
when the pull request is merged or closed. It exits 3 on a conflict — the
call fails and changes nothing, and the stop is left for the session's
catch-up look below, whose `DIRTY` row restarts the loop once the conflict is
resolved and pushed. When the user says to stop, use
`write proc://<name>/kill`. Thirty consecutive failed reads exit 2: a watch
polling a repository it cannot read is noise, not a watch.

**`daily_driver_schedule` is not this cadence's vehicle.** The managed timer
is unref'd and cleared on `session_shutdown`, so a cadence it carried lived
only as long as the session — the failure that left ready pull requests
behind their bases indefinitely. The CI wait uses `review-cycle`'s bounded,
persistent named service, not a shell wait.

The catch-up look
-----------------

**The first read of every turn that lands back on an open undertaking pull
request is the base-currency read.** The detached service merges without a
session, but it does not judge: red CI, a review wall, a conflict, and the
milestone still need an agent turn. Read the service state and logs with
`read proc://keep-current-<number>`, then run:

    gh pr view <number> --json state,mergeStateStatus,mergeable,headRefOid

Merged and closed pull requests end continuation. Read `statusCheckRollup` and
`review-cycle`'s check and status endpoints before a currency merge; if either
reports a run in flight, skip that merge. Otherwise `BEHIND`, `DRAFT`,
`BLOCKED`, and `UNKNOWN` run `gh pr update-branch <number>`, whose own reply
settles draft-masked or indeterminate currency. `DIRTY` is the conflict stop;
`CLEAN` and `UNSTABLE` need no currency action.

**Currency is not completion.** After a currency test that can move the head,
read `gh pr view <number> --json statusCheckRollup` for the resulting
`headRefOid`; `review-cycle`'s two endpoint reads remain the CI verdict.
Pending or unregistered checks use its persistent bounded watcher. Failed
checks return to `Fix, answer, resolve, push`; unavailable logs are a named
evidence blocker, not green. A durable Omp service preserves its process, but
does not resume the owner: where no owner turn is running, report unfinished
work and the owner-resume requirement rather than claiming autonomous review.

The detached `keep-current-<number>` merge loop still starts at ready and
remains mechanical. It is not pre-ready CI supervision and never marks a
draft ready.
