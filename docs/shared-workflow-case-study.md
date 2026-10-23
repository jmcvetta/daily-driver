# One workflow across three coding tools

Daily Driver's shared workflow grew from one environment to three: Claude Code, Omp and Codex. The engineering problem was to keep the same task and review practices while each tool exposes different runtime capabilities.

## Design

The project keeps one set of skill instructions and a shared constitution. Each skill puts tool calls in a harness-specific reference file. Runtime integration stays in adapters: Claude Code and Codex use hooks, while Omp uses an extension. This lets a workflow keep one policy without pretending that every environment offers the same tools or lifecycle.

The earlier [architecture decision](notes/0011-two-harnesses-one-skill-tree.md) records the shared skill tree and the Omp adapter. The later [Codex decision](notes/0016-three-harnesses-one-skill-tree.md) extends that design and documents the Codex-specific boundaries.

## Delivered change

[Issue #180](https://github.com/jmcvetta/daily-driver/issues/180) coordinated the Codex integration. [Merged PR #189](https://github.com/jmcvetta/daily-driver/pull/189) added Codex references to nine skills and updated manifest validation so harness routes stay in their reference files. The change extended one shared workflow rather than creating a separate Codex skill tree.

## Evidence and limits

The issue and pull request show the delivered change. The [Codex decision note](notes/0016-three-harnesses-one-skill-tree.md) records that some behavior was observed through the Codex binary and stub Responses API. It also says the delegation path was not observed and that no live-account end-to-end workflow was run. These records support the design and code changes; they do not prove equivalent behavior across live accounts or providers.

Coding-tool portability is not provider-independent model selection. The harness references and runtime may impose different requirements, and the evaluation records measure only their named runs. See the [current skill references](../skills/) and [evaluation results](../evals/RESULTS.md) for those separate details.
