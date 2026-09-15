# Omp routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The review surface
==================

The **`reviewer`** task agent, dispatched through the `task` tool: a
code-review specialist, taking the review brief for the pull request and
reading the diff through `pr://`.

**It takes no effort level.** The round names the agent and nothing more, and
the depth judgement is the agent's. `SKILL.md`'s `Name the level` has nothing
to bind here — there is no remembered level to override.

**Its findings do not land on the pull request as review threads.** They come
back in the agent's result and nowhere else, so the round carries them into
`Fix, answer, resolve, push` itself. That is the degradation `SKILL.md`
describes under `A reviewer, not a bare subagent`: nothing is posted for a
reviewer to resolve, so *resolve* reads as *answered*, and the caller's gate
reads its no-unresolved-thread condition the same way.


Fix-delta verification
======================

Dispatch exactly one `reviewer` task agent with a bounded brief. Give it the
pull request, full-review SHA, current SHA, original findings, dispositions,
and pass number. Require it to inspect `git diff <reviewed-sha> <current-sha>`
and affected callers, then report only whether each implemented finding is
solved and concrete regressions in that delta. It must not perform a full-PR
audit or offer style improvements.

The author records the result with `gh pr comment <number> --body-file <path>`:

```text
Review verification
scope reviewed: <sha>
pass: <1|2>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
cap: <open|hit>
usage: unavailable
```

The task agent's result is independent evidence. The author writes this record
only after receiving it; it must not invent a verdict. Omp exposes no reviewer
token-usage value, so `usage: unavailable` is required.

The wait
========

**`github.run_watch`.** The built-in `github` tool's `run_watch` op watches the
head commit's Actions runs and streams until every one has reported. Success is
double-checked with one more poll before it returns, and a failure names the
failed jobs.

It is a blocking watch, so the Actions half of the wait is one call. No
subscription, no backstop, no timer — the three things `claude.md` needs exist
because Claude has nothing that blocks.

**`run_watch` answers for Actions runs and nothing else**, and `SKILL.md` says
*reported* means the union of the check runs and the commit statuses. So the
wait is two reads, not one:

| Half | Call |
| ---- | ---- |
| The Actions runs | `github.run_watch` on the head commit |
| The commit statuses | `gh api /repos/{owner}/{repo}/commits/{sha}/status` |

Read the statuses **after** `run_watch` returns. A repository that posts none
answers with an empty `statuses` array and a `state` of `pending`, which is the
empty answer rather than a report: where the repository is known to post none,
it reports nothing and there is nothing to wait for; where one is expected and
has not arrived, keep reading.

**`run_watch` returns immediately on a pull request with zero Actions runs**,
which is the same empty answer and not the end of the wait. A head pushed
seconds ago has registered nothing yet.

**The fifteen-minute cap is the round's to keep**, because one blocking call
has nowhere to put it. Time the wait from the first read. On the cap, stop and
name what has not reported, as `SKILL.md` says.

`run_watch` is present wherever the `github` tool is enabled, which includes
the laptop Omp surface. The surface `SKILL.md` says cannot wait does not arise
here the way it arises on Claude.

There is no durable wake
------------------------

**`daily_driver_schedule` is an in-process managed timer, and a reminder dies
with the session.** Omp's own documentation says managed timers are unref'd and
cleared on `session_shutdown`. It is not a `send_later`, which survives the
session that armed it.

So the never-empty wake slot —
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) — is
Claude's rule and not this harness's. It has nothing to hold. `run_watch`
completes the wait inside the turn, so no wake is scheduled around it, and a
wake scheduled with nothing to do on it is the noise `0010` exists to prevent.
Schedule with `daily_driver_schedule`, and cancel with
`daily_driver_cancel_schedule`, only where the round must hand the pull request
back to itself for a follow-up **inside the current session** — never as a
watch that outlives it.


The review threads
==================

**The built-in `github` tool has no review-thread operation.** All three go
through the GitHub CLI and API.

| Operation | Call |
| --------- | ---- |
| Read the threads | `gh api /repos/{owner}/{repo}/pulls/{n}/comments` |
| Reply on a thread | `gh api -X POST /repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two here too: the
mutation takes the thread's `PRRT_…` node ID, and the reply takes the
comment's numeric id — the `#discussion_r…` suffix of its `html_url`.
