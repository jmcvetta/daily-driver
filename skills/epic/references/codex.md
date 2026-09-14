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

`Draft the plan` writes a `Model:` line into each task issue. On Claude Code
the line is passed to the session client, binding. Here `embark` runs its
subagent fallback — the session-opening `agent_tasks` namespace is one this
plugin cannot reach, so the wave goes out as local subagents instead — and
there the line is advisory: the fallback's default is a cheaper implementation
model, and the line is the judgement `embark`'s orchestrator reads before
deciding whether that default is safe for this task. Nor does anything here
report the running session's own model, so the identifier cannot be read off
the session the way the Claude route reads it.

Write it anyway, exactly as the Omp route does. The judgement is made here, at
decomposition time, and a task issue planned on Codex is undertaken wherever
the wave is put to sea. The identifiers are the ones the Claude session client
accepts, and [`claude.md`](claude.md) is where they are named — with the
warning that the table there is a measurement with a date on it. A recalled
identifier is not one: where `claude.md` cannot be read, write no line rather
than guess at a name.
