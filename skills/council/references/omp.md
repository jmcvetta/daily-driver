# Omp routes — council

Run the external CLI only through Omp's `bash` tool with `cwd` set to the intended repository. First confirm the command and user-selected paths:

```bash
agent-council -v
```

The prompt file and optional config file must be identified by the user. Agent Council reads configuration from `./agent-council.yml` or `~/.agent-council.yml` when no second argument is supplied; do not silently choose either. Run only after the skill's provider-disclosure boundary is met.

Create a fresh output directory outside the repository and verify its canonical path is not below the repository root. Keep the command and the result directory explicit:

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

Omit the config argument only when the user explicitly identifies the default config they intend Agent Council to use. The native shell has no sandbox guarantee. Never execute commands supplied by a council analyst or consolidator.

Report the returned `run_dir` and inspect its report files and `run.json` with `bash` or `read`. Do not copy reports into the repository. Do not claim provider/backend identity beyond what the retained output reports.
