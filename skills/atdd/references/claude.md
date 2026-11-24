# Claude Code routes — atdd

Resolve the bundled program through the plugin root supplied by the harness:

```sh
bootstrap="${CLAUDE_PLUGIN_ROOT}/skills/atdd/scripts/bootstrap-typescript.mjs"
test -f "$bootstrap" || { echo "ATDD bootstrap unreachable" >&2; exit 1; }
node "$bootstrap" "/absolute/path/to/target-repository"
```

For offline or preinstalled dependencies, use
`node "$bootstrap" --no-install "/absolute/path/to/target-repository"`.
Keep the assignment and invocation in the same Bash tool call. Never substitute
a script relative to the target repository if the bundled program is missing;
report the unavailable resource instead.
