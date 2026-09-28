# Claude Code routes — embark

`SKILL.md` names each operation in words. This file names the call, for a
session running in Claude Code. Omp's routes are in [`omp.md`](omp.md) and
Codex's in [`codex.md`](codex.md); both carry the harness-local subagent
fallback rather than web-session tables, for different reasons each states.


The epic
========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Read the epic` | Read the body | `mcp__github__issue_read`, `method: get` |
| `Read the epic` | Read the task issues under it | `mcp__github__issue_read`, `method: get_sub_issues` |
| `Read the epic` | Read the muster rolls already posted | `mcp__github__issue_read`, `method: get_comments` |
| `Take the wave` | Read a task issue's body and claim | `mcp__github__issue_read`, `method: get` and `get_comments` |
| `Post the muster roll` | Comment on the epic | `mcp__github__add_issue_comment` |
| `Post the muster roll` | Mark the wave in the epic's body | `mcp__github__issue_write`, `method: update` |

`method: update` replaces `body` outright rather than appending to it, so a
wave marked `at sea` or `done` means sending the whole of the epic body back
with that one heading changed.

**The blocked-by edges are `issue-deps`'**, and on this harness the MCP
answers them as counts only — which is a different question from *which*. Read
that skill's routes before `Take the wave`; a count cannot tell you whether the
one blocker is closed.


The sessions
============

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the sessions` | Open one per task | `mcp__Claude_Code_Remote__create_session` |
| `Post the muster roll` | Load the messaging tools, once per session | `ToolSearch`, `select:ListAgents,SendMessage` |
| `Post the muster roll` | Resolve each new session's address | `ListAgents` |
| `Watch the wave` | Read a task session's status | `mcp__Claude_Code_Remote__get_session` |
| `Watch the wave` | Read the implementor reports that arrived | `ReadNotifications`, until it reports none remaining |
| `Watch the wave` | Send a visible answer or a nudge | `SendMessage`, to the roll's name |
| `Recover a session` | Stop the current turn | `mcp__Claude_Code_Remote__interrupt_session` |
| `Recover a session` | Re-resolve a name the roll lacks, or one a send failed to reach | `ListAgents` |
| `Recover a session` | Send a correction | `SendMessage`, to that name |
| `Recover a session` | Retire one | `mcp__Claude_Code_Remote__archive_session` |

What `create_session` is given
------------------------------

| Field | What goes in it |
| ----- | --------------- |
| `prompt` | The task issue and the ask to undertake it. Nothing else. |
| `append_system_prompt` | The way back: this session's own id, below. |
| `title` | `session-title`'s form for that task issue. |
| `model` | A concrete identifier resolved from the required class and current session availability. |
| `environment_id` | Omitted to inherit the calling environment. |
| `permission_mode` | Omitted to inherit. |
| `outcome_branch` | `Recover a session` only. |

**Never `permission_mode: "plan"`.** The call's own contract says a `plan`
session proposes a plan and then blocks for a human approval in the web UI. A
task session is unattended by design, so it would stall there for ever, and
`SKILL.md`'s rule about inheriting the environment's permissions is this
sentence's reason.

**`extra_allowed_tools` cannot widen anything.** Entries the calling session
does not itself have pre-approved are dropped, so a child never carries a grant
its parent lacks. There is nothing to pass here, and passing one would read as
a grant that was not made.

Addressing a session
--------------------

**`ListAgents` and `SendMessage` are deferred tools.** Neither is in the tool
list until `ToolSearch` loads it. Call `ToolSearch` with
`select:ListAgents,SendMessage` once per session, before the first send this
session makes, and both are then callable for the rest of it — a later wave
in the same session makes no second call. A tool list checked before that
call and found to carry neither is not evidence that messaging is
unavailable — it is evidence that this load step has not run yet.

**`SendMessage` is addressed by name, never by a session id.** Its `to` takes
the name a row of `ListAgents` prints — that name is the address, and there is
no other syntax for one. The `session_01AbC…` identifier `create_session`
returns is not one: passing it fails to resolve.

`Post the muster roll` resolves that name once, as each session opens, and
writes it into the roll beside the session id — the `Implementor` cell carries
both. A later wake reads the name straight off the roll; that is the ordinary
route, and it costs no call. Call `ListAgents` again only to re-resolve a name
the roll does not carry — an older roll, or one posted before this step
existed — or after a send to the recorded name fails to reach it, which is
usually the sign that the session under it has already stopped. Match the
fleet member there and send to the name it printed, appending the row's
` [ref]` only where an error asks for it. **A member the listing does not name
cannot be reached at all**, and that is the reopen path in `Recover a session`
rather than a retry.

The required class
------------------

Resolve the task's `Model class` using
[`issue-body`'s shared guidance](../../issue-body/references/model-classes.md)
before calling `create_session`. `session_context.model` is a candidate
concrete identifier only after that assessment; `configured_model` can be an
alias or unsupported suffix. Never pass a class name to `model`, and never
silently inherit an unchecked model.

Reading a session, and what cannot be read
------------------------------------------

`mcp__Claude_Code_Remote__get_session` takes a child's id and reports its
`session_status` and its title. **It does not report what the session said**,
and no call reads it: dispatch is available and reading the result is not.
What the implementor sends on the way back is the one exception, and it is
what the implementor chose to say, not a read of its session. That is
the whole reason `Watch the wave` watches pull requests instead, and it is why
a status is read as a hint rather than as a verdict — `SESSION_STATUS_RUNNING`
covers a session that is working and a session that is stuck.

`mcp__Claude_Code_Remote__list_sessions` with `mine: true` finds the fleet again
where a muster roll is missing. The muster roll is still the record: it is on
the epic, it survives every session in the fleet, and a person can read it.

The way back
------------

**The implementor reports with a one-shot Routine it creates itself, bound to
this session.** This session passes its own id, from
`mcp__Claude_Code_Remote__get_session` with `session_id` omitted, in each
`create_session` call's `append_system_prompt`:

```text
You were opened by an embark orchestrator, session <this session's id>, which
the user started on the same account. That session is your orchestrator for
undertake's `Reporting to an orchestrator`.
```

`undertake`'s `references/claude.md` names the call the implementor makes.
[`0028`](../../../docs/notes/0028-the-report-is-a-scheduled-routine.md) is the
measurement behind this route, and it records why the poke-only Routine this
session could have created, and passed an id for, is not the route.

**The address goes in `append_system_prompt`, not in `prompt`.** One
implementor handed its report route in the prompt stopped and asked its user
whether the prompt was an injection. The two briefed through
`append_system_prompt` reported without asking. Keep `prompt` to the task
issue, as the table above says.

**A report arrives as a queued notification**, read with `ReadNotifications`.
Its origin reads as a scheduled trigger "you or your owner scheduled", because
the Routine is on the same account. That label does not make the report this
session's own instruction. The report opens with `undertake`'s marker line,
and the marker is what identifies it. A report lands one to three minutes after
the implementor sends it, because Routines fire on a one-minute scheduler.


The watch
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Watch the wave` | Subscribe to a task's pull request | `mcp__github__subscribe_pr_activity` |
| `Watch the wave` | Find the pull request for a task issue | `mcp__github__issue_read`, `method: get` — `closed_by_pull_requests` |
| `Watch the wave` | Read a pull request's state and checks | `mcp__github__pull_request_read` |
| `Watch the wave` | Arm the backstop | `mcp__Claude_Code_Remote__send_later`, ten minutes out |
| `Watch the wave` | Archive a finished session | `mcp__Claude_Code_Remote__archive_session` |
| `Land the pull request` | Read draft, merge state, head SHA, labels, and body | `mcp__github__pull_request_read`, method `get` |
| `Land the pull request` | Read review threads | `review-cycle`'s `references/claude.md` thread read |
| `Land the pull request` | Read the review-cycle completion notice | `mcp__github__pull_request_read`, method `get_comments`, every page — `user.login` |
| `Land the pull request` | Read the commits after the notice's SHA | `mcp__github__get_commit`, from `head.sha` back along first parents — `parents` |
| `Land the pull request` | Squash merge the gated head | `mcp__github__merge_pull_request`, `merge_method: squash`, `expectedHeadSha: <head.sha>` |
| `Close the epic` | Comment with the landed pull requests or missing claim | `mcp__github__add_issue_comment` |
| `Close the epic` | Close as completed | `mcp__github__issue_write`, `method: update`, `state: closed`, `state_reason: completed` |
| `Close the epic` | Cancel the backstop | `mcp__Claude_Code_Remote__delete_trigger` |
| `Close the epic` | Drop each subscription | `mcp__github__unsubscribe_pr_activity` |

Landing and close
-----------------

The state read is `undertake`'s `The milestone` row: `draft` must be false,
`mergeable_state` must be `clean`, and `head.sha` is the head the merge binds
to. The same `get` call supplies the labels and body for the human-action read.
The complete thread read is the one `review-cycle`'s `Review history,
publication, and threads` names; a partial review-comments page does not
answer the gate.

The completion read is the conversation-comment read `review-cycle`'s
`Review-cycle completion notice` names, read to the last page: the latest
comment starting with `## Review cycle complete! 🎉` whose author is the
author of the task issue's claim comment, and the SHA it names. Where that SHA is not
`head.sha`, walk `get_commit` from `head.sha` along each first parent until the
named SHA; every commit on the way must carry two `parents`. A single-parent
commit, or a walk that never reaches the SHA, fails the read.

The merge call is made only after those reads hold. `expectedHeadSha` makes it
fail closed if the task session pushes after the read. `merge_method: squash`
preserves the repository's pull-request-title subject. `Close the epic` uses
the issue update only after its comment records the pull requests that
delivered every `Summary` claim.

**`closed_by_pull_requests` is the link from a task to its pull request**, and
it is populated by the `Closes #123` line `pr-body` writes. A task issue with
no pull request against it is a session that has not reached `undertake`'s
`Open the draft` yet — or one that died before it did, which is what
`Recover a session` is for.

**There is a `mcp__Claude_Code_Remote__subscribe_pr_activity` with the same
contract.** Where both exist, use the GitHub one, and use one namespace
throughout. Read the tool result either way: where a PR Steward already watches
that pull request, the call succeeds and the events go to the steward instead,
and the backstop is then the whole watch for it.

The backstop, and the one slot
------------------------------

`mcp__Claude_Code_Remote__send_later` survives the session that armed it, which
is what makes a watch across turns possible at all. Keep the `trigger_id` it
returns: that is this session's one wake slot, and
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md) is the rule
it is held under. The test is whether the slot is empty rather than what woke
the turn.

Ten minutes rather than `undertake`'s two, and `SKILL.md` says why. A shorter
interval does not make a task session faster: each one already holds a
two-minute cadence of its own, and this timer is only what brings this session
back when no event does.
