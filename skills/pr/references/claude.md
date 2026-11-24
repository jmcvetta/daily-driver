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
- **Updating an existing pull request.** Inspect title and body first, then
  call `mcp__github__update_pull_request` only with stale or incorrect fields
  set. Make no update when both are accurate; keep the identified remote push
  head and do not create a second PR for the execution branch.
 
Keep it current
===============

Start this route after creating or updating a PR. Arm one
`mcp__Claude_Code_Remote__send_later` wake two minutes out; reuse the pending
trigger, and retain its `trigger_id`. Cancel it with
`mcp__Claude_Code_Remote__delete_trigger` when the PR is merged, closed, or
the user stops the watch.

The scheduled prompt carries this whole check-in, including its PR identity
and the instruction to re-arm itself. **Re-arm first on every wake:** reuse a
pending trigger or schedule the same prompt two minutes out before taking the
reads below. Retain the new identifier. A wake with no successor loses
maintenance after one tick.

Read the PR's state, repository, actual base ref and SHA, head SHA and conflict
state. Stop on terminal state, user stop or conflict. Compare the pinned base
and head through GitHub's compare endpoint in the PR base repository. A
validated merge base equal to the base SHA proves currency; a consistent
positive `behind_by` proves staleness. An unavailable or inconsistent
comparison is unknown, never permission to write. Immediately before a stale
update, re-read authority, state, both SHAs, base ref, conflict and comparison.
Only the same proven stale pair permits an expected-head update-branch request;
CI is not a prerequisite. A 202 is pending, not completion: observe without
replaying until settled, and compare again after any later base advance.

After an update that can move the head, read `head.sha`, `get_check_runs`, and
`get_status` again. The CI wait and result assessment use `review-cycle`'s
routes. Its wait may borrow this wake; cancel the borrowed trigger at `End the
wait` and arm one replacement before the turn ends.
