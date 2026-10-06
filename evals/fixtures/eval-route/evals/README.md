# Evaluations (fixture excerpt)

Test fixture: an excerpt of `evals/README.md`, the entry point, as of the
`Choose the execution session first` section. Refresh it when that section changes.

### Choose the execution session first

Choose the subject model, judge model, and execution session separately. A
Claude subject does not require a Claude judge, and evaluations need not use
Claude for every judge. **When a Claude judge grades the run — the default for
every `agent_judge` — run the entire evaluation from a Claude Code session**,
web or CLI. The judge runs through the Claude Code SDK and inherits that
session's subscription. A non-Claude judge selected with `JUDGE=` is the
exception; see [Choosing the judge](#choosing-the-judge). Running
`make evals-run` from Omp is not a supported route for a Claude-judged
evaluation, even when the subject arm is Omp. Do not turn a judge failure in
Omp into a request to repair local Claude authentication.

Before any model or authentication probe, an Omp caller must select a Claude
Code execution session. Use an existing authorized handoff facility if the
current environment provides one; do not invent a dispatch or launch a local
probe to discover this known boundary. If it provides no such facility, record
this handoff for a Claude Code session:

> Run the requested evaluation from this Claude Code web or CLI session.
> Use the repository's existing `make evals-plan` and the narrow `make
> evals-run TASKS='…'` target below. Let the Claude Code SDK inherit this
> session's subscription. Do not ask for login repair, search for or transfer
> OAuth tokens, or use a metered Anthropic or gateway route. Return the run
> identifier and observed results; do not claim a pass without the recorded
> run evidence.

No local `claude -p` probe is needed before that handoff. A failed supported
SDK run must be diagnosed from current evidence in the Claude Code execution
session. A previous error, an agent's claim, or a local CLI failure in Omp
does not establish that the subscription route is unavailable. Request human
action only when current evidence shows an indispensable human contribution.
[`docs/notes/0014`](docs/notes/0014-the-judge-runs-on-the-subscription.md)
is the current decision; this README is the single operational runbook.
