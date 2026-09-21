# Codex routes — pr-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own**, so both calls are `gh` in the shell.

- **Setting the body while opening a pull request.**
  `gh pr create --body-file <path>`.
- **Revising the body of an existing pull request.**
  `gh pr edit --body-file <path>`.

**`--body-file` rather than `--body`.** The body this skill writes carries
backticks, headings and a salutation in verse, and a double-quoted shell
argument substitutes every backtick and `$…` in it before `gh` sees the text.
Write the body to a file and hand over the path. That is the same argument
`epic` makes for an issue body, and it binds harder here, because a pull
request body is the larger document.

[`omp.md`](omp.md) names `--body` for the same operation. The hazard is `gh`'s
rather than Codex's, so that spelling is no safer there — but it is what the
Omp eval rows grade, and correcting it is a change with its own rows to
rewrite.

- **Labelling the pull request `human`** beside a body that carries the
  human-action blocker. `gh pr edit --add-label human`.
