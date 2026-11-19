# Omp routes — issue

`SKILL.md` names each move in words. This file names the call, for a session
running in Oh My Pi. Claude Code's routes are in [`claude.md`](claude.md),
Codex's in [`codex.md`](codex.md).

Two clients share the work. The built-in `github` tool reads and writes what
it covers; `gh` covers the rest, and every read is also available as an
`issue://` internal URL, which resolves from the same cache the `github` tool
writes to.

| Move | Operation | Call |
| ---- | --------- | ---- |
| Read what is there | Read the issue | `issue://<number>` |
| Read what is there | Search the open issues | `github.search_issues`, or `gh search issues` |
| The label | Set or swap a label | `gh issue edit <number> --add-label <label> --remove-label <the old one>` |
| The body | Open with a body; settle destination under [the target repository rule](../SKILL.md#the-target-repository) and pass it here | `daily_driver_gh_write({ args: ["issue", "create", "--label", <label>, "--body-file", <path>] })`, adding `"--repo", "OWNER/REPO"` when the target differs from the current repository |
| The body | Replace a body | `daily_driver_gh_write({ args: ["issue", "edit", <number>, "--body-file", <path>] })` |
| The edges | Blocked-by, parent, sub-issue | `issue-deps`'s own routes |
| The state | Close or reopen | `gh issue close <number>` / `gh issue reopen <number>` |

The body goes through `daily_driver_gh_write` as a structured argument array.
The wrapper reads the supplied body file and publishes a private attributed
copy; do not add a provenance block to the caller's content.

**A label swap on this harness adds and removes in one call**, so the stock
and bot-owned labels `issue-labels` says to leave alone are never in
danger — the opposite of the Claude route, where the write replaces and the
read has to come first.
