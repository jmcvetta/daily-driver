# Omp routes — issue-deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

`scripts/issue-deps.sh` is invoked through the injected skill-directory path,
which Omp names as a `skill://` URL:

```sh
deps="skill://issue-deps/scripts/issue-deps.sh"
```

**Omp rewrites that URL before the shell sees it.** The Bash tool expands every
internal URL in the command string to a shell-escaped absolute path, so the
assignment above reaches `bash` as `deps='/abs/path/to/issue-deps.sh'`. This is
verified from the Omp source rather than assumed: `tools/bash.ts` calls
`expandInternalUrls()` on the command before it runs, and
`tools/bash-skill-urls.ts` does the substitution. The quotes are part of the
token Omp replaces, so the single- and double-quoted forms both work.

**The skill name is the bare directory name, even inside a plugin.** Omp
registers this skill as `issue-deps`, not `daily-driver:issue-deps`: its
Claude-plugin loader deliberately does not prefix skill names, because a colon
is ambiguous in a `skill://` URL.

Two properties of the rewrite decide how this file is used.

**An unresolvable URL is left alone, silently.** Omp does not fail the command
when a `skill://` URL names an unknown skill or a missing file — it leaves the
literal text in place and runs it. The literal `skill://…` then reaches the
shell as an ordinary word. So **check that the path resolves before relying on
it**, with `test -x "$deps"`. Where the test fails, the script is unreachable
and the operation is unavailable — say so. Never fall back to a relative
`scripts/issue-deps.sh`, which is the trap `SKILL.md` describes: in a project
with its own `scripts/` it runs an unrelated file rather than failing.

**The URL must be its own token.** Omp skips a bare `skill://` URL that sits
inside a larger shell quote, so it stays literal in `bash -c "… skill://… …"`
and in any string built around it. Write the assignment above as its own
statement, and use `"$deps"` everywhere after it — in the same Bash command,
since each call is a fresh shell and the variable does not survive between
them.

Client selection
================

Use the first branch that holds:

1. `gh` 2.94.0 or later, with `gh auth status` succeeding.
2. `scripts/issue-deps.sh`, when `GITHUB_TOKEN` or `GH_TOKEN` is present.
3. The available GitHub MCP operations.

Probe the CLI with `gh --version` and `gh auth status`; installed but
unauthenticated is unavailable. The version floor matters because the issue
relationship flags and JSON fields arrived together.

The `gh` client
===============

```sh
gh issue view 191 --json blockedBy,blocking,subIssues,parent,closedByPullRequestsReferences
gh issue edit 191 --add-blocked-by 199
gh issue edit 199 --add-blocking 191
gh issue edit 191 --remove-blocked-by 199
gh issue edit 191 --parent 150
gh issue edit 150 --add-sub-issue 191
gh issue edit 190 --add-blocked-by https://github.com/googleapis/release-please/issues/2853
```

Every relationship flag takes an issue number or URL, never a database ID.
`--remove-parent` takes no argument. Check the command's status before piping
its output. Verify that a read target is an issue before believing an empty
graph. After a write, read the other end with `--json blocking` or
`--json subIssues`.

The fallback script
===================

Resolve `deps` as above, then keep the path and the command in one Bash call:

```sh
test -x "$deps" || { echo "issue-deps.sh unreachable" >&2; exit 1; }
"$deps" blocked-by 191
"$deps" blocking 188
"$deps" summary 191
"$deps" add 191 199
"$deps" remove 191 199
"$deps" add 190 googleapis/release-please#2853
```

It reaches blocked-by and blocking only, and states writes from the blocked
side. Never replace the injected path with a project-relative path.

The MCP client
==============

The newer server reads sub-issues with `issue_read` using `get_sub_issues` or
`get_parent`, writes them with `sub_issue_write` or `issue_write` using
`parent_issue_number`, and returns `closed_by_pull_requests` from `issue_read`.
The older server exposes `get_issue`, `create_issue` and `update_issue`, and
reaches none of those relationships. Neither generation lists the members of
blocked-by or blocking edges or writes them; it returns summary counts only.
