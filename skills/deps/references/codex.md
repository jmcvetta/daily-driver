# Codex routes — deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own**, so every call is `gh` in the shell.

**Dependabot PR context.** Search with `gh pr list --search "is:open
author:app/dependabot"`. Search results identify known upgrades and links to
mention when the batch supersedes them; they are not the inventory. When no
PRs are found, Dependabot configuration is absent or disabled, or it omits a
declared ecosystem, inspect project configuration, manifests and lockfiles,
then use each mapped manager's documented supported
outdated/dependency-discovery and bulk-upgrade commands. `app/dependabot` is
search syntax for a GitHub App, not a login; keep it inside `--search` rather
than using `--author`.

- **Marking the pull request ready**, once every check has reported green.
  `gh pr ready`.
- **Opening the pull request itself** is `pr`'s call — see that skill's own
  reference files.
