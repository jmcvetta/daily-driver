# Claude Code routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

- **Opening an issue with a body.** `mcp__github__issue_write`, `method:
  create`, `body` set.
- **Replacing a body.** `mcp__github__issue_write`, `method: update`, `body`
  set. The update replaces the body outright rather than appending, so it
  carries the whole new body and not the part that is new.


The required class
==================

Task bodies use the provider-neutral `Model class` section defined in
[`model-classes.md`](model-classes.md). Before creating a session, `embark`
resolves that class to a currently valid concrete identifier. It never passes
`standard`, a configured alias, or a suffixed `configured_model` value as the
`model` argument.

`mcp__Claude_Code_Remote__get_session`, with `session_id` omitted, reports the
current session's concrete model at `session_context.model`; use it only after
checking it against the class guidance. Keep `configured_model` distinct: it
can be an alias or unsupported suffix. `create_session` has no effort
argument; effort remains harness configuration.
