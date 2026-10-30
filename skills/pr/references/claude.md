# Claude Code routes — pr

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

- **Checking whether a pull request already exists for the branch.**
  `mcp__github__list_pull_requests` filtered by `head` finds it;
  `mcp__github__pull_request_read` reads one once its number is known. For
  ordinary and resume work, use the task branch. For the verified
  primary-held designation mapping, resolve the push repository and branch
  from the task worktree's configured upstream, and filter by that exact
  remote head (`OWNER:BRANCH`); never query the local execution name.
- **Opening a new pull request.** `mcp__github__create_pull_request`, with
  `draft: true` for the initial state this skill requires. For the mapped
  path, set its `head` to the designated push branch in its resolved remote
  repository. Never let GitHub infer the head from the local execution name.
- **Updating an existing pull request as a whole** — title and body
  together. `mcp__github__update_pull_request`, called once both are decided
  (`pr-title`, `pr-body`). Keep the identified remote push head; do not create
  a second PR for the execution branch.
 
Keep it current
===============

Start this route after creating or updating a PR. Arm one
`mcp__Claude_Code_Remote__send_later` wake two minutes out; reuse the pending
trigger, and retain its `trigger_id`. Cancel it with
`mcp__Claude_Code_Remote__delete_trigger` when the PR is merged, closed, or
the user stops the watch.

For each wake and each return to the PR, read `mcp__github__pull_request_read`
with method `get` for `state`, `draft`, `mergeable_state`, and `head.sha`, plus
`get_check_runs` and `get_status`. If the PR is merged or closed, cancel the
wake and exit. If the user has stopped the watch, cancel it and exit before
any update. If either CI endpoint reports a run in flight, defer the update.
For `behind`, `draft`, `blocked`, or an indeterminate merge state, update with
`mcp__github__update_pull_request_branch`. For `dirty`, stop before the update
and escalate the conflict. For `clean` or `unstable`, do not update the branch.

After an update that can move the head, read `head.sha`, `get_check_runs`, and
`get_status` again. The CI wait and result assessment use `review-cycle`'s
routes. Its wait may borrow this wake; cancel the borrowed trigger at `End the
wait` and arm one replacement before the turn ends.
