# Claude Code routes — deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

**Dependabot PR context.** Search with `mcp__github__search_pull_requests`
using `is:open author:app/dependabot`. Search results identify known upgrades
and links to mention when the batch supersedes them; they are not the
inventory. When no PRs are found, Dependabot configuration is absent or
disabled, or it omits a declared ecosystem, inspect project configuration,
manifests and lockfiles, then use each mapped manager's documented supported
outdated/dependency-discovery and bulk-upgrade commands. Do not use
`mcp__github__list_pull_requests`: it takes no author filter, so the filter
would never be applied.

- **Marking the pull request ready**, once every check has reported green.
  `mcp__github__update_pull_request` with `draft: false`.
- **Opening the pull request itself** is `pr`'s call — see that skill's own
  reference files.
