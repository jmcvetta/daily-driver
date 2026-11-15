# Codex routes — council

Use Codex's native shell tool from the intended repository. Agent Council starts Pi child agents; the host shell and Codex sandbox do not establish a sandbox for those child processes. Check that the external CLI is installed without installing it:

```sh
command -v agent-council
agent-council -v
```

Run only with the prompt path and optional config path the user identified, after stating that repository material and command output can reach every configured provider. The command calls providers at their normal rates. Do not use Codex agents or another model tool to replace the configured ensemble.

Create a fresh directory outside the repository, canonicalize it, and refuse to run if it resolves inside the repository:

```sh
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
