# Omp routes — pr-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

- **Setting the body while opening a pull request.**
  `gh pr create --draft --title "<title>" --body-file <path>`.
- **Revising the body of an existing pull request.**
  `gh pr edit --body "…"`.
- **Adding or removing the pull request `human` label** beside the matching
  blocker state. Use `gh pr edit --add-label human` or `gh pr edit --remove-label human`;
  remove only when current evidence satisfies the human action and preserve
  every unrelated label.
