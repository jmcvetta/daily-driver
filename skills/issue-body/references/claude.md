# Claude Code routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

- **Opening an issue with a body.** `mcp__github__issue_write`, `method:
  create`, `body` set.
- **Replacing a body.** `mcp__github__issue_write`, `method: update`, `body`
  set. The update replaces the body outright rather than appending, so it
  carries the whole new body and not the part that is new.


The model a task records
========================

The task body's `Model:` line names an identifier the harness can act on, and
`embark` passes that identifier to `mcp__Claude_Code_Remote__create_session`.
So it has to be one that call accepts — a marketing name recalled from
training is not one, and the session it opens fails rather than falling back.

**Read one rather than recall one.** `mcp__Claude_Code_Remote__get_session`,
with `session_id` omitted, reports this session's own identifier at
`session_context.model` — the model the session is currently set to run, and
the right answer for a task no lighter than the authoring session.

**`configured_model` is not that field and is not safe to copy.** The call's
own contract says it is echoed as stored, so it may be an alias or carry a
context-window suffix — which is exactly the identifier `create_session`
rejects, written into a `Model:` line that reads as correct. Take
`session_context.model`, and where only `configured_model` is available,
write no line.

The family, as the harness named it on 2026-09-11:

| Weight | Identifier |
| ------ | ---------- |
| Heaviest | `claude-opus-5` |
| Middle | `claude-sonnet-5` |
| Lightest | `claude-haiku-4-5-20251001` |

`claude-fable-5-1` exists beside these and is not a weight on that scale.
Model identifiers move; this table is a measurement with a date on it, not a
contract. Where it disagrees with what the harness reports, the harness is
right and this table is stale.

**`create_session` takes `model` and has no effort parameter.** Effort is
session configuration — `session_context.effort_level` — rather than a
dispatch argument, so it cannot be carried on a task issue. `SKILL.md` says
not to write an `Effort:` line, and this is why.
