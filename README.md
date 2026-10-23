# daily-driver

Daily Driver gives coding agents shared skills and runtime integrations for
guiding repository work from planning through implementation and review. You
direct the task; the agent uses the workflow, verifies its change, and prepares
it for review.

This is the author's personal toolkit, published without a license. See
[License](#license) and [ANTI-LICENSE.md](ANTI-LICENSE.md); installation does
not grant reuse rights.

## Installation

Install the plugin in the environment where you use it. Detailed setup,
migration, cloud configuration and compatibility limits are in
[Repository setup](docs/bootstrapping-a-repository.md).

### Claude Code

```sh
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install daily-driver@daily-driver
```

### Omp

```sh
omp plugin marketplace add jmcvetta/daily-driver
omp plugin install daily-driver@daily-driver
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

## Links

- [Repository setup](docs/bootstrapping-a-repository.md): detailed installation,
  migration, configuration and verification.
- [Shared workflow case study](docs/shared-workflow-case-study.md): the
  completed Codex integration and the evidence limits.
- [Harness architecture](docs/notes/0011-two-harnesses-one-skill-tree.md) and
  [Codex integration](docs/notes/0016-three-harnesses-one-skill-tree.md):
  design decisions and harness behavior.
- [Skills](skills/): workflow instructions and per-harness references.
- [Runtime integration and compatibility](docs/harness-integration.md):
  hooks, the Omp extension, worktree behavior and harness limits.
- [Evaluation guide](evals/README.md) and [measured results](evals/RESULTS.md):
  evaluation method and recorded runs.
- [Project rules](rules/constitution.md): the shared constitution.
- [License status](ANTI-LICENSE.md): the project's no-license notice.

## License

No license is granted. This personal toolkit is not open source. See
[ANTI-LICENSE.md](ANTI-LICENSE.md) for the full notice.
