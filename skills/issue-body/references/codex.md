# Codex routes — issue-body

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` cache behind it. There is one
client, `gh` in the shell.

- **Opening an issue with a body.** Settle destination under
  [`issue`'s target repository rule](../../issue/SKILL.md#the-target-repository)
  and pass it in `gh issue create --label <label> [--repo OWNER/REPO when the
  target differs from the current repository] --body-file <path>`.
- **Replacing a body.** `gh issue edit <number> --body-file <path>`.

`--body-file` rather than `--body`: a handoff body carries fenced blocks and
lists, and passing that through a shell argument is where the quoting breaks.
Write the body to a file and hand over the path.


The required class
==================

Task bodies, assignable epic stories of any eligible kind, and frontier
research assignments use the provider-neutral
`Model class` section defined in [`model-classes.md`](model-classes.md).
Codex dispatch makes the initial selection within the invoking family and
provider. Do not invent model or effort arguments for an unmeasured delegation
surface. Class labels describe capability, not a permission check.
