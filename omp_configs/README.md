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
omp --config ./minimax-m3.yml
```

The overlay applies only to that process. It overrides the roles it lists; unlisted roles continue to use the underlying Omp configuration. Later files win when `--config` is repeated.

For a shell wrapper, set `PI_CONFIG_FILES` instead:

```sh
PI_CONFIG_FILES=./cocktail.yml omp
```

## Available overlays

| File | Role configuration |
| --- | --- |
| `glm-5.3-flash.yml` | GLM 5.3 Flash as the default model. |
| `deepseek-v4-pro.yml` | DeepSeek V4 Pro as the default model. |
| `gpt-5.6-sol.yml` | GPT-5.6 Sol as the default model. |
| `gpt-5.6-sol-terra-task.yml` | GPT-5.6 Sol as the default model and GPT-5.6 Terra for task subagents. |
| `cocktail.yml` | GLM 5.3 Flash by default, for task subagents, and for small and tiny work; Qwen 3.8 Max 0902 for planning, deep work, and advice; MiniMax M3 for vision. |
| `cocktail.gpts-choice.yml` | The original GPT-generated cocktail: DeepSeek V4 Pro by default; Luna for small work; Sol for planning and deep work; GLM Flash for task subagents; Terra as advisor; MiniMax M3 for vision; Mercury 2.5 for tiny background work. |
| `mercury-2.5.yml` | Mercury 2.5 as the default model for testing its diffusion-based agent behavior. |
| `kimi-k3.yml` | Kimi K3 as the default model with high reasoning. |
| `minimax-m3.yml` | MiniMax M3 as the default model with high reasoning. |
| `qwen3.8-max-0902.yml` | Qwen 3.8 Max 0902 as the default model with high reasoning. |
| `deepseek-v4.1-flash.yml` | DeepSeek V4.1 Flash as the default model with high reasoning. |
| `mimo-v2.5-pro.yml` | MiMo V2.5 Pro as the default model with high reasoning. |

The `advisor` role in `cocktail.yml` does not enable the advisor. Start Omp with `--advisor` when you want it:

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
