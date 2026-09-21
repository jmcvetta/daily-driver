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


The required class
==================

Task bodies use the provider-neutral `Model class` section defined in
[`model-classes.md`](model-classes.md). An Omp task issue does not carry a
Claude identifier. `embark` resolves a class against the effective
implementation-agent configuration and records the actual model the harness
reports. Existing Omp roles and YAML selectors stay concrete execution
configuration, not issue metadata.
