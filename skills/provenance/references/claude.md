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

**The serving provider** follows `SKILL.md`'s precedence; this call names no
provider identity of its own. Record, in order:

1. A serving provider that a harness surface explicitly reports.
2. `Anthropic` when the session is a verified official Claude cloud session —
   one its environment or harness identifies as running in Anthropic's
   first-party Claude Code cloud — or when the CLI configuration is positively
   identified as direct Anthropic API or another first-party Anthropic
   service.
3. The actual provider when the CLI configuration is positively identified as
   a third-party backend such as Bedrock or Vertex AI.
4. Otherwise `n/a`.

A Claude model id or `Harness: Claude Code` alone never proves the serving
provider. A Claude CLI session whose backend is not positively identified
records `Provider: n/a`, and the cloud rule is never generalized to every
Claude session.

Where this call is absent, read the model from the harness's own statement of
what is serving the turn, and record `Session: n/a`.

**The harness version** is `claude --version`, where a shell is available. A
version no surface in the session reports is `n/a`, never a guessed one.


Commits
=======

Claude Code appends `Co-Authored-By` and `Claude-Session` trailers to a
commit the session makes, filled from the model and session values above. The
agent adds neither trailer itself, and never adds a second copy of either —
that duplicate is the one `SKILL.md`'s `Commits` section forbids.
