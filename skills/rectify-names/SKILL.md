---
name: rectify-names
description: >-
  Use when asked to examine naming systematically across a repository or a
  defined part of one, assess candidate improvements, or coordinate approved
  naming corrections. Not for a repository-wide audit because an unrelated
  task exposed one poor name. Supplies evidence-led correction scaled to risk:
  a bounded internal rename takes the ordinary issue-to-PR path, while a
  broad, public, stateful or cross-session audit keeps durable candidates,
  separate judgment and coordinated mapping. It authorizes no edits,
  compatibility changes, deployment, or production access.
---

# Rectify names

## Names and things

This skill takes its frame from the Chinese philosophy of **Rectification of
Names** (*zhengming*, 正名). In the *Analects*, Confucius connects correct names
with truthful speech and effective action:

> "If names be not correct, language is not in accordance with the truth of
> things. If language be not in accordance with the truth of things, affairs
> cannot be carried on to success."
>
> — *Analects* 13.3, wording preserved from
> [Pagoda #318](https://github.com/Green-Pagoda/pagoda/issues/318).

The original concern includes social roles and conduct. Here the engineering
application is narrower: a name makes a claim about a domain concept, a
responsibility or a behavior. When that claim and the implementation diverge,
readers reason from the wrong model. Rectification corrects that mismatch,
not merely the spelling or style of an identifier.

The **White Horse Dialogue**, attributed to Gongsun Long and associated with
the School of Names, offers a related but distinct lens. Its claim, "a white
horse is not a horse," has disputed interpretations; one useful reading
distinguishes the scope of "white horse" from that of "horse." The terms are
not interchangeable, even though a white horse is a horse. This is not a
teaching from the *Analects* or a reason to deny ordinary category membership.
See [School of Names](https://plato.stanford.edu/entries/school-names/).

Apply that distinction to the code: does a name denote a category, a subtype,
an instance or a property, and does its scope match the values and behavior
it actually covers? `metal` does not cover CPI; `measure` can cover both.
Conversely, `gold` is more accurate than `metal` when the thing is specifically
gold. Broader and narrower names are not inherently better. Establish the
domain distinction from evidence rather than using philosophy to justify
unnecessary renaming.

The stages below turn this frame into reviewable decisions. No code changes
happen during examination, recording, judging or planning. The record scales
to the coordination and migration risk of the correction; the naming standard
and the evidence behind it do not.

**Use the active harness routes supplied by the skills this workflow invokes.**
Do not add a second route for an operation those skills already provide.

## Examine

Read the repository's domain vocabulary and inspect behavior within the
operator's requested scope. Follow relevant packages, directories, files,
exported interfaces, configuration, workflows, commands, tests and user-facing
copy. Trace consumers and use language-server references when available. A
text search can locate occurrences; it cannot establish what a name means or
prove that all consumers were examined.

Examination is always read-only and proportional to the requested scope:
discovering an awkward name does not authorize a renaming or an audit beyond
that scope. Separate observed behavior from assumptions and unresolved
questions.

**Output:** the evidence the selected route needs — the named thing's observed
meaning, the proposed name and its semantic benefit, concrete source
references, the consumers traced and the coverage gaps. If the requested scope
is unclear, use `judgement-call` before expanding it.

## Scale the record to the risk

Classify the correction before recording it. Every route keeps semantic
evidence, consumer tracing, the compatibility decision and behavior-preserving
verification; the classification changes how much of that evidence is durable
and separately reviewed, not whether it exists.

**A bounded correction** has all of these:

- One coherent correction that the operator has already authorized.
- Names that are internal: not exported, not part of a supported link, package
  or release surface, and not persisted, serialized or migrated state.
- Consumers that are traced or unambiguously enumerable, with no unresolved
  compatibility decision.
- No second correction that must land with it, and no cross-session
  coordination.

A bounded correction takes the ordinary agreed issue-to-PR path. Record its
evidence once — in the agreement or in the issue that carries the correction —
and hand it to `undertake`. Do not require durable candidate IDs (stable
identifiers kept through judgment, issue creation and resumption), a separate
judging pass, a durable planning record, epic mapping, or one-issue-at-a-time
ceremony. One coherent rename remains one correction: do not split it into an
issue per occurrence, however many files it touches.

**A structured audit** is everything else. It includes a broad audit across a
repository or a defined part of one, work that crosses sessions or that
another session must resume, and any correction that cannot satisfy every
bounded condition above. It also includes in particular:

- Externally observable names: exported interfaces, supported links, package
  or release surfaces, automation contracts, or user-facing copy.
- Persisted, serialized or migrated state, or a change that needs migration
  authority.
- Unknown or contested consumer impact.
- Multiple independently useful corrections that need coordination.

A structured audit keeps the full record: stable candidate IDs, separate
judgment, a durable planning record with the issue mapping, and `epic`'s
planning and sequencing gates. Its compatibility review covers the boundaries
above before implementation begins.

Finish the consumer tracing before choosing the route when the surface is
uncertain. Uncertainty is not permission to take the lighter route. An
unresolved compatibility decision blocks only the affected correction: keep it
unready and continue unrelated safe preparation.

## Record candidates

For a structured audit, create a durable, reviewable candidate list in the
agreed planning record. Give each candidate a stable identifier that remains
unchanged through judgment, issue creation and resumption. Each entry contains:

- Current name, proposed name, and concrete source references.
- The named thing's observed meaning and why the current name mismatches it.
- A prose explanation of the proposed name's semantic benefit. A longer or
  different name is not inherently clearer.
- Affected consumers and the complete coherent correction surface.
- Compatibility and migration implications, release risks, uncertainty, and
  verification needed.

A bounded correction records the same facts once, without a durable candidate
list: current name, proposed name, source references, observed meaning and
mismatch, semantic benefit, the complete consumer surface, the compatibility
conclusion and the planned verification. The agreement or issue may carry them
in a few sentences.

Distinguish semantic errors from taste. One candidate represents one coherent
correction and all references required to complete it; on either route, do not
split one rename into an issue per occurrence. Mark unknown impact as unknown
rather than assuming there are no consumers.

**Output:** candidate entries with stable IDs and evidence, plus the coverage
note, for a structured audit; the bounded correction's concise evidence
record otherwise. No source edits or issue dispatch.

## Judge separately

A structured audit runs a separate judging pass over the recorded evidence.
For each candidate, select, reject or defer it and state why. Weigh semantic
accuracy and clarity benefit against churn, ambiguity and migration risk. The
judge may recommend keeping the current name or select nothing. Separate
judgment from operator scope agreement; judgment itself is not permission to
edit or dispatch. Do not require a paid service or hard-code a frontier model.

A bounded correction needs no separate pass. Its judgment is the operator's
agreement on the stated evidence: weigh the same semantic and clarity benefit
against churn and the recorded compatibility conclusion, then record the
decision. That agreement is still not permission to edit or dispatch until the
complete scope is agreed.

**Output:** a decision and rationale for every structured candidate, including
rejected and deferred entries, with stable IDs and the original evidence; the
agreed decision for a bounded correction.

## Plan and agree

Every route agrees the complete correction scope before implementation begins.
A bounded correction agrees it directly with the operator and, when an issue
is needed, records it under `issue-body` as one coherent task. It does not
require `epic`.

A structured audit presents the selected candidates and each complete
correction scope for agreement through `epic`. Keep candidate decisions and the
mapping to issues in the durable planning record so another session can resume
without reconstructing the audit. A zero-candidate result is a supported
no-change outcome.

After agreement, search for existing issues before creating one per selected
candidate. Use `issue`, `issue-body`, `issue-labels` and `issue-deps` for issue
content, kind, and verified graph relationships. Include the candidate ID
where the route has one, plus the evidence, old and proposed names, affected
consumers, compatibility decision, verification, and required model class in
each handoff. Record only actual code dependencies; shared files alone do not
establish a blocker.

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

Compatibility is specific to each candidate, whether or not the correction is
bounded. Identify internal and externally observable names, consumers,
supported links, package and release effects, automation, persisted state and
migration authority. Pagoda #318 is a practical example of these distinct
boundaries, not an instruction to change Pagoda or a universal compatibility
policy. Do not silently drop supported consumers, introduce unapproved aliases,
or hand-edit package manifests or lockfiles; follow the package manager. A
naming audit grants no deployment, production or state-migration authority. If
required authority is unavailable, leave that correction unready and report
the exact boundary; do not probe production.

**Output:** one issue-backed correction per agreed scope, with its completed
checks and remaining compatibility boundaries. The audit and planning phases
alone never count as implementation.
