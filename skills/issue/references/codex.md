# Codex routes — issue

`SKILL.md` names each move in words. This file names the call, for a session
running in Codex. Claude Code's routes are in [`claude.md`](claude.md),
Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` cache behind it. There is one
client, `gh` in the shell.

| Move | Operation | Call |
| ---- | --------- | ---- |
| Read what is there | Read the issue | `gh issue view <number>` |
| Read what is there | Search the open issues | `gh search issues` |
| The label | Set or swap a label | `gh issue edit <number> --add-label <label> --remove-label <the old one>` |
| The body | Open with a body | `gh issue create --label <label> --body-file <path>` |
| The body | Replace a body | `gh issue edit <number> --body-file <path>` |
| The edges | Blocked-by, parent, sub-issue | `issue-deps`'s own routes |

`--body-file` rather than `--body`: an issue body carries fenced blocks and
lists, and passing that through a shell argument is where the quoting breaks.
Write the body to a file and hand over the path.

**A label swap on this harness adds and removes in one call**, so the stock
and bot-owned labels `issue-labels` says to leave alone are never in
danger — the opposite of the Claude route, where the write replaces and the
read has to come first.
