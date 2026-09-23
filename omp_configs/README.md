# Omp model role overlays

These YAML files select model roles for one Omp process. Use them to run independent Omp sessions with different model combinations without changing your persistent configuration.

## Usage

From this directory, pass one overlay when starting Omp:

```sh
omp --config ./cocktail.yml
```

Start each configuration in a separate terminal to run several copies at once:

```sh
omp --config ./cocktail.yml
omp --config ./minimax.yml
```

The overlay applies only to that process. It overrides the roles it lists; unlisted roles continue to use the underlying Omp configuration. Later files win when `--config` is repeated.

For a shell wrapper, set `PI_CONFIG_FILES` instead:

```sh
PI_CONFIG_FILES=./cocktail.yml omp
```

## Available overlays

| File | Role configuration |
| --- | --- |
| `glm.yml` | GLM 5.3 Flash for default, small, vision, commit, and tiny work; GLM 5.3 for deep analysis, planning, and advice; GLM 5.3 Fast for task subagents. |
| `gpt.yml` | Sol for default work, deep analysis, and advice; Luna for small, commit, and tiny work; Terra for task subagents and vision; Astra for planning. |
| `cocktail.yml` | GLM 5.3 Flash by default, for task subagents, and for small, vision, and commit work; Kimi K3 for planning and deep work; Qwen 3.8 Max 0902 for advice; Mercury 2.5 for tiny background work. |
| `kimi.yml` | Kimi K3 with high reasoning for default work, planning, and deep work, and low reasoning for task subagents; GLM 5.3 Flash for small, vision, and commit work; Qwen 3.8 Max 0902 for advice; Mercury 2.5 for tiny background work. |
| `cocktail.gpts-choice.yml` | The original GPT-generated cocktail: DeepSeek V4 Pro by default; Luna for small work; Sol for planning and deep work; GLM Flash for task subagents; Terra as advisor; MiniMax M3 for vision; Mercury 2.5 for tiny background work. |
| `cheaper.yml` | DeepSeek V4 Pro for default and deep work; GPT-6 Luna for task subagents; Kimi K3 for planning; GLM Flash for advice; MiniMax M3 for vision; Mercury 2.5 for tiny background work. |
| `minimax.yml` | MiniMax M3 as the default model with high reasoning. |

The `advisor` role in the cocktail overlays does not enable the advisor. Start Omp with `--advisor` when you want it:

```sh
omp --config ./cocktail.yml --advisor
```

## Provider access

Omp must have access to every selected provider. Check that Omp recognizes a selector before use:

```sh
omp models find mercury-2.5
```

Catalog entries do not guarantee that a provider still serves a model. An inference request can fail even when `omp models find` lists it.

The Vercel AI Gateway models require `AI_GATEWAY_API_KEY`. The `openai-codex` models use Omp's configured OpenAI Codex credentials.

## Capability classes

These overlays select concrete model roles. They do not prove that a role or
model satisfies a task capability class. Task issues record `mechanical`,
`standard`, or `advanced` through
[`issue-body`'s shared guidance](../skills/issue-body/references/model-classes.md);
dispatch inspects the effective agent configuration and actual route before
selecting a compatible implementer. Keep concrete selectors in these YAML
files unchanged.
