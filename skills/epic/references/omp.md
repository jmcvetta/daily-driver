# Omp routes — epic

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

Two clients share the work. The built-in `github` tool reads and writes what it
covers; `gh` covers the rest, and every read is also available as an `issue://`
internal URL, which resolves from the same cache the `github` tool writes to.


The issues
==========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Size the work` | Read an issue already in hand | `issue://<number>` |
| `Open the issues` | Search the open issues | `github.search_issues`, or `gh search issues` |
| `Open the issues` | Open the epic, and each task | `gh issue create --label epic` / `--label task` |
| `Open the issues` | Turn an existing issue into the epic | `daily_driver_gh_write({ args: ["issue", "edit", <number>, "--body-file", <path>, "--add-label", "epic", "--remove-label", <old label>] })` |
| `Fill in the epic` | Replace the epic's body | `daily_driver_gh_write({ args: ["issue", "edit", <number>, "--body-file", <path>] })` |

Bodyless issue creation remains on `gh issue create`. If creation includes a
body, route the same argument array through `daily_driver_gh_write`; the wrapper
attaches provenance without changing the supplied title or labels.

The wrapper adds and deduplicates provenance to each body-bearing write; do not
include a new block in the supplied body.


The parent, at creation
=======================

**`gh issue create` does not take a parent**, so the parent is a second write
here and `Write the graph` does it — through `issue-deps`, which reaches
sub-issues on this harness when `gh` is at its stated floor.


The graph
=========

`issue-deps` owns both relationships and picks its own client. Read that
skill's routes before `Write the graph`.

Apply `issue-deps`' pre-link assignability gate before every parent or
sub-issue write to the epic, including when linking an existing issue.


The required class
==================

`issue-body` owns the task body contract and shared routing guidance in
[`model-classes.md`](../../issue-body/references/model-classes.md). Every story
uses that task contract and required model class at `Open the issues`, whether
new or reused. This skill neither duplicates the taxonomy nor records a
concrete model.
