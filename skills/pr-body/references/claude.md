# Claude Code routes — pr-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

- **Setting the body while opening a pull request.**
  `mcp__github__create_pull_request` takes `body` directly.
- **Revising the body of an existing pull request.**
  `mcp__github__update_pull_request` with `body` set.
- **Labelling the pull request `human`** beside a body that carries the
  human-action notice. `mcp__github__update_pull_request` with `labels`
  set to the pull request's full label set — that call replaces, so read
  the existing labels first.
