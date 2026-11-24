# Claude Code routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

- **Opening an issue with a body.** Settle destination under
  [`issue`'s target repository rule](../../issue/SKILL.md#the-target-repository)
  and pass it in `mcp__github__issue_write`, `method: create`, with `body`;
  set `owner` and `repo` when the target differs from the current repository.
- **Replacing a body.** `mcp__github__issue_write`, `method: update`, `body`
  set. The update replaces the body outright rather than appending, so it
  carries the whole new body and not the part that is new.


The required class
==================

Task bodies, assignable epic stories of any eligible kind, and frontier
research assignments use the provider-neutral `Model class` section defined in [`model-classes.md`](model-classes.md). Before
creating a session, `embark` attempts automatic class-appropriate selection
through the supported Claude Code mechanism. It never passes a class name,
configured alias or unsupported suffixed `configured_model` as `model`.
If no supported route is available, explain and continue on the invoking
model without confirmation or repair. Do not apply Omp class-role semantics.

Do not invent a Fable identifier or assume an API route. Class labels describe
capability, not a permission check.

`mcp__Claude_Code_Remote__get_session`, with `session_id` omitted, reports the
current session's concrete model at `session_context.model`. Keep
`configured_model` distinct: it
can be an alias or unsupported suffix. `create_session` has no effort
argument; effort remains harness configuration.
