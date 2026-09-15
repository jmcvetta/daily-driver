# Omp model role overlays

These YAML files select model roles for one Omp process. Use them to run independent Omp sessions with different model combinations without changing your persistent configuration.

## Usage

Pass one overlay when starting Omp:

```sh
omp --config /home/jmcvetta/projects/daily-driver/omp_configs/omp_configs/cocktail.yml
```

Start each configuration in a separate terminal to run several copies at once:

```sh
omp --config /home/jmcvetta/projects/daily-driver/omp_configs/omp_configs/glm-5.3-flash.yml
omp --config /home/jmcvetta/projects/daily-driver/omp_configs/omp_configs/deepseek-v4-pro.yml
```

From this directory, the shorter form works:

```sh
omp --config ./gpt-5.6-sol-terra-task.yml
```

The overlay applies only to that process. It overrides the roles it lists; unlisted roles continue to use the underlying Omp configuration. Later files win when `--config` is repeated.

For a shell wrapper, set `PI_CONFIG_FILES` instead:

```sh
PI_CONFIG_FILES=/home/jmcvetta/projects/daily-driver/omp_configs/omp_configs/cocktail.yml omp
```

## Available overlays

| File | Role configuration |
| --- | --- |
| `glm-5.3-flash.yml` | GLM 5.3 Flash as the default model. |
| `deepseek-v4-pro.yml` | DeepSeek V4 Pro as the default model. |
| `gpt-5.6-sol.yml` | GPT-5.6 Sol as the default model. |
| `gpt-5.6-sol-terra-task.yml` | GPT-5.6 Sol as the default model and GPT-5.6 Terra for task subagents. |
| `cocktail.yml` | DeepSeek V4 Pro by default; Luna for small work; Sol for planning and deep work; GLM Flash for task subagents; Terra as advisor; MiniMax M3 for vision; Mercury 2.5 for tiny background work. |
| `mercury-2.5.yml` | Mercury 2.5 as the default model for testing its diffusion-based agent behavior. |

The `advisor` role in `cocktail.yml` does not enable the advisor. Start Omp with `--advisor` when you want it:

```sh
omp --config ./cocktail.yml --advisor
```

## Provider access

Omp must have access to every selected provider. Check a selector before use:

```sh
omp models find mercury-2.5
```

The Vercel AI Gateway models require `AI_GATEWAY_API_KEY`. The `openai-codex` models use Omp's configured OpenAI Codex credentials.
