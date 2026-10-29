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

`undertake` still owns its pre-ready gate and post-ready `keep-current-<number>`
service. This checkpoint adds the first required update to the ordinary `pr`
workflow; it does not replace that ongoing watch.
