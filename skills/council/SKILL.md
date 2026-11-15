---
name: council
description: >-
  Use only when the user explicitly asks for a multi-model council to explore a
  planning question, proposal, or open research direction before intent is
  settled. Compare options, risks, unanswered questions, and disagreements with
  Agent Council; return evidence and stop. Not for ready-task execution, issue
  creation, epic decomposition or dispatch, undertaking, implementation, PR
  review, or other settled work. Never invoked automatically by another skill.
---

# Council

Use Agent Council as an optional planning precursor when the user explicitly
requests a council for an open planning question, proposal, or research
direction. The user owns the prompt and the Agent Council ensemble
configuration. This skill returns planning evidence and stops; it does not
settle user-owned choices or begin execution.

## Before the run

Read the active harness reference before running: [Omp](references/omp.md),
[Claude Code](references/claude.md), or [Codex](references/codex.md). Use only
the native shell in the intended repository. Do not create a task worktree,
edit repository or Git state, run tests or builds by default, or start
persistent services.

Confirm that `agent-council` is already installed and available, and that the
user identified the prompt file and ensemble configuration. Do not install or
configure Ruby, Pi, Agent Council, providers, or credentials. Do not read,
copy, or print credentials. If the prerequisites are missing, report them and
stop without changing the environment.
Before invoking the command, state that Agent Council starts several Pi agents
and an optional consolidator; it is not sandboxed. Its agents can run shell
commands, and repository files and command output can be sent to every
configured provider. The command calls providers at their usual rates. Continue
only for an explicit request to run this council with an identified prompt and
ensemble configuration. If the user asks only for planning advice or has not
identified either input, explain the boundary and request only the missing
inputs; do not run.

Keep the planning prompt read-only. Do not ask analysts to edit files or change
Git state. Do not request tests or builds unless the user explicitly asks;
never start persistent services. The external CLI cannot enforce this boundary.

## Run

Run from the repository the user wants analyzed. Keep the prompt and config at
the paths the user identified. Put all reports outside the repository with
Agent Council's `--output-dir`; never use its default in-repository report
directory. Use a fresh temporary directory and confirm its resolved path is
outside the repository before execution. Do not use `--consolidate` together
with `--output-dir`.

Run the exact native shell command from the harness reference, with the
identified configuration as the optional second positional argument. The
command is an external provider operation with the providers' usual rates. Do
not change the selected models, provider setup, or credentials.

## Report and stop

Return the consolidated findings, material contradictions, and open questions.
Preserve substantive disagreement; do not convert it into a false consensus or
resolve decisions the user owns. Identify the individual analyst reports and
`run.json`, failed analysts, and available duration and usage. A single
successful analyst is one opinion, not consensus. The consolidator's claims
are advisory, not verified facts; identify which claims still need evidence.

State the task directory containing the reports. Do not copy them into the
repository. Do not create issues or epics, dispatch work, or continue into
implementation or review. Any later action uses its own normal workflow after
the user settles intent.

## Non-goals

- Automatic use by `issue`, `epic`, `undertake`, `embark`, or `review-cycle`.
- Issue creation, decomposition, model routing, implementation, verification,
  or pull-request review.
- Installing or managing the external CLI, Ruby, Pi, providers, or credentials.
