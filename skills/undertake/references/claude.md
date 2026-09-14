# Claude Code routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `mcp__github__search_issues` |
| `Open the issue` | Open one, labelled | `mcp__github__issue_write`, method `create`, with `labels` |
| `Read the issue and its edges` | Read the body and the graph | `mcp__github__issue_read` |
| `Read the issue and its edges` | Label an issue that carries none | read `labels` with `mcp__github__issue_read`, then `mcp__github__issue_write`, method `update`, sending that set plus the new label |
| `Claim the issue` | Comment on the issue | `mcp__github__add_issue_comment` |

**The read in that row is not optional.** `labels` replaces the whole set, so
an update sending one label deletes every other label the issue had — the
stock and bot-owned ones `issue-labels` says to leave alone included. An
issue carrying none of the standard's five is not an issue carrying none.

`issue-deps` owns the edge writes, and has its own routes. So does
`issue-labels`, whose `references/claude.md` states that trap where the label
write lives.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `Ready for review` | Take it out of draft | `mcp__github__update_pull_request`, `draft: false` |
| `Keep it current` | Merge the base branch in | `mcp__github__update_pull_request_branch` |
| `A round after ready goes back to draft` | Return it to draft | `mcp__github__update_pull_request`, `draft: true` |

`Review the head` and `Fix, answer, resolve, push` are `review-cycle`'s, and
its own `references/claude.md` has the review surface, the wait and the thread
clients.


The session
===========

`mcp__Claude_Code_Remote__get_session`, with `session_id` omitted, describes
the caller. `task-worktree` consumes the designated branch when the call
supplies exactly one for this repository. `Claim the issue` then confirms the
task worktree is on that branch and reads the model and session from the same
call.

| What | Field |
| ---- | ----- |
| The designated branch | `session_context.outcomes[].git_repository.git_info.branches` |
| The repository it is pushed to | `session_context.outcomes[].git_repository.git_info.repo` |
| The model that served the turn | `external_metadata.last_served_model` |
| The model the session is set to | `session_context.model`, `configured_model` |
| The session id | the call's own `id`, for `https://claude.ai/code/session_…` |

Both branch fields are arrays. Read the outcome whose `git_info.repo` names the
repository this work will be pushed to. Exactly one branch is a designation;
more than one is a collision, not a pick. The branch checked out in the task
worktree must agree before the claim is posted.

`external_metadata.current_branches` is a different field and answers a
different question: what is checked out, not what the harness designated.

Where this call is absent, `Claim the issue` still records `session: n/a` and
reads the model from the harness environment. Read the branch from the task
worktree's Git state, and its repository from the remote `task-worktree`
resolved.


The cadence
===========

`Keep it current`'s check-ins need a durable wake, and Claude has one:
`mcp__Claude_Code_Remote__send_later`, two minutes out, cancelled with
`mcp__Claude_Code_Remote__delete_trigger`. It survives the session that armed
it, which is what makes a cadence across turns possible at all.

The slot it occupies is the same slot `review-cycle`'s wait borrows and hands
back, and the rule for both is
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md).
