# Model classes

Task issues name the minimum capability needed to implement their settled
handoff. They do not name a provider, a price tier, a context window, or a
reasoning-effort setting.

## Classes

| Class | Suitable work | Boundary |
| --- | --- | --- |
| `mechanical` | A bounded transformation with an explicit rule, identified scope, existing example, and direct check. | No substantive implementation choice or diagnosis remains. |
| `standard` | Settled design using repository patterns, routine local choices, ordinary multi-file coordination, meaningful tests, and local failure diagnosis. | The normal class for a specified feature or bug fix. |
| `advanced` | A settled design with sustained reasoning about interacting invariants or difficult failure modes. | State the irreducible reason, such as concurrency correctness, security boundaries, or data integrity. File count, a security filename, and missing specification are not reasons. |

Improve the task specification before raising its class. A stronger model does
not make an underspecified task ready.

## Routing policy

This dated policy is provisional guidance, not a certification or a claim of
cross-provider equivalence. Bind a choice to the concrete model, version, and
execution settings. Catalog presence is not availability, and a family member
does not inherit another member's class.

| Model | Starting class | Basis and limit |
| --- | --- | --- |
| Claude Haiku 4.5 | `mechanical` | Anthropic's low-cost subagent positioning; no repository-wide reliability claim. |
| Claude Sonnet 5 | `standard` | Anthropic's everyday coding and agent positioning. |
| GPT-5.6 Terra | `standard` | Published intelligence/cost positioning and the existing task-role configuration; not parity with Sonnet. |
| GLM-5.3 | `standard` | Published coding, tool-use, and agent capabilities; conservative starting point. |
| DeepSeek V4 Pro | `standard` | Published agentic coding and tool-use capabilities; conservative starting point. |
| Claude Opus 5 | `advanced` | Anthropic's complex agentic-coding positioning. |
| GPT-5.6 Sol | `advanced` | OpenAI's complex professional-work positioning and existing stronger roles. |

At dispatch, filter candidates for the required class, tools, context,
modalities, and current availability. Prefer the lowest expected reliable cost,
including known rework and quota costs. Unknown or incomparable prices use the
operator's configured eligible preference; do not call missing or zero catalog
cost free. A stronger eligible model may run lower-class work. If no eligible
route exists, stop only that task and report the configuration gap.

Record the requested class separately from the selected route and actual model.
Use `unreported` when the harness does not report actual execution identity;
report visible runtime fallback mismatches and reassess before continuing.

## Evidence

These assignments were recorded on 2026-09-21 from published positioning and
local configuration. Existing behavioural evals test this plugin's contracts;
they do not establish universal model capability classes. Primary sources:
[Anthropic model selection](https://platform.claude.com/docs/en/about-claude/models/choosing-a-model),
[Claude models](https://platform.claude.com/docs/en/models/overview),
[GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra),
[GPT-5.6 Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[GLM-5.3](https://docs.z.ai/guides/llm/glm-5.3), and
[DeepSeek V4](https://api-docs.deepseek.com/news/news260424).
