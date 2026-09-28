---
name: provenance
description: >-
  This skill should be used before any GitHub write an agent makes — a pull
  request, issue or epic body; a comment; a review or review reply — and
  before any commit, so the artifact and the commit both name the model,
  harness and session that produced them. Supplies the trailing provenance
  block's shape and placement, the rule for reading the model that served the
  turn against the one the session was set to, the harness name and version,
  the session identifier or `n/a`, the rule that a body edited later gains a
  second block rather than losing the first, and the commit trailer each
  harness adds. Not for the claim comment's branch line or haiku, which are
  `undertake`'s, and not for a task issue's `Model class` section, which is
  implementation metadata `issue-body` owns.
---

# Provenance

One shape for the record every write leaves: which model wrote it, on which
harness and version, in which session. `undertake`'s claim comment and
first-readiness report already carried a version of this; every other
writing skill carried nothing, or only a harness's own generic footer. This
skill is the one owner of that record, cited rather than restated wherever a
body, a comment, a review reply, or a commit is written.

**The routes are per harness, and they live beside this file.** Every
operation below is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before the first write this skill governs.


The block
=========

Placed at the end of the body or comment, after a `---` rule of its own, and
above any footer the harness appends to the same write:

```
---
Model: <model id that served the turn>
Harness: <name> <version>
session: <session link or id, or n/a>
```

**`Model:`, one line.** The model that served the turn — never a name
recalled instead of read. Where the model the session was *set* to run
disagrees with the one that actually served, name both: the gap between the
two is the half of the record worth having. Read it from the harness's own
session call where it has one, and from the harness's own statement of the
serving model where it does not.

**`Harness:`, one line.** The harness's name and the version a surface in the
session can actually read, by whatever call the reference file for the
harness in use names. A version no surface reports is `n/a`, never a guessed
one.

**`session:`, lowercase, one line.** The session identifier — linked where
the harness offers a link, bare where it offers only an id, and `n/a` where
it offers neither. A missing session is recorded as `n/a`, never narrated: a
block that explains why it has no session id publishes a diagnostic instead
of a record.

**The line shapes are fixed, because other skills key their reads off them.**
`undertake`'s claim lookup and first-readiness timing find the claim comment
by its `Model:` and `session:` lines. Changing either shape breaks that
lookup silently, on every issue it has ever run against.


Bodies edited later
====================

**An existing block is never removed, and never rewritten in place.** A
session that edits a body, or replies in a thread, it did not start adds its
own block beneath whatever is already there, so the record reads as a
sequence of writers rather than a single overwritten claim.

**A repeat write by the same session, in the same turn, changes nothing.**
One block per write, not one per line touched — a body revised twice in one
turn carries the block once, at the end of the final version. Where the same
session returns in a later turn to revise its own earlier write, that is a
new write and earns its own block under the rule above: the earlier one
stays, and the body now carries two.

`undertake`'s claim comment and first-readiness report keep their own timing
and once-per-undertaking rules for the block they carry; this section governs
every other body and comment.


Commits
=======

Every commit an agent makes keeps GitHub's `Co-Authored-By: <name> <address>`
trailer for the model, and adds a session trailer beside it. **Where the
harness already appends both on its own, the agent adds nothing and never
duplicates them** — one of the three does, by name in its own reference file.
The per-harness reference names the trailer and the address to use where the
harness does not append one itself, grounded in what that harness documents.
Where a harness documents no address, the reference says so rather than
inventing a domain, and the commit carries the session trailer alone.


Non-goals
=========

- **Does not decide when a write happens.** Every other skill still decides
  what to write and when; this skill only says what the write carries once
  it happens.
- **Does not gate anything on the block's presence.** No readiness test,
  review finding, or merge gate gains a new condition from this skill — a
  write made before this skill existed carries no block, and that is
  history, not a defect to fix retroactively.
- **Does not touch a task issue's `Model class` section.** That section is
  implementation metadata about the required capability, not concrete-model
  provenance, and `issue-body` owns its shape and its own trailing-field
  rule.
- **Does not carry the claim comment's branch line or its haiku.** Those stay
  `undertake`'s, placed around the block rather than inside it.
