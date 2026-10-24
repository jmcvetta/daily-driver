# Skills

Daily Driver's skills give coding agents instructions for recurring engineering
tasks. Ask for the work in plain language or name the skill you want. For example:

> Use epic to break this feature into task issues.
>
> Review this pull request and address the findings.
>
> Use deps to resolve the open Dependabot pull requests.

The links below open each skill's instructions. Where tool calls differ across
Omp, Claude Code and Codex, the skill links to its harness-specific references.
See [runtime integration and compatibility](../docs/harness-integration.md) for
limits; a shared skill does not imply identical capabilities on every harness.

## Plan and carry out work

| Skill | When to use it |
| ----- | -------------- |
| [epic](epic/SKILL.md) | Break work into multiple issues and establish their dependencies and completion criteria. |
| [undertake](undertake/SKILL.md) | Take a task issue through implementation, verification and PR review, or produce an evidenced research answer. |
| [task-worktree](task-worktree/SKILL.md) | Establish an isolated feature branch and worktree before repository-changing work. |
| [embark](embark/SKILL.md) | Dispatch eligible child issues of an epic in parallel and monitor the work. |
| [stand-down](stand-down/SKILL.md) | Stop an embarked epic, preserve work in progress, and record a handoff. |

## Create and organize issues

| Skill | When to use it |
| ----- | -------------- |
| [issue](issue/SKILL.md) | Open or update a GitHub issue; coordinate its body, labels and relationships. |
| [issue-body](issue-body/SKILL.md) | Write an issue body with the scope, evidence and completion conditions required by its kind. |
| [issue-labels](issue-labels/SKILL.md) | Classify issues and determine which kinds are eligible for agent work. |
| [issue-deps](issue-deps/SKILL.md) | Record or inspect blocked-by, parent/sub-issue and PR-closes relationships. |

## Prepare and review changes

| Skill | When to use it |
| ----- | -------------- |
| [pr](pr/SKILL.md) | Open a pull request for the current branch or update the existing one. |
| [pr-title](pr-title/SKILL.md) | Write or revise a Conventional Commits PR title. |
| [conventional-commits-type](conventional-commits-type/SKILL.md) | Choose the change type from its effect, including the resulting release significance. |
| [pr-body](pr-body/SKILL.md) | Write a PR description with linked issues, a summary and relevant detail. |
| [review-cycle](review-cycle/SKILL.md) | Review a PR, address findings, verify corrections and resolve review threads. |
| [deps](deps/SKILL.md) | Upgrade dependencies in bulk or resolve open Dependabot pull requests. |

## Write and communicate

| Skill | When to use it |
| ----- | -------------- |
| [readme](readme/SKILL.md) | Explain what a project or directory provides and how to use it. |
| [judgement-call](judgement-call/SKILL.md) | Distinguish engineering choices the agent should settle from tradeoffs that need the user's decision. |
| [provenance](provenance/SKILL.md) | Record the model, harness and session responsible for GitHub contributions and commits. |
| [session-title](session-title/SKILL.md) | Give the current session a short, recognizable title. |

The [constitution](../rules/constitution.md) supplies the shared engineering rules
across these workflows. Return to the [project README](../README.md) for
installation and a task-to-PR example.
