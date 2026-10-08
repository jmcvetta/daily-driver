# Codex routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` cache behind it. There is one
client, `gh` in the shell.

- **Opening an issue with a body.** `gh issue create --label <label>
  --body-file <path>`.
- **Replacing a body.** `gh issue edit <number> --body-file <path>`.

`--body-file` rather than `--body`: a handoff body carries fenced blocks and
lists, and passing that through a shell argument is where the quoting breaks.
Write the body to a file and hand over the path.


The required class
==================

Task bodies and frontier research assignments use the provider-neutral
`Model class` section defined in [`model-classes.md`](model-classes.md).
Codex dispatch must inspect the offered route and configuration, use an
eligible configured route when it can establish one, and otherwise report a
configuration gap. Do not invent model or effort arguments for an unmeasured
delegation surface.

Check the effective route, including overrides, configured fallbacks, and
visible parent-model inheritance. A route the harness identifies as
astra/fable is frontier regardless of its role name. Do not invent a Fable
identifier or assume an API route. Since the delegation route is unmeasured,
dispatch frontier only if the actual configured route and eligibility can be
established; otherwise stop that task with a configuration gap.

Frontier dispatch requires explicit user approval recorded with the assignment's
exact work envelope. Frontier implementation of ordinary work requires a
separate explicit user exception and bounded scope.
