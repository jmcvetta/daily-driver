# Omp routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

- **Opening an issue with a body.** `gh issue create --label <label>
  --body-file <path>`.
- **Replacing a body.** `gh issue edit <number> --body-file <path>`.

`--body-file` rather than `--body`: a handoff body carries fenced blocks and
lists, and passing that through a shell argument is where the quoting breaks.
Write the body to a file and hand over the path.


The model a task records
========================

The task body's `Model:` line is read two ways. On Claude Code, `embark`
passes it to the session client, binding. On this harness, `embark` runs its
subagent fallback, and there the line is advisory: the fallback's default is
a cheaper implementation model, and the line is the judgement `embark`'s
orchestrator reads before deciding whether that default is safe for this
task.

Write it anyway. The judgement is made at authoring time, and a task issue
planned on Omp is undertaken wherever the wave is put to sea. The identifiers
are the ones the Claude session client accepts, and [`claude.md`](claude.md)
is where they are named.

Nothing here reports the running session's own model, so the identifier
cannot be read off the session the way the Claude route reads it. Where
`claude.md` cannot be read, write no line rather than guess at a name.
