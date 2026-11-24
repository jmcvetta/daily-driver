# Codex routes — atdd

Resolve the skill directory from the session's `<skills_instructions>` roots
table. Find the `atdd` skill entry (possibly plugin-prefixed), expand its
`r<n>` root, and use the script beside its `SKILL.md`:

```sh
bootstrap="<the expanded root>/atdd/scripts/bootstrap-typescript.mjs"
test -f "$bootstrap" || { echo "ATDD bootstrap unreachable" >&2; exit 1; }
node "$bootstrap" "/absolute/path/to/target-repository"
```

For offline or preinstalled dependencies, use
`node "$bootstrap" --no-install "/absolute/path/to/target-repository"`.
Keep the assignment and invocation in the same shell call. `skill://` is not
expanded by Codex, and a plugin hook's `CLAUDE_PLUGIN_ROOT` is not evidence that
a skill shell receives that variable. Use the roots table, not either harness's
path convention. Never fall back to a target-relative script when resolution
fails; report the unavailable bundled program.
