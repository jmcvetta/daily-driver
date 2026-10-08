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
