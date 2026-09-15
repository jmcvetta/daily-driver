# Codex routes — epic

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` cache behind it. There is one
client, `gh` in the shell.


The issues
==========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Size the work` | Read an issue already in hand | `gh issue view <number>` |
| `Open the issues` | Search the open issues | `gh search issues` |
| `Open the issues` | Open the epic, and each task | `gh issue create --label epic` / `--label task` |
| `Open the issues` | Turn an existing issue into the epic | `gh issue edit <number> --body-file <path> --add-label epic --remove-label <the old one>` |
| `Fill in the epic` | Replace the epic's body | `gh issue edit <number> --body-file <path>` |

`--body-file` rather than `--body`: an epic body carries a fenced block and a
table, and passing that through a shell argument is where the quoting breaks.
Write the body to a file and hand over the path.


The parent, at creation
=======================

**`gh issue create` does not take a parent**, so the parent is a second write
here and `Write the graph` does it — through `issue-deps`, which reaches
sub-issues on this harness when `gh` is at its stated floor.


The graph
=========

`issue-deps` owns both relationships and picks its own client, and on this
harness it has two rather than three to pick from. Read that skill's routes
before `Write the graph`.


The model a task records
========================

The `Model:` line and the identifiers it may name are `issue-body`'s — see
`skills/issue-body/references/codex.md` for how this harness reads it. The
task bodies are written under that skill's contract at `Open the issues`;
nothing here reads or writes the line.
