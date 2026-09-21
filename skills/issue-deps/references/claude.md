# Claude Code routes — issue-deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).

`scripts/issue-deps.sh` is invoked through `${CLAUDE_PLUGIN_ROOT}`, the
plugin root the harness injects into a skill's Bash:

```sh
deps="${CLAUDE_PLUGIN_ROOT}/skills/issue-deps/scripts/issue-deps.sh"
```

Client selection
================

Use the first branch that holds:

1. `gh` 2.94.0 or later, with `gh auth status` succeeding.
2. `scripts/issue-deps.sh`, when `GITHUB_TOKEN` or `GH_TOKEN` is present.
3. The available GitHub MCP operations.

Probe the CLI with `gh --version` and `gh auth status`; installed but
unauthenticated is unavailable. The version floor matters because the issue
relationship flags and JSON fields arrived together. An older client reports
unknown flags or fields rather than naming its missing capability.

The `gh` client
===============

The CLI reads and writes the whole graph in both directions:

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
`--remove-parent` is the exception: it takes no argument. Check the command's
status before piping its output. A read against a pull request can return the
same empty graph as an issue with no relationships, so verify the target kind.
After a write, read the other end with `--json blocking` or
`--json subIssues`.

After every parent read or write, read the confirmed parent's labels and invoke
`issue-labels` to reconcile `epic-child` on the child. A failed or unavailable
graph read preserves the child labels and reports the limitation. A successful
read with no parent is confirmation to remove the marker.

The fallback script
===================

Invoke the script through `${CLAUDE_PLUGIN_ROOT}`:

```sh
deps="${CLAUDE_PLUGIN_ROOT}/skills/issue-deps/scripts/issue-deps.sh"
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
