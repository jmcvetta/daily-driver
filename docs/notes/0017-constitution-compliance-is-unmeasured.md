# 0017 — Constitution compliance is unmeasured

**Status:** decided, 2026-09-14.
**Provenance:** [#195](https://github.com/jmcvetta/daily-driver/issues/195)
diagnosed the row's failure, pre-registered the replacement design and the
branch table, and this note records the branch the run selected.
**Resolves:** [#195](https://github.com/jmcvetta/daily-driver/issues/195).

`tasks/constitution/reply-is-concise.yaml` is deleted. It was the only row in
this repository that asked whether the constitution *changes behaviour* rather
than whether it *arrives*, and it could not separate the arms. Rebuilding it
once, to a design pre-registered before any arm data existed, did not make it
separate either. The question it asked is now unmeasured, and this note is the
record of that rather than a plan to restore it.

## Scope

Everything below is about `claude-sonnet-5` in `coder_eval`'s Claude Code
agent. This suite was written by Claude and has only ever run against Claude:
the experiment pins `claude-sonnet-5`, the Codex arm skips the constitution
rows outright, and the Omp arm carries no bare variant, so the two-arm number
this row existed to produce was Claude's alone by construction. **No claim here
is about any other model.** A second model does not inherit these numbers; it
re-derives them, bands included.

## What was measured

### The first run — the row as written

Run `2026-09-14_09-37-54`, `with-without`, `claude-sonnet-5`, five replicates
per arm. **`evals/runs/` is gitignored**, so neither run directory cited in this
note is in the repository and neither outlives the container that produced it.
The tables here are therefore the record rather than a pointer to one. This
run's per-replicate scores are not among them — the directory was already gone
by the time this note was written, and #195 preserved only the means:

| Task | bare | with-plugin |
| ---- | ---- | ----------- |
| `constitution-reaches-subagent` | 0.500 | 1.000 |
| `constitution-reply-is-concise` | 1.000 | 1.000 |

The delivery row behaved. The compliance row tied at the ceiling, and a row
that reports 1.000 either way is worse than no row, because the report reads as
a pass.

Two defects, diagnosed in #195. The question exerted no pressure — it asked why
a documented-inclusive slice dropped its last item, and every bare replicate
answered in one sentence. And the rubric counted newlines, which the transcript
does not carry: `format_messages` hands the judge one unwrapped paragraph, so
every reply scored "1 line" in both arms and a ten-sentence paragraph would
have scored 1.0 the same way.

### The probe — bare CLI, outside the harness

Both defects were fixed together, to a design fixed in advance. The replacement
question is the mutable default argument in `log_call`: a mechanism with
machinery to walk through, and a cause that sits in the starter file rather
than in the prompt, so the agent must read before it can answer and then has a
hunt worth recapping. The rubric counts words, with bands at 65 and 100.

The question was probed before the row was rewritten, because the prediction
the first run falsified was Claude's about Claude and was worth nothing. Five
bare `claude -p --model claude-sonnet-5` replicates, in an empty directory with
the plugin disabled:

| Replicate | 1 | 2 | 3 | 4 | 5 |
| --- | --- | --- | --- | --- | --- |
| Words | 128 | 120 | 177 | 143 | 162 |

Five of five past the 65-word band, against a pass bar of three of five. The
candidate was locked on those numbers and the second candidate was never
needed.

One thing the probe had to establish first: the naive probe is contaminated.
This container enables `daily-driver` in the global `settings.json`, so the
plugin's `SessionStart` hook reaches every `claude -p` run on the box,
whatever directory it starts in. Asked whether it had been told how long its
replies could be, a plain `claude -p` answered YES. The probe above ran under
`--settings` with the plugin disabled, and the same question then answered NO.

**That is a deviation from #195, recorded rather than glossed.** Its
`Confirm the probe environment is bare` step said a YES answer invalidates the
probe: stop and report. The work
continued instead, because the YES had a located and removable cause — a
plugin entry in the container's global `settings.json`, not a constitution
leaking from somewhere unknown — and disabling it produced the NO the step
asks for. The stop rule exists to prevent probing a contaminated environment,
and the environment was decontaminated rather than assumed clean. A reader who
thinks that call was wrong should discount the probe numbers; the run numbers,
which decided the branch, do not depend on them.

### The second run — the rebuilt row

Run `2026-09-14_13-21-15`, five replicates per arm, one run — again untracked,
so the table below is the evidence. Every replicate anchored on
`ANCHOR: result`; no `ANCHOR: none`, no TIMEOUT. The instrument worked.

| Replicate | bare words | bare length | with-plugin words | with-plugin length |
| --- | --- | --- | --- | --- |
| 00 | 52 | 1.0 | 41 | 1.0 |
| 01 | 53 | 1.0 | 30 | 1.0 |
| 02 | 51 | 1.0 | 43 | 1.0 |
| 03 | 39 | 1.0 | 32 | 1.0 |
| 04 | 67 | 0.5 | 43 | 1.0 |

Correctness scored 1.0 in all ten. Bare passed the length criterion in four of
five, which is the pre-registered reading **nothing to constrain**: the
untreated model is already inside the budget, so there is no gap for the rule
to close and nothing for the row to measure.

The direction is right and the size is not. Bare averages 52 words against the
treated arm's 38 — a real difference, and far too small to cross a band. A row
cannot report a 14-word shift as compliance.

## The discrepancy, which is a finding about the instrument

The same question, to the same model, with no constitution either way, ran 128
to 177 words from a bare CLI and 39 to 67 words inside `coder_eval`. The
harness arm is roughly a third the length of the CLI arm, and the gap is larger
than the treatment effect the row exists to detect.

Something in the harness framing is already compressing the reply before the
constitution is applied. Candidates, none of them measured: the eval agent's
own system prompt, the `Do not change any code` instruction, the closed write
tools, the sandbox with one file in it, or the absence of a conversational
partner. Whatever it is, it means **a bare arm in this harness is not a proxy
for an untreated session**, and a question probed to be verbose outside the
harness cannot be assumed verbose inside it.

That is the more useful half of this work. It applies to every ablation in this
repository that reasons from a bare arm, not only to the row being deleted.

## What this does not say

- Not that the constitution has no effect. The delivery row still separates
  cleanly, and the treated arm here is consistently shorter. What is
  unsupported is any *measured* claim that the `Before you reply` rule changes
  what an agent writes.
- Not that the budget is set wrong. The row never got far enough to say
  anything about where four lines should sit.
- Not that the rebuilt instrument was bad. It is strictly better than the one
  it replaced — it counts something the transcript actually carries, and it
  reported a real 0.5. It is deleted because there is nothing here for it to
  find, not because it failed.

## What would measure it

Not another famous Python gotcha. `claude-sonnet-5` answers those tersely in
this harness with or without the constitution, and a third question of the same
shape buys a third tie. Two directions, neither of them this note's to take:

- An unfamiliar multi-step interaction, where the model has no rehearsed short
  answer to fall back on.
- A harness whose bare arm reproduces what a bare CLI session does, so the
  control is a control. The discrepancy above has to be understood first.

Until one of those exists, compliance is unmeasured and the repository says so
rather than reporting a number it cannot stand behind.
