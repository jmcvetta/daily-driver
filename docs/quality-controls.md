# Quality controls

This standard names the deterministic quality controls that our repositories
run. A deterministic control is a tool that gives the same answer on the same
input and fails loudly. It is the discipline an agent cannot talk its way past.

This version records the **current baseline**: the controls in use on
2026-10-24, and where each is in use. It adds no new check. Gaps are recorded
so that a later revision can close them.

The survey covered five repositories:

| Short name | Repository |
| --- | --- |
| DD | `jmcvetta/daily-driver` |
| CA | `jmcvetta/career` |
| PG | `Green-Pagoda/pagoda` |
| PRA | `jmcvetta/projected-releases-action` |
| CMWB | `jmcvetta/chiang-mai-wall-book` |


## How to read this standard

**A control is defined by what it guarantees, not by its tool.** Each control
has a stable ID, such as `QC-COMPLEXITY`, and one sentence that states its
guarantee. The tool is an implementation detail of one ecosystem.

**One control can have many implementations.** Each ecosystem control has an
implementation table with one row per ecosystem. Ruff's `C901` in Python and a
complexity rule in TypeScript are rows of the same control, `QC-COMPLEXITY`.
To compare two repositories, compare their rows for one control ID.

**Every row has a status:**

| Status | Meaning |
| --- | --- |
| `gate` | Runs in CI on every relevant pull request, and a failure blocks the merge. |
| `local` | Configured in the repository, but run only by hand. |
| `none` | No implementation exists yet for this ecosystem. |

A `none` row is part of the baseline. It is not an error in this document.
Tests of tests and other testing machinery are not quality controls. Do not
list them as implementations of a control.


**Two layers.** Universal controls apply to every repository. Ecosystem
controls apply to a repository that contains that ecosystem. The ecosystems
in use are TypeScript/JavaScript, Python, Ruby, OpenTofu/HCL, shell, GitHub
Actions, Ansible, containers and Claude Code plugins.

### Apply it to a project

1. Implement every universal control.
2. List the ecosystems the repository contains.
3. For each ecosystem control, implement the row for each of those
   ecosystems. Where the row is `none`, record the gap.
4. Make each gate control part of a required check (`QC-REQUIRED-CHECKS`):
   a step of `Checks`, or of `Release Projection` for the title and the
   projection, which must run on every pull request.


## Universal controls

### QC-REQUIRED-CHECKS — merge gate as code

A merge to the default branch requires named CI checks, and that requirement
is declared in version-controlled configuration.

- **Implementation.** Each repository declares its branch protection or ruleset
  in an OpenTofu stack at `infra/github/`, applied by hand. CI runs on pull
  requests.
- **CI shape.** One job, `Checks`, runs every selected check as a conditional
  step, and `Release Projection` is the second required context. A change
  selector decides which steps run: `dorny/paths-filter` (CA),
  `.github/scripts/ci-select.sh` (PG), `scripts/ci-select.mjs` with
  `.github/ci-filters.yml` (DD). A step-level selection keeps the required
  check reporting on every pull request; a workflow-level `paths:` filter on a
  required check leaves it pending forever.

| Repository | Required contexts | Status |
| --- | --- | --- |
| DD | `Checks`, `Release Projection` | `gate` |
| CA | `Checks`, `Release Projection` | `gate` |
| PG | `Checks`, `Release Projection` | `gate` |
| CMWB | `Checks`, `Release Projection` | `gate` |
| PRA | `Checks`, `Release Projection` | `gate` |

### QC-PR-TITLE — Conventional Commits title

A pull request title is a Conventional Commit whose type is in the
`conventional-changelog-conventionalcommits` list, so the squash commit that
release-please parses carries a valid type.

- `amannn/action-semantic-pull-request`, with the twelve types written out.
  The action's own default is the Angular list, which omits `feature`.
- Status: `gate` in all five repositories.

### QC-RELEASE-PROJECTION — release impact on the pull request

Each pull request states, before merge, which release tags its merge will
cut.

- `jmcvetta/projected-releases-action`, as a sticky comment.
- Status: `gate` in DD, CA, PG and CMWB (inside the `Release Projection` job);
  `gate` in PRA, which runs its own action.

### QC-RELEASE-CONFIG — release configuration is valid

The release-please configuration validates against the upstream schema.

- `uvx check-jsonschema` with release-please's `schemas/config.json`.
- Status: `gate` in CA (`make check-release-config`); `local` in PG (a
  documented command); `none` in DD, PRA and CMWB.

### QC-CONVENTION-RULES — conventions as executable rules

A repository convention that a pattern or a script can detect is a check
with fixtures, not only a sentence in a document.

| Implementation | Repository | Status |
| --- | --- | --- |
| Opengrep rules with fixtures in `.opengrep/rules/` (for example no `npx`, no `git add -A`, no `terraform_remote_state`) | PG | `gate` |
| Repository checks under `scripts/` (for example `check-step-names.py`, `check-manifests.py`, `check-labels.py`, `check-release-paths.py`, and `check-constitution.py`) | DD | `gate` |
| Boundary sweep and Nx-input lint (`make test-python-boundary`, `make test-python-nx-inputs`) | CA | `gate` |

### QC-SAST — static analysis for defects and security

Source code is scanned for known bug and vulnerability patterns by a pinned
rule set.

| Implementation | Repository | Status |
| --- | --- | --- |
| Opengrep, pinned engine (`.opengrep-version`, cosign-verified) and pinned community corpus (`.opengrep/community-rules.pin`), with each excluded rule given a reason in `.opengrep/excluded-rules.txt` | PG | `gate` |
| Ruff `S` rules (Python only; see `QC-LINT`) | CA | `gate` |

`none` in DD, PRA and CMWB.

### QC-GENERATED-FRESH — generated files match their source

A committed file that a tool generates is regenerated in CI, and any
difference fails the check.

| Implementation | Repository | Status |
| --- | --- | --- |
| `npm run build`, then `git diff --quiet -- dist` (bundled action) | PRA | `gate` |
| `terramate generate`, then `git diff --exit-code` (`make -C infra check-generated-code`) | PG | `gate` |
| `scripts/evals-render-results.py` rewrites the committed `evals/RESULTS.md`; there is no freshness check | DD | `none` |
| The `Measured routes` table that `scripts/evals-render-routes.py` writes into `skills/issue-body/references/omp.md` has no freshness check | DD | `none` |
| `cflow/src/artifact.test.ts` byte-compares the committed workflow artifact with a fresh build, in the TypeScript suite that runs only locally | CA | `local` |

### QC-SUPPLY-CHAIN — controlled installation

Dependencies and tools install from pinned, verified sources, and install-time
code runs only where it is named.

| Implementation | Repository | Status |
| --- | --- | --- |
| pnpm `allowBuilds` (install scripts deny-by-default) and `minimumReleaseAge` (24-hour cooldown) in `pnpm-workspace.yaml` | PG | `gate` |
| CI tool downloads verified by checksum or signature (Worktrunk SHA-256 in DD, CA, PG and CMWB; Opengrep cosign in PG) | DD, CA, PG, CMWB | `gate` |

### QC-DEPENDENCY-UPDATES — automated update pull requests

A bot opens a pull request when a pinned dependency has a new version, and
the normal CI gate checks it.

| Repository | Dependabot ecosystems |
| --- | --- |
| DD | `github-actions`, `terraform`; not `npm`, although `package-lock.json` pins the CI-selector dependencies |
| CA | `github-actions` |
| PRA | `npm`, `github-actions` |
| PG | none |
| CMWB | none |

### QC-TESTS-OFFLINE — tests do not touch the network

A test runs against fixtures, never against a live service.

- `conftest.py` at the CA repository root fails a test that opens a network
  connection. Status: `gate` in CA.
- Elsewhere the rule is the constitution's, and no tool enforces it. Status:
  `none`.


## Ecosystem controls

### QC-FORMAT — one canonical format

Source is in the formatter's canonical form; the check fails on any
difference and never rewrites in CI.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript / JavaScript / JSON | Biome (`biome check`, formatter half) | PG | `gate` |
| Python | Black, zero configuration (`black --check`) | CA | `gate` |
| Ruby | StandardRB | PG | `gate` |
| OpenTofu / HCL | `tofu fmt -check -recursive` | DD, CA, PG, CMWB | `gate` |
| OpenTofu / HCL | `tofu fmt -check -recursive` | PRA | `gate` |
| Terramate | `terramate fmt --check` | PG | `gate` |
| Shell | — | — | `none` |

### QC-LINT — language linter

Source passes the ecosystem's linter at its recommended rule set or
stricter.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript / JavaScript | Biome, `recommended` preset | PG | `gate` |
| Python | Ruff: `E F W I B UP ANN S N SIM RUF`, plus the complexity and docstring rules below | CA | `gate` |
| Ruby | StandardRB | PG | `gate` |
| Shell | ShellCheck (`shellcheck -x`) | DD | `gate` |
| OpenTofu / HCL | TFLint (`make -C infra tflint`, `infra/.tflint.hcl`) | PG | `local` |
| GitHub Actions | actionlint, on `ci.yml`, in the Paseo leg only | PG | `gate` (partial) |
| Ansible | ansible-lint, pinned | PG (`apps/omp-web`) | `gate` |
| Claude Code plugin | `claude plugin validate --strict` on the plugin, skills and agents | DD | `gate` |

### QC-TYPECHECK — strict static types

Code type-checks in the strictest standard mode, and test code is checked
too.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript | `tsc --noEmit`, `strict: true`; only `packages/gold-prices` has a separate test tsconfig | PG | `gate` |
| TypeScript | `tsc --noEmit` plus `tsc -p tsconfig.test.json` | PRA | `gate` |
| JavaScript (repository scripts) | — | DD | `none` |
| Python | pyright, `typeCheckingMode = "strict"` | CA | `gate` |
| Python (repository scripts) | — | DD | `none` |

### QC-COMPLEXITY — bounded function complexity

No function exceeds the complexity thresholds of the linter's defaults.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | Ruff `C901`, `PLR0911`, `PLR0912`, `PLR0915` at default thresholds | CA | `gate` |
| TypeScript | Biome `complexity/noExcessiveCognitiveComplexity` exists, but the `recommended` preset does not enable it | — | `none` |

### QC-FILE-SIZE — bounded file length

No production source file exceeds a counted-line limit.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | `kokoro/core/scripts/check_file_size.py`: 500 lines, not counting docstrings, comments or blank lines | CA | `gate` |
| TypeScript | — | — | `none` |

### QC-MODULE-BOUNDARIES — enforced dependency direction

Imports between packages follow a declared dependency graph, and an
undeclared import fails.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | tach (`kokoro/tach.toml`) | CA | `gate` |
| TypeScript | — (no hoisting in pnpm limits imports to declared dependencies, but no tool checks the graph) | PG | `none` |

### QC-DOC-COMMENTS — documented public symbols

Every public symbol carries a doc comment, and every test says which fault it
catches.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | Ruff `D101`, `D102`, `D103` (presence only; tests included) | CA | `gate` |
| Every other ecosystem | — (the constitution's rule, checked by review) | — | `none` |

### QC-UNIT-TESTS — automated tests

Application code has committed tests that assert and run in CI.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript | vitest | PG | `gate` |
| TypeScript | vitest | PRA | `gate` |
| Python | pytest, with pytest-impacted selection and pytest-xdist | CA | `gate` |
| Python | pytest (`tests/test_git_sync.py`) | CMWB | `gate` |
| Python | `unittest` (`apps/omp-web/scripts`) | PG | `gate` |
| Python / shell | No automated unit-test suite; `make check` runs product and convention checks | DD | `none` |
| OpenTofu | `tofu test` for each module with a `tests/` directory | PG | `gate` |

### QC-COVERAGE — measured test coverage

Coverage is measured on CI runs, and a regression is visible on the pull
request or fails it.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | pytest-cov with branch coverage; per-package line and branch floors in `kokoro/coverage-baseline.json`, enforced on full runs | CA | `gate` |
| TypeScript | vitest v8 coverage, with a diff-aware sticky comment (`davelosert/vitest-coverage-report-action`); no threshold | PRA | `gate` |
| TypeScript | — | PG | `none` |

### QC-MUTATION — test strength

Tests kill the mutants that a mutation tester generates.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript | Stryker, `thresholds.break` at the achieved score (100) | PG | `local` |

The CI machinery stays in PG, but no real project is registered in
`.github/mutation-projects.json`. Run it by hand with `make mutation_test`.

### QC-LOCKFILE — reproducible dependency resolution

The lockfile agrees with the manifests, and CI installs from it without
changing it.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript (pnpm) | `pnpm install --frozen-lockfile` | PG | `gate` |
| TypeScript (npm) | `npm ci` | PRA | `gate` |
| JavaScript (npm) | `npm ci` (CI-selector dependencies) | DD | `gate` |
| Python (uv) | `uv lock --check --offline` | CA | `gate` |
| OpenTofu providers | `tofu init`, then `git diff --quiet` on `.terraform.lock.hcl` | DD | `gate` |
| OpenTofu providers | the same | PRA | `gate` |
| OpenTofu providers | — | CA, PG, CMWB | `none` |

### QC-VULN-AUDIT — known-vulnerable dependencies

Locked dependencies are checked against an advisory database, and a finding
fails the check.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | pip-audit over the `uv export` of the lockfile | CA | `gate` |
| TypeScript (pnpm) | — | PG | `none` |
| TypeScript (npm) | — (`npm ci`'s built-in audit always exits zero, and PRA turns it off) | PRA, DD | `none` |

### QC-BUILD — the shipped artifact builds and loads

The artifact that ships is built in CI, and where it can be run offline, it is
started.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| TypeScript | package `build` (`tsc`, `astro build`) inside each package's `make test` | PG | `gate` |
| TypeScript (bundled action) | esbuild bundle, then `node dist/index.mjs` must reach its own input checks | PRA | `gate` |
| Containers | image build plus a verification script (`apps/omp-web`, `apps/paseo`) | PG | `gate` |

### QC-IAC-VALIDATE — infrastructure configuration is valid

Every OpenTofu configuration initialises without a backend and validates,
including configurations applied by hand.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| OpenTofu | `tofu init -backend=false && tofu validate` on `infra/github` | DD, CA, CMWB | `gate` |
| OpenTofu | the same | PRA | `gate` |
| OpenTofu | the same on every hand-applied configuration (`make check-manual-validate`) | PG | `gate` |
| OpenTofu | offline `tofu plan` with fixture credentials (`apps/omp-web`) | PG | `gate` |

### QC-IAC-POLICY — infrastructure policy scan

Infrastructure code passes a policy scanner, and each skipped check carries
a reason.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| OpenTofu | Checkov, `.checkov.yaml` (skips carry a comment; an Opengrep rule enforces that) | PG | `gate` |
| OpenTofu, Dockerfile, secrets | Checkov, pinned, frameworks `terraform dockerfile secrets` (`apps/omp-web`) | PG | `gate` |
| OpenTofu | — | DD, CA, PRA, CMWB | `none` |


## Adoption matrix

`gate`, `local` and `none` as above. Two more values appear in the
matrix only:

- `on` means a bot is configured (`QC-DEPENDENCY-UPDATES` is not a check).
- `n/a` means the control has nothing to act on in that repository: the
  ecosystem is absent, nothing is built, the code is a single package (so
  there is no boundary between packages to enforce), or there are no
  third-party dependencies.

A qualifier in parentheses names the part of the repository that the
control covers.

| Control | DD | CA | PG | PRA | CMWB |
| --- | --- | --- | --- | --- | --- |
| QC-REQUIRED-CHECKS | gate | gate | gate | gate | gate |
| QC-PR-TITLE | gate | gate | gate | gate | gate |
| QC-RELEASE-PROJECTION | gate | gate | gate | gate | gate |
| QC-RELEASE-CONFIG | none | gate | local | none | none |
| QC-CONVENTION-RULES | gate | gate | gate | none | none |
| QC-SAST | none | gate (Python) | gate | none | none |
| QC-GENERATED-FRESH | none | local (TypeScript) | gate | gate | none |
| QC-SUPPLY-CHAIN | gate (partial) | gate (partial) | gate | none | gate (partial) |
| QC-DEPENDENCY-UPDATES | on | on | none | on | none |
| QC-TESTS-OFFLINE | none | gate | none | none | none |
| QC-FORMAT | gate (HCL) | gate | gate | gate (HCL) | gate (HCL) |
| QC-LINT | gate (shell, plugin) | gate (Python) | gate | none | none |
| QC-TYPECHECK | none | gate (Python) | gate | gate | none |
| QC-COMPLEXITY | none | gate (Python) | none | none | none |
| QC-FILE-SIZE | none | gate (Python) | none | none | none |
| QC-MODULE-BOUNDARIES | n/a | gate (Python) | none | n/a | n/a |
| QC-DOC-COMMENTS | none | gate (Python) | none | none | none |
| QC-UNIT-TESTS | none | gate | gate | gate | gate |
| QC-COVERAGE | none | gate (Python) | none | gate | none |
| QC-MUTATION | none | none | local | none | none |
| QC-LOCKFILE | gate (npm, HCL) | gate (Python) | gate (pnpm) | gate | none |
| QC-VULN-AUDIT | none | gate (Python) | none | none | n/a |
| QC-BUILD | n/a | none | gate | gate | n/a |
| QC-IAC-VALIDATE | gate | gate | gate | gate | gate |
| QC-IAC-POLICY | none | none | gate | none | none |

CA also holds a TypeScript tree (`agent-cli`, `core`, `cflow`, `viewer`,
`polite-pace`). Its vitest and `tsc` legs run only locally (`make
test-current`), because that code is aborted. This matrix reports CA's
Python workspace and repository tooling; a cell that refers to the
TypeScript tree says `(TypeScript)`.


## Candidates to explore

These tools were recommended but are not in use. They are **not** part of
this standard. Each needs an evaluation before it can become a control.

| Tool | What it is | Control it would implement | What is not yet known |
| --- | --- | --- | --- |
| [knip](https://knip.dev/) | Finds unused files, exports and dependencies in JavaScript and TypeScript projects. | A new control for dead code and unused dependencies; no current control covers it. | Its behaviour on the pnpm workspaces in PG and on PRA's bundled action. |
| [jscpd](https://github.com/kucherenko/jscpd) | Detects copy-pasted code blocks across many languages. | A new control for duplicated code; it is multi-language, so one tool could serve several ecosystem rows. | A threshold, and how it treats fixtures and generated files. |
| archlint | Unclear. Several unrelated tools use this name or a close variant (for .NET, Go, Dart and a Tree-sitter variant), and the one recommended has not been identified. | Probably `QC-MODULE-BOUNDARIES` for an ecosystem with a `none` row, such as TypeScript. | Which project was meant. Identify it before evaluating it. |

Two tools in the baseline also have room to grow: TFLint (`local` in PG) and
actionlint (one workflow in PG). Making either a `gate` is a change to this
standard, not an evaluation of a new tool.


## Changing this standard

Change it through a pull request against this repository. A pull request that
adds or changes a control in a surveyed repository updates the control's
implementation table and the adoption matrix in the same change.
