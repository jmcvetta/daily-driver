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
Claude identifier or an Omp agent/model selector. Before dispatch, `embark`
selects the implementation agent named for the required class (`mechanical`,
`implementation`, or `reasoning`) and checks its effective route. For that agent,
`task.agentModelOverrides[agentName]` takes precedence over its discovered
frontmatter model, which can select a tagged role such as `@implementation`. Resolve
configured prewalk and retry fallbacks too; they must meet the same class,
tools, context, modality, availability, and credential requirements. A model
name, catalog entry, effort setting, or price does not prove class suitability
or working credentials. Omp's parent-model authentication fallback needs the
same reassessment and cannot be assumed to satisfy the class. A missing or
unsuitable route stops only that task with a reported configuration gap; do
not lower its required class.

The plugin provides runtime defaults for its three roles only when there is no
effective assignment. A global/project setting or CLI overlay present before
plugin startup wins over those defaults; existing explicit role assignments
also remain authoritative. The OpenAI Codex defaults require Omp's configured
OpenAI Codex credentials. Operators may change a role for subsequent dispatches
through Omp's `/model` Roles UI. Clearing an assignment leaves the tagged role
visible but unassigned, so report a gap instead of restoring a default in the
same session. Existing `omp_configs/` overlays remain supported. A YAML or
overlay edit after startup may stay shadowed until Omp restarts because disk
reload preserves runtime overrides. The plugin writes no Omp configuration
files; disabling it leaves no plugin-written assignments or tags.

Keep the task's provider-neutral required class, the selected agent, and the
actual model reported by Omp as separate facts. Use `unreported` when Omp
provides no execution identity; never treat a selector as an observed model.
Report visible runtime fallback mismatches and reassess before work continues.
