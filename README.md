# daily-driver

Daily Driver gives coding agents a shared engineering constitution, task-specific
skills, and runtime integrations for Omp, Claude Code and Codex. You direct the
task; the agent uses the workflow to plan, implement, verify, and prepare its
change for review. Harness support levels and their limits are in
[Runtime integration and compatibility](docs/harness-integration.md#support-levels).

This is the author's personal toolkit, published without a license. See
[License](#license) and [ANTI-LICENSE.md](ANTI-LICENSE.md); installation does
not grant reuse rights.

## Installation

Install the plugin in the environment where you use it. Detailed setup,
migration, cloud configuration and compatibility limits are in
[Repository setup](docs/bootstrapping-a-repository.md).

### Omp

Supported and tested: the required eval arms and live runtime checks run here.

```sh
omp plugin marketplace add jmcvetta/daily-driver
omp plugin install daily-driver@daily-driver
```

### Claude Code

Best effort: the plugin, hooks and per-skill reference routes are maintained,
with no required eval arm or live runtime check.

```sh
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install daily-driver@daily-driver
```

### Codex

Best effort on the same terms. Codex uses `plugin add`:

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

For work that needs research before implementation, use `epic` to coordinate
a discovery and interactive specification, then `embark` the promoted epic.

## Local maintenance

In this repository, ask Omp to `fix-daily-driver-bugs` to triage open automatic
reports and dispatch eligible fixes. While coordinating, the session title is
`🐛 Daily Driver bug fixes`; issue implementors keep their issue-based titles.
Include issue numbers to limit triage. This repository-local skill is not part
of the published plugin.

## Skills

Skills are instructions for recurring engineering tasks. Ask in plain language
or name a skill. The [skill catalog](skills/README.md) is the authoritative
index: it lists every skill in workflow order and explains when to use each.

- **Plan and carry out work** — `undertake` completes an assigned issue;
  `specification` and `epic` settle larger work before implementation;
  `embark` and `stand-down` coordinate parallel sessions.
- **Create and organize issues** — `issue`, `issue-body`, `issue-labels` and
  `issue-deps` write issues and connect their relationships.
- **Prepare and review changes** — `pr`, `pr-title`, `pr-body` and
  `review-cycle` open, validate and review pull requests; `deps` resolves
  dependency upgrades.

## Constitution

The [constitution](rules/constitution.md) keeps universal safety, authority,
task isolation, evidence, and execution rules always available. Workflow
details stay in their owning skills. The
[skill catalog](skills/README.md) supplies the
workflow map. [Runtime integration](docs/harness-integration.md) describes
delivery, with its dated measurements in
[runtime-integration-measurements](docs/runtime-integration-measurements.md).

The constitution consumes context in every session and delivered subagent, so
keep this document focused: include rules that change behavior in most
sessions, address a nameable moment, and add something the harness does not
already supply. Amend it through a pull request against Daily Driver.

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
- [Runtime integration measurements](docs/runtime-integration-measurements.md):
  dated delivery-measurement checkpoints and the evidence-file links.
- [Quality controls](docs/quality-controls.md): the deterministic checks every
  repository runs, by control and by language.
- [Evaluation guide](evals/README.md) and [measured results](evals/RESULTS.md):
  evaluation method and recorded runs.
- [License status](ANTI-LICENSE.md): the project's no-license notice.

## License

No license is granted. This personal toolkit is not open source. See
[ANTI-LICENSE.md](ANTI-LICENSE.md) for the full notice.
