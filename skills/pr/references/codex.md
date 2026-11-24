# Codex routes — pr

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server and no
built-in `github` tool. Every call below is `gh` in the shell, which is the
half of the Omp routes that carries over unchanged.

- **Checking whether a pull request already exists for the branch.**
  `gh pr view` (or `gh pr list --head <branch>`) finds it.
- **Opening a new pull request.** `gh pr create --draft`, for the initial
  state this skill requires.
- **Updating an existing pull request.** Inspect title and body first, then
  run `gh pr edit` with only stale or incorrect fields (`--title` and/or
  `--body`). Make no update when both are accurate.

Keep it current
===============

Start this route immediately after creating or editing a PR and on every
owner turn that returns to it. Codex has no durable wake, process, or
subscription; do not claim autonomous maintenance.

Read the PR's state, actual base ref and SHA, head SHA, repository and conflict
state. Stop on terminal state, user stop or conflict. Compare pinned base and
head using GitHub's compare endpoint in the PR base repository. A validated
merge base equal to the base SHA proves currency; a consistent positive
`behind_by` proves staleness. Unavailable or inconsistent comparison is unknown
and permits no write. Immediately before updating, revalidate authority,
state, base ref and SHA, head SHA, conflict and comparison. Only the same
proven stale pair permits an expected-head update-branch request, regardless
of CI. Treat 202 as pending and observe without replay until settled; compare
again after any later base advance.

After an update that can move the head, read `gh pr view <number> --json
headRefOid,statusCheckRollup` and both check and status endpoints again.
Pending checks use `review-cycle`'s bounded wait. There is no timer or
subscription to cancel when the watch stops.
