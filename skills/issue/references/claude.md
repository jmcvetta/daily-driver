# Claude Code routes — issue

`SKILL.md` names each move in words. This file names the call, for a session
running in Claude Code. Omp's routes are in [`omp.md`](omp.md), Codex's in
[`codex.md`](codex.md).

| Move | Operation | Call |
| ---- | --------- | ---- |
| Read what is there | Read the issue | `mcp__github__issue_read` |
| Read what is there | Search the open issues | `mcp__github__search_issues` |
| The label | Set or swap a label | `mcp__github__issue_write` with `labels` set |
| The body | Open with a body | `mcp__github__issue_write`, `method: create`, `body` set |
| The body | Replace a body | `mcp__github__issue_write`, `method: update`, `body` set |
| The edges | Blocked-by, parent, sub-issue | `issue-deps`'s own routes |

**`method: update` replaces `body` outright rather than appending**, so an
update carries the whole new body and not the part that is new.

**`labels` replaces the whole set too.** A swap therefore reads the issue's
current labels first and sends that set back with the old standard label
exchanged for the new one — otherwise the stock and bot-owned labels
`issue-labels` says to leave alone go with it. A new issue has nothing to
lose and needs no read.
