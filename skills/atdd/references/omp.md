# Omp routes — atdd

Resolve the bundled program through Omp's injected skill directory:

```sh
bootstrap="skill://atdd/scripts/bootstrap-typescript.mjs"
test -f "$bootstrap" || { echo "ATDD bootstrap unreachable" >&2; exit 1; }
node "$bootstrap" "/absolute/path/to/target-repository"
```

For offline or preinstalled dependencies, use
`node "$bootstrap" --no-install "/absolute/path/to/target-repository"`.
Keep the assignment and invocation in the same Bash tool call.

Omp expands `skill://` to a shell-escaped absolute path before execution. The
URL must be its own token, not embedded inside a larger shell string. The bare
skill name is `atdd`, not a plugin-prefixed name. An unresolved URL remains
literal, so always check that the program exists. Never fall back to a script
relative to the target repository: that could execute unrelated project code.

The expansion is a Bash tool feature, not a shell feature. When giving an
operator a command to run in their own terminal, use the absolute directory
reported by the `skill://atdd` read: replace its trailing `SKILL.md` with
`scripts/bootstrap-typescript.mjs`, quote the resulting path, and show
`node "/actual/resolved/path/scripts/bootstrap-typescript.mjs" "/absolute/path/to/target-repository"`.
Never give a literal `skill://` URI as a shell command outside the Omp tool.
