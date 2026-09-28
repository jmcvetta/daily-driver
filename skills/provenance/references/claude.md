# Claude Code routes — provenance

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


The block
=========

`mcp__Claude_Code_Remote__get_session`, with `session_id` omitted, describes
the caller.

| What | Field |
| ---- | ----- |
| The model that served the turn | `external_metadata.last_served_model` |
| The model the session is set to | `session_context.model`, `configured_model` |
| The session id | the call's own `id`, for `https://claude.ai/code/<id>` |

Where this call is absent, read the model from the harness's own statement of
what is serving the turn, and record `session: n/a`.

**The harness version** is `claude --version`, where a shell is available. A
version no surface in the session reports is `n/a`, never a guessed one.


Commits
=======

Claude Code appends `Co-Authored-By` and `Claude-Session` trailers to a
commit the session makes, filled from the model and session values above. The
agent adds neither trailer itself, and never adds a second copy of either —
that duplicate is the one `SKILL.md`'s `Commits` section forbids.
