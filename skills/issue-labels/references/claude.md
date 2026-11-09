# Claude Code routes — issue-labels

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md),
Codex's in [`codex.md`](codex.md).


Reading and writing a label
===========================

| Operation | Call |
| --------- | ---- |
| Read the labels on one issue | `mcp__github__issue_read`, method `get`, which returns `labels` |
| Read the labels as their own list | `mcp__github__issue_read`, method `get_labels` |
| Label an issue being opened | `mcp__github__issue_write`, method `create`, with `labels` |
| Label an issue that exists | `mcp__github__issue_write`, method `update`, with `labels` |

**`labels` replaces the whole set; it does not add to it.** An update that
sends one label drops every other label the issue had, the bot-owned ones
included. Read the current set first and send it back with the change applied.

Reconciling the story marker
============================

`issue-deps` supplies a verified direct-parent read. If that parent's labels
include `epic`, include `story` in the replacement `labels` set. If no parent
is confirmed or its labels omit `epic`, remove `story` from that set. A failed
graph read preserves the current set and reports the limitation. The
replacement write includes the existing issue kind, stock labels, bot labels,
and unrelated labels; `story` is never a substitute for a kind.

Finding the issues that carry a label is `mcp__github__list_issues` with
`labels`, or `mcp__github__search_issues` with `label:task` in the query —
the search is what answers "which of these could I hand to an agent".
