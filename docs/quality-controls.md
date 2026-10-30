# Quality controls

This standard names the deterministic quality controls that our repositories
run. A deterministic control is a tool that gives the same answer on the same
input and fails loudly. It is the discipline an agent cannot talk its way past.

This version records the **decided standard** on 2026-10-29: where each
control is in use on that date, and the changes decided since the 2026-10-24
baseline. A decided change that has not landed is marked as decided (see
*How to read this standard*). A companion issue in each repository lands the
change, and its pull request removes the mark.

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
| `none` | No implementation exists for this ecosystem. |

A `none` row records a gap. It is not an error in this document.
Tests of tests and other testing machinery are not quality controls. Do not
list them as implementations of a control.

**A status is the current state, and a decided change is marked.** Where a
change is decided but has not landed, a status reads `current → decided`:
`none → gate` is a gate that is decided but not yet wired, and `gate → none`
is a gate that is decided for removal but still runs. A decided change that
is not a status change is named as decided in the control's text or table,
such as Dependabot's "Decided, not yet landed" column and CA's unpinned
release-config schema. The companion issue's pull request removes the mark.


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

The release-please configuration validates against the upstream schema, run
only when that configuration changes, against a schema pinned to a release
tag rather than `main`.

- `uvx check-jsonschema` with release-please's `schemas/config.json`, fetched
  from a release tag.
- Status: `gate` in CA (`make check-release-config`, selected only when
  `release-please-config.json` changes), but CA still fetches the schema from
  `main`, and pinning it to a tag is decided; `local` in PG (a documented
  command); `none` in DD, PRA and CMWB.

### QC-CONVENTION-RULES — repository rules as executable checks

A repository rule that a pattern or a script can detect is an executable
check with a failing test, not only a sentence in a document. Conventions are
one source of such rules; config consistency and domain invariants are
others. The rest stay review-only.

| Implementation | Repository | Status |
| --- | --- | --- |
| Opengrep rules in `.opengrep/rules/` (for example no `npx`, no `git add -A`, no `terraform_remote_state`) | PG | `gate` |
| Repository checks under `scripts/` (for example `check-step-names.py`, `check-manifests.py`, `check-labels.py`, `check-release-paths.py`, and `check-constitution.py`) | DD | `gate` |
| Candidate-boundary sweep (`make test-python-boundary`): candidate-owned values stay out of shipped sources and prose, and `CLAUDE.md`'s budget and links stay consistent | CA | `gate` |

### QC-SAST — static analysis for defects and security

Source code is scanned for known bug and vulnerability patterns. A pattern
corpus earns its place only by finding defects: PG's Opengrep community corpus
measured 215 findings and no defect on 2026-09-09, so it is retired rather
than kept as a gate.

| Implementation | Repository | Status |
| --- | --- | --- |
| Opengrep, pinned engine (`.opengrep-version`, cosign-verified) and pinned community corpus (`.opengrep/community-rules.pin`), with each excluded rule given a reason in `.opengrep/excluded-rules.txt` | PG | `gate → none` |
| Ruff `S` rules (Python only; see `QC-LINT`) | CA | `gate` |

`none` in DD, PRA and CMWB, and in PG once its corpus is retired. PG's custom
`.opengrep/rules/` stay under `QC-CONVENTION-RULES`.

### QC-WORKFLOW-SECURITY — workflows are safe against untrusted input

GitHub Actions workflows are scanned for template injection from untrusted
event fields, over-broad token permissions, dangerous triggers such as
`pull_request_target`, credentials left in the checkout, and cache poisoning.

- zizmor, promoted from the candidates list. It matters most for PRA, a
  public action that reads untrusted pull-request text with a write token.
  Each repository's adoption issue triages the first findings and sets how
  the pinning audit treats major-version tags.
- Status: `none → gate` in all five repositories (#709 in DD).

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

| Repository | Dependabot ecosystems | Decided, not yet landed |
| --- | --- | --- |
| DD | `github-actions`, `terraform` | `npm`, for the `package-lock.json` that pins the CI-selector dependencies (#707) |
| CA | `github-actions` (Python is `uv.lock`, which Dependabot has no ecosystem for) | — |
| PRA | `npm`, `github-actions` | — |
| PG | none | `github-actions` |
| CMWB | none | `github-actions`, `terraform` |

The decided standard is that every repository with pinned third-party
dependencies has Dependabot on for the matching ecosystems.

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
| TypeScript | Biome `complexity/noExcessiveCognitiveComplexity`, enabled beyond the `recommended` preset | PG | `none → gate` |

### QC-FILE-SIZE — bounded file length

No production source file exceeds a counted-line limit.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | `kokoro/core/scripts/check_file_size.py`: 500 lines, not counting docstrings, comments or blank lines | CA | `gate` |
| TypeScript | a script mirroring CA's `check_file_size.py` at 500 lines, not counting comments or blank lines (Biome has no file-length rule) | PG | `none → gate` |

### QC-MODULE-BOUNDARIES — enforced dependency direction

Imports between packages follow a declared dependency graph, and an
undeclared import fails.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | tach (`kokoro/tach.toml`) | CA | `gate` |
| TypeScript | — (pnpm no-hoisting already blocks undeclared imports; the remaining gap is cycles and direction, which dependency-cruiser may close once evaluated, see *Candidates to explore*) | PG | `none` |

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
| TypeScript | vitest v8 coverage, same diff-aware comment as PRA | PG | `none → gate` |
| Python | pytest-cov, mirroring CA without floors until a baseline exists | CMWB | `none → gate` |

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
| OpenTofu providers | `tofu init`, then `git diff --quiet` on `.terraform.lock.hcl` | DD | `gate → none` (#706) |
| OpenTofu providers | the same | PRA | `gate → none` |

OpenTofu provider lockfiles (`.terraform.lock.hcl`) stay committed for
hash-pinning when a configuration is applied by hand, but the decided
standard has no CI gate on their drift: every configuration is applied by one
operator by hand or by Spacelift with major-version-pinned providers, so the
reproducibility a drift gate buys is not worth the check. CA, PG and CMWB
already have no such gate.

### QC-VULN-AUDIT — known-vulnerable dependencies

Locked dependencies are checked against an advisory database at its latest
data, and any finding fails the check. The scan scopes to production
dependencies; dev-only advisories are not a gate. DD declares only dev
dependencies today, so its audit finds nothing until a production dependency
is added.

| Ecosystem | Tool | Repositories | Status |
| --- | --- | --- | --- |
| Python | pip-audit over the `uv export` of the lockfile | CA | `gate` |
| TypeScript (pnpm) | `pnpm audit --prod` (fails on any finding; no severity floor) | PG | `none → gate` |
| TypeScript (npm) | `npm audit --omit=dev` (fails on any finding; no severity floor) | PRA, DD | DD `gate`; PRA `none → gate` |

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
| OpenTofu | Checkov 3.2.472, `.checkov.yaml` (five skips carry reasons) | DD | `gate` |
| OpenTofu, Dockerfile, secrets | Checkov, pinned, frameworks `terraform dockerfile secrets` (`apps/omp-web`) | PG | `gate` |
| OpenTofu | Checkov, `.checkov.yaml`, selected only when Tofu changes | CA | `none → gate` |
| OpenTofu | Checkov 3.2.472, `.checkov.yaml`, selected by the infra filter | PRA | `none → gate` |
| OpenTofu | Checkov 3.2.472, `.checkov.yaml`, selected by the infra filter | CMWB | `gate` |


## Adoption matrix

`gate`, `local`, `none` and the `current → decided` arrow as above. Two
more values appear in the matrix only:

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
| QC-RELEASE-CONFIG | none | gate (schema unpinned) | local | none | none |
| QC-CONVENTION-RULES | gate | gate | gate | none | none |
| QC-SAST | none | gate (Python) | gate → none | none | none |
| QC-WORKFLOW-SECURITY | none → gate | none → gate | none → gate | none → gate | none → gate |
| QC-GENERATED-FRESH | none | local (TypeScript) | gate | gate | none |
| QC-SUPPLY-CHAIN | gate (partial) | gate (partial) | gate | none | gate (partial) |
| QC-DEPENDENCY-UPDATES | on | on | none → on | on | none → on |
| QC-TESTS-OFFLINE | none | gate | none | none | none |
| QC-FORMAT | gate (HCL) | gate | gate | gate (HCL) | gate (HCL) |
| QC-LINT | gate (shell, plugin) | gate (Python) | gate | none | none |
| QC-TYPECHECK | none | gate (Python) | gate | gate | none |
| QC-COMPLEXITY | none | gate (Python) | none → gate | none | none |
| QC-FILE-SIZE | none | gate (Python) | none → gate | none | none |
| QC-MODULE-BOUNDARIES | n/a | gate (Python) | none | n/a | n/a |
| QC-DOC-COMMENTS | none | gate (Python) | none | none | none |
| QC-UNIT-TESTS | none | gate | gate | gate | gate |
| QC-COVERAGE | none | gate (Python) | none → gate | gate | none → gate |
| QC-MUTATION | none | none | local | none | none |
| QC-LOCKFILE | gate (npm); gate → none (HCL) | gate (Python) | gate (pnpm) | gate (npm); gate → none (HCL) | none |
| QC-VULN-AUDIT | gate | gate (Python) | none → gate | none → gate | n/a |
| QC-BUILD | n/a | none | gate | gate | n/a |
| QC-IAC-VALIDATE | gate | gate | gate | gate | gate |
| QC-IAC-POLICY | gate | none → gate | gate | none → gate | gate |

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
| [dependency-cruiser](https://github.com/sverweij/dependency-cruiser) | Standalone dependency-graph validation for JavaScript and TypeScript: cycles, orphan dependencies, and declared direction rules, without ESLint. | `QC-MODULE-BOUNDARIES` for the TypeScript row. | Whether it surfaces real violations in PG beyond what pnpm no-hoisting already blocks, and what the declared boundary policy should be. |

Two tools already in use also have room to grow: TFLint (`local` in PG) and
actionlint (one workflow in PG). Making either a `gate` is a change to this
standard, not an evaluation of a new tool.


## Changing this standard

Change it through a pull request against this repository. A pull request that
adds or changes a control in a surveyed repository updates the control's
implementation table and the adoption matrix in the same change.
