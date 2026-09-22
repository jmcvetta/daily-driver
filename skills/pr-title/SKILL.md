---
name: pr-title
description: >-
  This skill should be used whenever the title of a GitHub pull request is
  being written or revised — including when the user says "fix the PR title",
  "rename the PR", "that title is wrong", or asks what a PR should be called,
  and including any call the agent makes on its own initiative that writes or
  revises a pull request's title while opening or updating one. Supplies the
  Conventional Commits convention the title must
  conform to; the type itself comes from `conventional-commits-type`. Not for
  commit messages, not for the PR body — that is `pr-body` — and not for the
  session's own name — that is `session-title`.
---

# PR Title

The title of a pull request, whether it is being opened or corrected.

    type(scope)!: subject

- **Concise**: _Just enough_ detail. The subject is imperative, lower-case
  after the colon, and carries no trailing period — `fix: retry the S3
  upload on a stale token`.
- **Conventional Commits**: the title MUST conform, and MUST carry the type
  the contents warrant.

**The call that sets the title is per harness, and it lives beside this
file.** [`references/claude.md`](references/claude.md) is the route for
Claude Code, [`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex. Read the one for
the harness in use before the first call.


The type
--------

Follow `conventional-commits-type`. It decides the type from what the change
**does** — the two gates and the one test that settle it are its business,
and they are not guessed at here from the branch name, the issue label, or
the shape of the diff.

It also decides when the type is decided already: a type on the pull request
that this session did not write is settled — whoever set it — and a
disagreement with it is raised rather than retitled.

The type is not decoration. Releases are cut from it: the type in a merged
PR's title becomes the squashed commit subject, and that subject is what
decides the next version. A `feat:` that was really a `fix:` ships a minor
release nobody asked for, and a `fix:` that was really a `feat:` hides one
somebody needed. Where a *Projected Releases* comment exists on the pull
request, read it after the title is set; `conventional-commits-type` says
what to compare it against.


The scope
---------

Optional, and nothing routes on it. Name one when the pull request is
confined to a single nameable component — a skill, `agents`, `ci`, `infra`,
`deps` — as `feat(judgement-call):` and `fix(agents):` do; leave it out when
the change is not so confined. A scope invented to fill the parentheses says
less than none.


Opening a pull request
----------------------

Opening a pull request is the `pr` skill's job. When the title is being written
as part of opening one, follow `pr` as well, for the branch guard, the
existing-PR check and draft state.
