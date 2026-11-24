# Omp routes — deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

**Dependabot PR context.** Search with the `github` tool's `search_prs` op,
using `is:open author:app/dependabot`. Search results identify known upgrades
and links to mention when the batch supersedes them; they are not the
inventory. When no PRs are found, Dependabot configuration is absent or
disabled, or it omits a declared ecosystem, inspect project configuration,
manifests and lockfiles, then use each mapped manager's documented supported
outdated/dependency-discovery and bulk-upgrade commands. The tool exposes no
list op; `gh pr list` is the only listing call, and a plain listing cannot
apply an author filter.

- **Marking the pull request ready**, once every check has reported green.
  `gh pr ready`.
- **Opening the pull request itself** is `pr`'s call — see that skill's own
  reference files.
