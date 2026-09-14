# The judge needs its own transport

**Status:** decided, 2026-09-11.
**Provenance:** found while running
[#158](https://github.com/jmcvetta/daily-driver/issues/158)'s nine
`references` rows — the run the issue asked for surfaced a defect the issue
did not anticipate.
**Resolves:** the `llm_judge` half of
[#158](https://github.com/jmcvetta/daily-driver/issues/158#issuecomment-5634289151)'s
first finding.

`coder_eval`'s `llm_judge` criterion needs a transport to a judge model, and
that transport is separate from whatever authenticates the agent under test.
On the default DIRECT backend,
`models/routing.py::_resolve_direct_judge_transport` picks `"anthropic"` iff
`ANTHROPIC_API_KEY` is set, and `None` otherwise. `criteria/llm_judge.py` does
not fail the run when it gets `None` — it returns score 0.0 with
`details="(judge transport unconfigured)"`, logs one `ERROR` line, and the run
**continues**. Only the DIRECT backend can be unconfigured this way; BEDROCK
and LITELLM always carry a usable transport.

Running `tasks/session-title/07-get-session-before-set.yaml` with no
`ANTHROPIC_API_KEY` set made this concrete. `experiment.md` reported `Score
0.000 (bare) / 0.333 (with-plugin)`, `Best: with-plugin`, `Win Rates —
with-plugin: 1/1 tasks (100%)`. That reads as a clean ablation. The row's
entire 0.333 was the weight-1 `skill_triggered` criterion; the weight-2
`llm_judge` — the criterion actually carrying the row's finding — never ran.
Nothing in the report says so. The per-replicate log does
(`API routing: anthropic_direct (judge transport: none)`, then the `ERROR`
line), and `task.json` records `environment_info["judge_transport"]`, but
neither reaches `experiment.md`, which is the file anyone actually reads.
Eight of the nine `references`-tagged rows carry their finding in a weight-2
`llm_judge`, so this one missing key silently voids most of that suite.

## Decided

**A pre-run guard, `scripts/evals-preflight.py`, not a `make check` leg.**
`make evals-run` now depends on it: it reads every task file `$(TASKS)`
would pass to `coder-eval`, and where an enabled `llm_judge` criterion exists
and the resolution rule above says its transport would be unconfigured, it
exits 1 before a model is called — naming the offending rows and a remedy
that actually works from this Makefile (`ANTHROPIC_API_KEY`, or
`API_BACKEND=bedrock make evals-run`), rather than the flag `llm_judge`
itself would name if it were allowed to fail instead of scoring 0.0.

**Why before the run rather than after.** The alternative — read the report
more carefully, or grep `task.json` for `judge_transport` — is exactly what
already failed here: the information is in the run's own output and a reader
still missed it, because a 0.333 with a `Best:` line does not look like
something to double-check. A guard ahead of the run saves the run's own cost:
every replicate of every row in an unconfigured `llm_judge` run gets paid for
and produces a number nobody can trust.

**The first version duplicated a rule that lives upstream, and that turned
out to be a real cost, not a free one.** It reimplemented `coder_eval`'s
settings resolution using `os.environ` alone, and got it wrong three ways. A
`medium` code review on PR #166 found all three, correctly, and traced them
to the one root cause:

1. It read `API_BACKEND` from the shell environment only. `Settings` also
   resolves it from a cwd-relative `.env` (`config.py`'s
   `env_file=".env"`), so a real run configured entirely through
   `evals/.env` graded fine while the guard, seeing no shell variable,
   blocked it.
2. Its own `.env` reading sat behind an optional `python-dotenv` import that
   the interpreter running the guard did not have available — `python-dotenv`
   is a dependency of the separately-installed `coder-eval` tool, not of this
   repository's own tooling — so the repository's own documented path,
   `ANTHROPIC_API_KEY` in `evals/.env`, was silently blocked by the guard
   meant to protect it.
3. Its remedy text named `--backend bedrock`, copied verbatim from
   `coder_eval`'s own dispatch-time message. That flag only becomes
   `API_BACKEND` inside `coder_eval`'s own CLI, after the guard has already
   run, and `make evals-run` has no flag passthrough to reach it at all. The
   only form that actually clears the guard, `API_BACKEND=bedrock make
   evals-run`, was never named.

**The fix is to delegate, not mirror.** The guard now locates the real
`coder-eval` installation — `coder-eval` on `PATH`, whose shebang names its
own venv's interpreter — and runs a short probe under that interpreter, from
the same working directory `evals-run` itself uses. The probe imports
`coder_eval.config.Settings` and `coder_eval.models.routing.resolve_route`,
builds the route the way a real run would, and reports whether
`criteria/llm_judge.py` would find a transport on it. The guard parses that
result; it carries no copy of `coder_eval`'s resolution rule to drift.
`scripts/check-evals-preflight.py` covers the new shape against a stub
`coder-eval`/`coder_eval`, offline, so the probe's own plumbing — subprocess,
shebang parsing, result parsing — stays under test without needing the real
tool installed in CI.

## What it deliberately does not do

**Does not import `coder_eval` into its own process.** The guard itself runs
under system `python3`, which does not have `coder_eval` or its dependencies
installed. It asks a SEPARATE process — the probe, launched under
`coder-eval`'s own interpreter — to resolve settings and report back; that is
a subprocess call out to the real tool, not a patch to it and not an import
into this one.

**Does not catch every way the transport could fail.** Only the
"unconfigured" case — a present-but-wrong key, an expired one, a network
error, all fail the same way any other API error does, mid-run, and this
guard has nothing to say about them. It exists for the one failure mode that
is silent by design upstream.

**No longer needs to know where `coder_eval` would read a `.env` from.**
That not-knowing was the first version's whole problem. The probe now runs
`coder_eval` itself, from the same working directory `evals-run` uses, so
`Settings` resolves `.env` exactly the way the real run's `Settings` would —
cwd-relative search included — and this repository carries no copy of that
resolution to get wrong or leave stale when `coder_eval` changes it.

**Not part of `make check`.** Like `evals-plan` and `evals-run` themselves, it
needs task YAML in hand to mean anything; `check-evals-preflight` — the
acceptance test for the guard itself, run against synthetic fixtures — is
the leg that is.
