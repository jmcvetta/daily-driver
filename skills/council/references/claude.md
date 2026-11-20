# Claude Code routes — council

Use Claude Code's native `Bash` tool in the intended repository. The tool is not a sandbox for Agent Council's child processes. Check the external prerequisite without installing it:

```bash
command -v agent-council
agent-council -v
```

Run only with the prompt path and optional config path the user identified, and only after stating that project material and command output can reach every configured provider. The command calls providers at their normal rates. Do not use `claude`, another model tool, or a second agent to substitute for the configured CLI ensemble.

Create a fresh report directory under the system temporary directory, canonicalize it, and reject any path inside the repository before calling the CLI:

```bash
set -eu
repo=$(git rev-parse --show-toplevel)
cd "$repo"
repo=$(pwd -P)
run_dir=$(mktemp -d "${TMPDIR:-/tmp}/agent-council.XXXXXX")
run_dir=$(cd "$run_dir" && pwd -P)
case "$run_dir/" in
  "$repo/"*)
    rmdir "$run_dir"
    printf 'Output directory is inside the repository: %s\n' "$run_dir" >&2
    exit 1
    ;;
esac
agent-council --output-dir "$run_dir" /absolute/path/to/user-prompt.md /absolute/path/to/user-config.yml
```

Omit the config argument only when the user explicitly identifies the intended default config. Inspect and report the actual report paths, `run.json`, failures, and available usage/duration. Do not execute analyst-provided commands or copy output into the repository.
