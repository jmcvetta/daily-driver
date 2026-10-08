# Issue-kind body contracts

`issue-body` selects the contract by the issue's effective kind. These are
information requirements, not a quota of headings. Keep small issues small,
omit inapplicable fields, and never invent facts to fill a field. Separate
supplied observations, inspected evidence, assumptions, and open questions.
Record material constraints and unknowns. Body sufficiency is distinct from
kind eligibility: a `task`, `bug`, or `research` can be eligible for agent work
while its own readiness test still fails.

Every body write follows `provenance`'s block rules. The contracts below do
not add a kind-specific provenance format. `task` retains the full format in
[`issue-body/SKILL.md`](../SKILL.md). `epic` retains the normative format in
[`epic/SKILL.md`](../../epic/SKILL.md#the-epic-body); this reference does not
copy it.

## Research — closes on an evidenced answer

Carry:

- A precise question and the decision or practical purpose its answer serves.
  “Investigate caching” alone is not a sufficient question.
- Known facts and starting references, separated from hypotheses and unknowns.
  Repository research uses grounded pointers. External research names useful
  sources or source categories without inventing citations.
- Scope, non-goals, and material constraints on access, experiments, external
  requests, spending, or persistent changes. An issue cannot authorize an
  action forbidden by governing safety rules.
- Evaluation criteria and an adequate approach: what evidence could distinguish
  alternatives or establish feasibility. Name relevant alternatives, including
  no change when meaningful. Do not select the conclusion or require an
  exhaustive survey by default.
- The required deliverable and destination, such as an answer on the issue, a
  repository note, or implementation-ready issue specifications. Findings
  state what each source establishes separately from what the investigator
  infers; label material conclusions as inferences. Cite sources or
  reproducible experiment details, explain trade-offs, recommend a course when
  requested, and state uncertainty and limitations. Use dates or versions for
  time-sensitive evidence. Do not invent numerical confidence.
- A stopping rule: enough evidence to answer, or a justified bounded
  investigation after which remaining uncertainty is reported. Bounds can be
  named alternatives, sources, experiments, or another justified limit; do not
  invent time, token, or cost estimates.

**Ready for investigation** means an agent can proceed without guessing the
question's purpose, evaluation criteria, permitted actions, or expected output.
An unknown answer is the work, not a readiness defect. An unresolved decision
that determines what to investigate is a defect.

**Complete** means the agreed answer and evidence are delivered. A supported
“no” succeeds. “Inconclusive” is complete only when the bounded investigation
permits that result and the report records what was examined, why evidence is
insufficient, and what would resolve it. Missing credentials, a failed tool
call, or abandoned work alone is not completion. Inconclusive research does not
settle an implementation prerequisite. A closed research issue does not block
execution by itself: known affected task handoffs must still identify the
unresolved contract and fail their own readiness test. Use `issue-deps` for
real follow-on dependencies; do not invent a blocker to keep research open.

Recommendations do not decide matters reserved for the user. A requested
recommendation can complete without approval being implied. Experimental code
may be disposable; shipping a production change is a separate task. If follow-
on issues are required deliverables, create them through `issue` or `epic`
under their existing gates, without inventing an epic for one task. An answer
recorded on GitHub needs no empty pull request.

## Bug — closes on a verified correction or evidenced disposition

Carry the affected behavior or component; expected versus observed behavior;
supplied reproduction steps or the smallest available failure evidence;
relevant version, environment, and frequency when known; and material impact.
Redact secrets and private data. Say explicitly when reproduction, environment
detail, or root cause is unknown.

A plausible cause is a hypothesis, not a fact. Do not require a diagnosed cause,
settled implementation, exhaustive impact study, acceptance plan, or model
class to file a bug. A user's reported observation is evidence and need not be
rerun to qualify. `issue`'s automatic Daily Driver bug route keeps its stronger
ownership evidence and brief report; it does not acquire task machinery.

**Ready for diagnosis** means there is enough evidence to identify the
incorrect behavior and start a bounded diagnosis without guessing the expected
contract. Reproduction is valuable but not a universal filing prerequisite.
If evidence is insufficient to start, record the missing prerequisite; do not
invent a reproduction or reject a report only because it is incomplete.

**Complete** means the correction is verified against the reported failure and
relevant regressions. If investigation establishes a duplicate, intended
behavior, or a decision not to fix, record the evidence and reason under the
existing issue disposition rules. Do not say an uncorrected bug was fixed. No
implementation-plan template is required.

## Proposal — closes on a recorded decision or explicit handoff

Carry the problem or opportunity; affected users or use case; desired outcome
and value; known constraints; and open decisions that prevent commitment.
Record suggested approaches or alternatives only as suggestions unless already
agreed. Include existing evidence when available and identify the next
decision or evidence needed to assess the proposal.

**Ready for discussion** does not mean ready for unattended implementation.
Do not require a settled architecture, task model class, implementation map,
or invented pass/fail implementation criteria. An agent may draft a proposal
without choosing the user's solution. Undertaking a `proposal` remains a stop.

**Complete** means acceptance, rejection, or supersession and its rationale
are recorded. Acceptance names the handoff: one settled task when it fits one
PR, research when evidence is missing, or an epic only when its gates hold.
Convert the issue in place only under the existing label policy. Acceptance is
not delivery. Deferral alone is not delivery; a `not planned` closure follows
the existing disposition rules.

## Human — closes on a person's observable action or decision

Carry the exact action or decision; why an agent cannot perform it; the
responsible person or role when known; the inputs and context needed; and the
completion evidence and where to record it. State when responsibility is
unknown. Include a deadline only when it is real and relevant.

**Ready for a person** means that person can act without reconstructing the
request or guessing choices and consequences. This is never agent-execution
readiness. Keep credentials and sensitive proof out of the issue; request only
a safe confirmation or reference. Where permitted, distinguish agent
preparation from the action reserved for the person without implying that the
action is authorized.

**Complete** means the action or decision and its safe evidence are recorded.
An agent handing over the request is not completion. Keep relationships in
the graph; do not duplicate blocker lists in the body.
