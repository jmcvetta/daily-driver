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
