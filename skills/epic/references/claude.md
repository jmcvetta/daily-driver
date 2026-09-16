# Claude Code routes — epic

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The issues
==========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Size the work` | Read an issue already in hand | `mcp__github__issue_read` |
| `Open the issues` | Search the open issues | `mcp__github__search_issues` |
| `Open the issues` | Open the epic, and each task | `mcp__github__issue_write`, `method: create`, with `labels` |
| `Open the issues` | Turn an existing issue into the epic | read `labels` with `mcp__github__issue_read`, then `mcp__github__issue_write`, `method: update`, sending that set with the old standard label swapped for `epic` |
| `Fill in the epic` | Replace the epic's body | `mcp__github__issue_write`, `method: update` |

`method: update` replaces `body` outright rather than appending to it, so
`Fill in the epic` sends the whole of `The epic body` and not the part that is
new.


The parent, at creation
=======================

**The read in that row is not optional.** `labels` replaces the whole set, so
an update sending `["epic"]` deletes every other label the issue had — the
stock and bot-owned ones `issue-labels` says to leave alone included. A new
issue has nothing to lose and needs no read; a converted one does.

`mcp__github__issue_write` with `method: create` takes `parent_issue_number`,
and attaches the new issue to that parent in the same operation. Where that
field is available, a task opened at `Open the issues` arrives parented and
`Write the graph` has only the edge to verify — it still verifies, because the
write response is the issue you modified and `issue-deps` requires the read
from the other end regardless of which call made the edge.

**It is not available everywhere.** `issue-deps` records two generations of
the GitHub MCP server, and the older one has no sub-issue write at all: there,
`Write the graph` has no parent route and says so rather than reporting a
parent it did not set. Read that skill's routes before believing this one.

The field cannot be combined with `issue_fields`, and it is read on `create`
only. An issue that already exists is re-parented through `issue-deps`' own
routes, not here.


The graph
=========

`issue-deps` owns both relationships and picks its own client — which for
blocked-by on a Claude Code web worker is its script rather than the MCP,
because neither generation of the GitHub MCP server writes that edge at all.
Read that skill's routes before `Write the graph`.


The model a task records
========================

The `Model:` line and the identifiers it may name are `issue-body`'s — see
`skills/issue-body/references/claude.md` for the routes. The task bodies are
written under that skill's contract at `Open the issues`; nothing here reads
or writes the line.
