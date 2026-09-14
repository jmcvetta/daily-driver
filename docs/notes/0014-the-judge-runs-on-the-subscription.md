# The judge runs on the subscription

**Status:** decided, 2026-09-11.
**Provenance:** found while running
[#158](https://github.com/jmcvetta/daily-driver/issues/158)'s nine
`references` rows, on the second attempt at that run.
**Supersedes:** the premise of
[`0012`](0012-the-judge-needs-its-own-transport.md), not its decision. The
pre-run guard `0012` added is still right and still runs. What changed is why
a row would trip it: not a key an operator forgot, but a criterion this
project cannot run at all. See "What is left" for the four rows that still
trip it.

`0012` treated a missing `ANTHROPIC_API_KEY` as a configuration gap — something
an operator sets before a run. It is not. This project's only Claude access is
a Max subscription, and it will not acquire a metered API key. `llm_judge`
calls the Anthropic API directly, so on the DIRECT backend it needs that key by
construction, and the two remedies `0012` names are both out of reach:
`ANTHROPIC_API_KEY` is metered, and `API_BACKEND=bedrock` wants
`AWS_BEARER_TOKEN_BEDROCK` and `AWS_REGION`, which is a Bedrock API key and
metered too.

Eight of the nine `references` rows carried their finding in a weight-2
`llm_judge`. Written that way, those findings could never execute here. That is
not a run waiting on credentials; it is a criterion chosen wrongly.

## Decided

**Every judge in the nine `references` rows is `agent_judge`, and no new
judge anywhere in this suite is `llm_judge`.**

`coder_eval`'s `agent_judge` spawns a Claude Code SDK agent as the judge
instead of calling the API. It builds that agent through the same
`ClaudeCodeAgent` and the same route as the agent under test
(`evaluation/sub_agent.py:193`), and the DIRECT branch of the environment
builder (`agents/claude_code_agent.py:817`) leaves `ANTHROPIC_API_KEY` alone
and lets the SDK inherit the environment. So the judge authenticates exactly
the way the agent under test already does, which on this project is the
subscription.

`AgentJudgeCriterion` mirrors `LLMJudgeCriterion`'s prompt and context fields —
`prompt`, `include_agent_output`, `include_reference`, `weight` are all shared
— so the eight findings ported across unchanged. Only the `type` line and a new
`agent` block differ.

### Two settings in that block, both load-bearing

**`allowed_tools: []`.** These rows grade a reply, and
`include_agent_output: true` pre-attaches the whole transcript to the judge's
prompt. There is nothing for the judge to go and look at, so it is given
nothing to look with. That is also the narrowest available answer to the
prompt-injection surface `AgentJudgeCriterion`'s own docstring warns about: the
transcript being graded is untrusted text, and the criterion's default tool
surface is `[Bash, Read, Glob, Grep]`. The `submit_verdict` MCP tool is
force-added by the criterion itself and is unaffected by the empty list.

**`permission_mode: default`.** `AgentJudgeCriterion` defaults to
`bypassPermissions`, which the CLI refuses outright when it runs as root:

```
agent_judge: sub-agent crashed: CLI process failed (exit code 1):
--dangerously-skip-permissions cannot be used with root/sudo privileges
for security reasons
```

A container runs as root, so the default makes the judge unusable in half the
places this suite runs. Nothing here needs it, because the tool surface is
empty.

## What the port costs

It is tempting to say `agent_judge` fails more loudly than `llm_judge`. It
does not. Checked in `coder_eval` 0.11.6: `llm_judge`'s unconfigured-transport
path (`criteria/llm_judge.py:123`) returns score 0.0 with `details` **and** a
populated `error`, exactly as `agent_judge`'s crash path
(`criteria/agent_judge.py:230`) does, and `reports.py` keys on `cr.error`
without reference to the criterion type. Both surface the same way.

What the port does change is coverage, and it changes it for the worse.
`scripts/evals-preflight.py` matches `type: llm_judge` and nothing else, so
these eight rows have left the one guard standing in front of them. The
failure they can now have is also harder to read than the one they had: a
judge that cannot start fails per replicate, so it shows as some replicates
missing from a mean rather than as a row uniformly zero.

That is a real cost, accepted because the alternative is eight findings that
never execute at all. Two things hold it down, and neither is the guard:
`permission_mode` and `allowed_tools` are set explicitly on every one of
these rows, which is what the crash above was; and `max_turns` and
`turn_timeout` are bounded, so an overrunning judge cannot silently cancel
its replicate against `task_timeout`. A `make check` leg asserting those four
fields on every `agent_judge` in the tree is the guard this note does not
add.

## What is kept

`scripts/evals-preflight.py` stays, and `make evals-run` still depends on it.
It reports `no enabled llm_judge criteria` on the nine `references` rows,
which is the answer it should give there. It is a guard against the criterion
coming back — by a row copied from upstream's examples, or written from
memory — not a guard against a missing key.

## What is left

Thirteen rows elsewhere in the suite still carry an enabled `llm_judge`, so
`make evals-run` over the whole suite still stops at the guard. Four are
Claude-arm rows outside the nine:

- `tasks/constitution/reply-is-concise.yaml`
- `tasks/embark/06-launches-without-asking.yaml`
- `tasks/issue-deps/02-write-the-edge-without-asking.yaml`
- `tasks/undertake/08-wake-slot-is-refilled.yaml`

The other nine are the `omp-only` forks `0013` added, including the forks of
eight of the nine rows this note is about. They have the same defect, and the
same fix would work on them: `agent_judge` spawns a Claude Code SDK judge
whatever harness produced the transcript it grades, exactly as `llm_judge`
called the API whatever produced it.

They are not ported here for one reason: they cannot be run. The Omp arm needs
`omp` on `PATH` and a provider configured, which `0013` records as still
outstanding, so a port of those nine would ship rubrics nobody has executed.
Porting them belongs with the first paid run of that arm.

One of them is worth flagging while it is in view. `pr-07-one-call-sets-both-omp`
grades the same "one call, not two" rule its Claude sibling has just been
corrected away from — and on Omp `gh pr edit` is the *right* answer, so the
bare arm reaches for the same tool the treated arm should. Whatever separates
those two arms, the single-call fact on its own probably does not. That is a
prediction from reading it, not a measurement.

## What this does not claim

Nothing here says `agent_judge` grades *as well as* `llm_judge` would. It is a
different instrument: a full agent turn rather than a single completion, with
its own system prompt and its own verdict channel. The rows' rubrics were
written for a one-shot judge and were not retuned. Whether any of them needs
retuning is a question the scores answer, not this note.
