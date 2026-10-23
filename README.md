# daily-driver

Daily Driver gives coding agents a shared engineering constitution, task-specific
skills, and runtime integrations for Omp, Claude Code and Codex. You direct the
task; the agent uses the workflow to plan, implement, verify, and prepare its
change for review.

This is the author's personal toolkit, published without a license. See
[License](#license) and [ANTI-LICENSE.md](ANTI-LICENSE.md); installation does
not grant reuse rights.

## Installation

Install the plugin in the environment where you use it. Detailed setup,
migration, cloud configuration and compatibility limits are in
[Repository setup](docs/bootstrapping-a-repository.md).

### Omp

```sh
omp plugin marketplace add jmcvetta/daily-driver
omp plugin install daily-driver@daily-driver
```

### Claude Code

```sh
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install daily-driver@daily-driver
```

### Codex

Codex uses `plugin add`:

```sh
codex plugin marketplace add jmcvetta/daily-driver
codex plugin add daily-driver@daily-driver
```

Codex stores plugin registration in `$CODEX_HOME/config.toml`; preserve its
plugin tables when editing that file. See [Codex setup and
limitations](docs/bootstrapping-a-repository.md#codex-has-no-stanza-at-all).

## Usage

In a repository with a task issue, ask:

> Undertake issue #123 in this repository.

The workflow is designed to create an isolated task branch and worktree,
implement the issue, gather verification evidence, and open a pull request for
review. Results depend on the task and the active harness; a request does not
guarantee success or a merge.

## Skills

Skills are instructions for recurring engineering tasks. Ask in plain language
or name a skill; the [skill catalog](skills/README.md) explains when to use each.

| Task | Provided skills |
| ---- | --------------- |
| Plan and carry out work | [epic](skills/epic/SKILL.md), [undertake](skills/undertake/SKILL.md) |
| Coordinate parallel work and stop it safely | [embark](skills/embark/SKILL.md), [stand-down](skills/stand-down/SKILL.md) |
| Isolate changes and handle decisions | [task-worktree](skills/task-worktree/SKILL.md), [judgement-call](skills/judgement-call/SKILL.md) |
| Create and organize issues | [issue](skills/issue/SKILL.md), [issue-body](skills/issue-body/SKILL.md), [issue-labels](skills/issue-labels/SKILL.md), [issue-deps](skills/issue-deps/SKILL.md) |
| Prepare and review pull requests | [pr](skills/pr/SKILL.md), [pr-title](skills/pr-title/SKILL.md), [pr-body](skills/pr-body/SKILL.md), [review-cycle](skills/review-cycle/SKILL.md) |
| Classify changes and upgrade dependencies | [conventional-commits-type](skills/conventional-commits-type/SKILL.md), [deps](skills/deps/SKILL.md) |
| Write documentation and identify agent work | [readme](skills/readme/SKILL.md), [provenance](skills/provenance/SKILL.md), [session-title](skills/session-title/SKILL.md) |

## Constitution

The [constitution](rules/constitution.md) supplies the shared engineering rules
that apply across tasks, while skills describe individual workflows. It covers
safe system access, isolated worktrees, tests for application code, CI
verification, focused commits, and concise communication. The
[runtime integrations](docs/harness-integration.md) load these instructions;
their enforcement and subagent coverage vary by harness.

## Links

- [Repository setup](docs/bootstrapping-a-repository.md): detailed installation,
  migration, configuration and verification.
- [Shared workflow case study](docs/shared-workflow-case-study.md): the
  completed Codex integration and the evidence limits.
- [Harness architecture](docs/notes/0011-two-harnesses-one-skill-tree.md) and
  [Codex integration](docs/notes/0016-three-harnesses-one-skill-tree.md):
  design decisions and harness behavior.
- [Runtime integration and compatibility](docs/harness-integration.md):
  hooks, the Omp extension, worktree behavior and harness limits.
- [Evaluation guide](evals/README.md) and [measured results](evals/RESULTS.md):
  evaluation method and recorded runs.
- [License status](ANTI-LICENSE.md): the project's no-license notice.

## License

No license is granted. This personal toolkit is not open source. See
[ANTI-LICENSE.md](ANTI-LICENSE.md) for the full notice.
