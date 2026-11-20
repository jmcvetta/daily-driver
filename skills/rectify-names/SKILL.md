---
name: rectify-names
description: >-
  Use when asked to systematically examine naming across a repository or a
  defined part of one, assess candidate improvements, or coordinate approved
  naming corrections. Do not start a repository-wide audit because an
  unrelated task exposes one poor name. Supplies an evidence-led audit,
  separate judgment and issue-backed incremental correction workflow; it does
  not authorize edits, compatibility changes, deployment, or production access.
---

# Rectify names

A name is a claim about the thing it names. This skill examines the thing and
its consumers before assessing that claim. A candidate is not a correction:
no code changes happen during examination, recording, judging or planning.

**The routes are per harness, and they live beside this file.** Use the active
harness routes supplied by the skills this workflow invokes. Do not add a
second route for an operation they already provide.

## Examine

Read the repository's domain vocabulary and inspect behavior within the
operator's requested scope. Follow relevant packages, directories, files,
exported interfaces, configuration, workflows, commands, tests and user-facing
copy. Trace consumers and use language-server references when available. A
text search can locate occurrences; it cannot establish what a name means or
prove that all consumers were examined.

Record the examined areas, the methods used and meaningful coverage gaps. Keep
examination read-only: discovering an awkward name does not authorize a
renaming or an audit beyond the requested scope. Separate observed behavior
from assumptions and unresolved questions.

**Output:** a scoped coverage note with the domain terms, surfaces examined,
consumer tracing performed and gaps. If the requested scope is unclear, use
`judgement-call` before expanding it.

## Record candidates

Create a durable, reviewable candidate list in the agreed planning record. Give
each candidate a stable identifier that remains unchanged through judgment,
issue creation and resumption. Each entry contains:

- Current name, proposed name, and concrete source references.
- The named thing's observed meaning and why the current name mismatches it.
- A prose explanation of the proposed name's semantic benefit. A longer or
different name is not inherently clearer.
- Affected consumers and the complete coherent correction surface.
- Compatibility and migration implications, release risks, uncertainty, and
  verification needed.

Distinguish semantic errors from taste. One candidate represents one coherent
correction and all references required to complete it; do not split one rename
into an issue per occurrence. Mark unknown impact as unknown rather than
assuming there are no consumers.

**Output:** candidate entries with stable IDs and evidence, plus the coverage
note. No source edits or issue dispatch.

## Judge separately

Run a separate judging pass over the recorded evidence. For each candidate,
select, reject or defer it and state why. Weigh semantic accuracy and clarity
benefit against churn, ambiguity and migration risk. The judge may recommend
keeping the current name or select nothing. Separate judgment from operator
scope agreement; judgment itself is not permission to edit or dispatch. Do not
require a paid service or hard-code a frontier model.

**Output:** a decision and rationale for every candidate, including rejected
and deferred entries. Preserve stable IDs and the original evidence.

## Plan and agree

Present the selected candidates and each complete correction scope for
agreement through `epic`. Keep candidate decisions and the mapping to issues in
the durable planning record so another session can resume without reconstructing
the audit. A zero-candidate result is a supported no-change outcome.

After agreement, search for existing issues before creating one per selected
candidate. Use `issue`, `issue-body`, `issue-labels` and `issue-deps` for issue
content, kind, and verified graph relationships. Include the candidate ID,
evidence, old and proposed names, affected consumers, compatibility decision,
verification, and required model class in each handoff. Record only actual code
dependencies; shared files alone do not establish a blocker.

Honor `epic`'s planning and decomposition gates:

- One reviewable correction is one task; do not create an artificial epic.
- Multiple independently useful corrections use an epic when coordination is
  needed. Link qualifying children with verified parent edges.
- Do not create issues or begin implementation before agreement on the selected
  scopes. Preserve the agreement and issue mapping for resume.

**Output:** the agreed selection and scope, or the supported no-change result;
then the searched/reused or newly created issue mapping and qualifying graph
edges. If a compatibility decision remains unresolved, keep only the affected
handoff unready and continue unrelated safe preparation.

## Rectify incrementally

Hand each approved correction to `undertake`. Use `embark` only when the
operator requests coordinated execution. Complete the full agreed correction
surface and preserve behavior outside its naming contract. Each correction
must pass its required verification before it is treated as complete. Do not
edit code or dispatch work merely because examination, judgment or planning
finished.

Compatibility is specific to each candidate. Identify internal and externally
observable names, consumers, supported links, package and release effects,
automation, persisted state and migration authority. Pagoda #318 is a practical
example of these distinct boundaries, not an instruction to change Pagoda or a
universal compatibility policy. Do not silently drop supported consumers,
introduce unapproved aliases, or hand-edit package manifests or lockfiles;
follow the package manager. A naming audit grants no deployment, production or
state-migration authority. If required authority is unavailable, leave that
correction unready and report the exact boundary; do not probe production.

**Output:** one issue-backed correction at a time, with its completed checks
and remaining compatibility boundaries. The audit and planning phases alone
never count as implementation.
