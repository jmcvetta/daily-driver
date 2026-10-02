# Claude Code routes — session-title

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

Two calls, in order, on the Claude Code Remote server:

1. `get_session` with `session_id` omitted — describes the caller, and
   answers this session's own id.
2. `set_session_title` with that `session_id` and the title.

**The server prefix is whatever the session registers.** The tools were
offered as `mcp__claude-code-remote__get_session` and
`mcp__claude-code-remote__set_session_title` on 2026-10-02, and as
`mcp__Claude_Code_Remote__…` in earlier sessions. Judge absence by the
operation name, never by the prefix: a prefix that differs from the one
written here is the same server, not a missing surface.

`set_session_title` accepts 500 characters. The forty-character budget in
`SKILL.md` is this skill's own cap, not the tool's.

Both tools exist only on the Claude Code Remote surface. Where no tool with
either operation name is offered — a laptop session — there is no way to set
the title from here.
