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
