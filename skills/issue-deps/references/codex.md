# Codex routes — issue-deps

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).


Two clients, not three
======================

**Codex has no GitHub MCP server**, so the third branch of `SKILL.md`'s probe
does not exist here. `gh` at 2.94.0 or later is the first client and
`scripts/issue-deps.sh` is the last one. Where neither holds, the operation is
unavailable — say so, rather than reporting the counts the MCP would have
given, because there is no MCP here to give them.

That makes the probe shorter but not weaker. The branch this harness loses is
the one that reads counts and writes nothing, which was never an answer to
*which* issue blocks this one.


Reaching the script
===================

**The path comes from the skills roots table.** Codex puts a
`<skills_instructions>` block in front of every session: a roots table naming
each skills directory as `r0`, `r1` and so on, then one line per skill giving
its file against a root — `daily-driver:issue-deps` is
`(file: r<n>/issue-deps/SKILL.md)`. Expand that root and the script sits
beside it:

```sh
deps="<the expanded root>/issue-deps/scripts/issue-deps.sh"
test -x "$deps" || { echo "issue-deps.sh unreachable" >&2; exit 1; }
```

**Neither of the other two harnesses' paths works here.** `skill://` is not
expanded in the Codex CLI — it reaches the shell as literal text, the way an
unresolvable URL does on Omp, so a command built around it runs against a
filename that does not exist. And `CLAUDE_PLUGIN_ROOT` is exported to a plugin
*hook*'s environment, which is not a skill's shell; whether a tool call sees it
is unmeasured, so probe it rather than build a path from it.

**Test before relying on it, and never fall back to a relative
`scripts/issue-deps.sh`.** That is the trap `SKILL.md` describes: in a project
with its own `scripts/` directory the relative path runs an unrelated file
rather than failing. An unreachable script is a client this harness does not
have, and the honest report is that the edge could not be written.

Auth comes from `GITHUB_TOKEN` or `GH_TOKEN`, as it does everywhere else.

Client selection
================

Use the first branch that holds:

1. `gh` 2.94.0 or later, with `gh auth status` succeeding.
2. `scripts/issue-deps.sh`, when `GITHUB_TOKEN` or `GH_TOKEN` is present.

Probe the CLI with `gh --version` and `gh auth status`; installed but
unauthenticated is unavailable. There is no GitHub MCP fallback on this
harness.

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

After every parent read or write, read the confirmed parent's labels and invoke
`issue-labels` to reconcile `story` on the child. A failed or unavailable
graph read preserves the child labels and reports the limitation. A successful
read with no parent is confirmation to remove the marker.

The fallback script
===================

Resolve `deps` as above, then:

```sh
"$deps" blocked-by 191
"$deps" blocking 188
"$deps" summary 191
"$deps" add 191 199
"$deps" remove 191 199
"$deps" add 190 googleapis/release-please#2853
```

It reaches blocked-by and blocking only, and states writes from the blocked
side. Never replace the resolved path with a project-relative path.
