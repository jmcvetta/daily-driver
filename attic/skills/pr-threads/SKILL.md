---
name: pr-threads
description: >-
  This skill should be used whenever pull request review threads are being
  read, answered, resolved, or tidied — including when the user says
  "/pr-threads", "reply to the review comments", "address the review
  feedback", "resolve those threads", or "minimise the old Claude comments",
  and including any use of `mcp__github__add_reply_to_pull_request_comment`,
  `mcp__github__resolve_review_thread`, or `pull_request_read` with the
  `get_review_comments` method on Claude's own initiative. Supplies the reply
  protocol, the resolve rule, the repeat-finding rule, the self-identification
  line, and the comment-minimisation path the GitHub MCP does not offer.
---

# PR Review Threads

The lifecycle of a review thread: read it, act on it, answer it, close it.
Applies to **every** reviewer — a human, Claude Approvals, a lint bot,
whatever comes next. None of what follows is reviewer-specific.

This fires on seeing open review threads, not on being asked about them. A
thread nobody answered is the failure this skill exists to prevent.


The Protocol
============

Four rules. They are the whole protocol.

1. **Implemented** — when the finding is fixed, reply on the thread saying it
   was implemented, and resolve the thread.
2. **Rejected** — when the suggestion is declined, reply on the thread saying
   why, and resolve the thread.
3. **Repeat finding** — when a reviewer opens a new thread for something
   already rejected in an earlier round, resolve it with the same message. The
   reviewer gets the same answer because the answer has not changed; writing a
   fresh variation invites a fresh argument.
4. **Nothing is left open silently.** A thread is answered or it is
   outstanding, and an outstanding thread gets said out loud — never dropped.

**Implemented** and **Rejected** are one rule seen from two sides: **reply,
then resolve.** A resolution with no reply hides the reasoning; a reply with no
resolution leaves the reviewer to guess whether anything happened.


Reply Content
-------------

- **Concise.** Not chatty. No thanks, no apologies, no restating the finding
  back at the reviewer.
- **Technical and accurate.** Say what changed, or what was measured, and
  where.
- **Verdict-first.** The reply must state *implemented* or *rejected*
  unmistakably. A reader skimming twenty threads should never have to parse a
  paragraph to learn which.
- **No poems.** Poetry attaches to the posted review artifact, never to a
  finding someone has to act on. A thread reply is prose.

A rejection carries its reason and stops. "Rejected — `n` is bounded by the
caller's `len(items)` check at `loader.go:88`" is a complete reply. Softening
it into a discussion reopens a thread the rule just closed.


Whose Thread Is It
------------------

Answering and resolving is for threads on **a pull request you opened, or one
you were asked to drive**. On a pull request you are merely watching, a reply
proposing what you would do is the whole action — the author resolves their
own threads.


Clients
=======

Two clients, for a reason that is not arbitrary. The MCP does what the MCP
exposes; a script exists only where it demonstrably does not.

| Task | Client |
| ---- | ------ |
| Read review threads and their IDs | `pull_request_read`, `get_review_comments` |
| Reply on a thread | `mcp__github__add_reply_to_pull_request_comment` |
| Resolve a thread | `mcp__github__resolve_review_thread` |
| Minimise a superseded comment | `scripts/pr-minimize-previous-claude-comments.sh` |

**Reply takes a numeric comment ID, resolve takes a GraphQL thread node ID.**
They are different identifiers for the same conversation and are not
interchangeable. Both are in a `get_review_comments` response, but they are
not both *fields* — measured on a real thread, 2026-09-06:

- **Resolve** wants `PRRT_…`, which is the thread's `id`. Read it directly.
- **Reply** wants a number that appears nowhere as a field. The comment object
  carries no `id`. The number is the `#discussion_r…` suffix of the comment's
  `html_url` — `…/pull/25#discussion_r3943994364` means `commentId: 3943994364`.

So take the thread ID from `id` and the reply ID from the tail of `html_url`.
Do not reach for the thread ID to reply with: it is the identifier that *is*
present, which is exactly why it gets substituted, and the call fails on a
type that looks plausible.


Self-Identification
===================

A review comment Claude posts ends with a self-identification line, in
italics, carrying the model id in brackets:

```
*Claude Opus 5 [claude-opus-5]*
```

The prose name is free — `*Claude 4.1 Opus (claude-opus-4-1-20250805)*` is
equally good, and parentheses work as well as brackets. **The bracketed
`claude-…` id is not.** It is the load-bearing half, and a line that omits it
is not a self-identification line:

| Written | Recognised |
| ------- | ---------- |
| `*Claude Opus 5 [claude-opus-5]*` | yes |
| `*Claude 4.1 Opus (claude-opus-4-1-20250805)*` | yes |
| `*Claude Opus 5*` | **no** — no model id |

**This is not decoration.** Together with the comment's author, it is how the
minimise path recognises Claude's own earlier comments, and the matcher in
`scripts/pr-find-claude-comments.sh` keys on exactly the shape above. Drop the
id and superseded comments stop collapsing — silently, months later, with
nothing to point at.

Self-identification and minimisation move together or not at all. Changing the
line means changing that matcher in the same commit.


Minimisation
============

When a fresh review supersedes an earlier one, the earlier comment is
collapsed rather than left to pad the conversation. **The GitHub MCP has no
tool for this** — `minimizeComment` is a GraphQL mutation and nothing in the
MCP surface reaches it. Verified by absence, not assumed; the retired
planning note `plugin-replaces-global-memory.md` (D3, Git history) recorded
the survey.

That gap is what the scripts in `scripts/` are for, and the only thing they
are for. Each one's header says why it exists and what deletes it.

```
skills/pr-threads/scripts/pr-minimize-previous-claude-comments.sh <pr-number>
```

Scoped to the token's own user by default, because the signature is *text*
and anyone quoting one of Claude's comments carries a matching body. Pass
`--author LOGIN` when the comments were posted under a different identity than
the one running the script.

The dependency chain behind that one line, which must not be cut in the
middle:

> minimisation is a real MCP gap → minimisation needs GraphQL node IDs
> (`IC_kwDO…`) → those come from a script, because no MCP tool returns them.

Retire any link only when its replacement has been demonstrated on a real pull
request. Retiring the supplier while keeping the consumers leaves a chain that
still reads correctly and no longer works.


Surface Limitation
------------------

**Minimisation does not work from a Claude Code web worker**, and the scripts
say so rather than failing obscurely. Measured on 2026-09-06: the session's
ambient `GITHUB_TOKEN` is brokered, and `POST api.github.com/graphql` answers
every operation with HTTP 403 and

> This GraphQL query is not enabled for this session — only the pinned set of
> PR-review operations is served.

The broker answers *before* GitHub does, so a deliberately invalid token gets
that same 403 — which is why the script matches the gate on its text and
reports every other status and message as itself. "No `data` key" identifies
nothing on this surface.

REST is unaffected, so finding the comments works everywhere; only the
mutation is gated. `gh` is not an escape hatch — it is not installed on a web
worker at all, which is why these scripts use `curl`.

So minimisation is a laptop capability, on a personal token. Everything else
in this skill — read, reply, resolve — runs identically on both surfaces
through the MCP.
