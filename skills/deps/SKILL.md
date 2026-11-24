---
name: deps
description: >-
  Use for `/deps`, a bulk dependency upgrade, or open Dependabot pull requests
  as the thing to answer. Noticing those pull requests during other work is
  worth a line, not a bulk upgrade. Supplies the one-branch upgrade, the bulk
  command each manager already has, green CI as the whole acceptance test, and
  the unattended-run boundary: no merge, no code edited around a breaking
  change, nothing outside the pull request it opens. Not for a single named
  dependency, which is ordinary work, or a major version bump, which it
  reports and hands to `undertake`.
---

# Bulk dependency upgrade

Dependabot files one pull request per dependency: a branch each, a CI run
each, a review each. This skill does the opposite. **One branch carries every
upgrade, and one CI run says whether the result holds together.**

The upgrades themselves follow `provenance`'s package-manager policy, never a
hand-edited manifest or lockfile. That policy is not restated here.

**The routes are per harness, and they live beside this file.** Every
operation below is named in words here and resolved to a call there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before the first search or write call.


Green CI is the acceptance test
===============================

**Green CI is required, but it is not the whole acceptance test.** The pull
request title must also reflect whether the batch fixes a serious security
vulnerability in the shipped product. Classify the title through `pr-title`,
which routes type selection to `conventional-commits-type`; do not add a
separate review round.

For each advisory that may qualify, gather and record its identifier and link,
severity, affected dependency and versions, patched version included in the
batch, and evidence that the vulnerable dependency affects the shipped
product. Do not infer applicability from a package name or severity alone.
When evidence is insufficient, state what is unknown and do not call it a
verified security fix. A high- or critical-rated advisory is a positive case
only when its applicability and product impact are supported.

Keep `build(deps): …` for routine bulk upgrades, and preserve the existing
`test`, `build` and `ci` boundaries for changes confined to verification or
tooling. A batch that actually patches a serious vulnerability affecting the
shipped product uses `fix(security): …`, including a mixed batch of routine
upgrades and that security fix. An advisory limited to development or CI
tooling is not automatically a product fix; judge whether it changes the
safety of the shipped artifact, not just the dependency category.

`fix` is the release-relevant type; `security` is descriptive scope. The
actual release also depends on the merge commit subject, path exclusions and
other pending commits. Read *Projected Releases* when available; never promise
a patch release from the title alone. Preserve a type set by a user or
another actor: raise a disagreement and wait rather than retitling it.

**A security patch held out by the existing major-version constraint remains
unresolved.** Report the dependency and constraint. Do not call it fixed or
cross the unattended boundary to take the major upgrade.

A red suite is answered by finding which upgrade broke what, never by pinning
around the failure, skipping the test, or silencing it. Follow
[`docs/testing-standards.md`](../../docs/testing-standards.md) for the test
contract.

**A compatible tool's own migration is inside the pass.** Where the bulk
command moves a tool within its existing major constraint and the fallout is
confined to that tool's configuration schema and its formatting of existing
files — a formatter's renamed configuration key and the reformat of the files
it already owns under the new version — the run performs the tool's own
migration, applies the resulting formatting, and continues to green CI on the
current head. That is the mechanical fallout of an upgrade the run itself
asked for, not a decision a person owes: the run finishes what it moved.

**The breaking-change prohibition is about application behaviour.** "Never
edit code to accommodate a breaking change" means application code and the API
or behaviour contracts it implements — the caller changes a changed library
interface demands. A tool's configuration schema and the formatting that tool
owns are not application code, so repairing them is the migration, not a code
edit around a break. Every prohibition in `The run is unattended` still holds,
and a major upgrade still goes to `Majors are not in the pass`.



The run is unattended
=====================

Nobody is watching, so the boundary is the substance of the skill. Inside a
run:

- **Never merge.** The pull request is the end of the run.
- **Never edit application code to accommodate a breaking change.** A
  compatible tool's own configuration and format migration is not that; see
  the paragraph above. Majors are excluded — see `Majors are not in the pass`
  below.
- **Never skip, disable or pin around a failing test.**
- **Nothing outside this pull request.** No comment on anybody else's pull
  request, nothing closed, and no issue opened. Opening the pull request and
  marking it ready are the run's whole footprint on GitHub.
- **Ready is the end, and only on green.** `pr` opens a draft; the run marks
  it ready once every check has reported green, and leaves it a draft with
  the failure named when one has not. No round runs in between — see `Green
  CI is the acceptance test` — so there is nothing else for the draft to
  wait on. The reference file for the harness in use names the call that
  marks it ready.


The pass
========

**Use open Dependabot pull requests as context, not as the inventory.** Search
for them when available: their titles identify known upgrades, and their links
belong in the pull request body when this batch supersedes them. No results,
missing or disabled configuration, delayed runs, or ecosystems the bot omits
do not stop the pass.

**Discover dependencies from the repository itself.** Inspect project
configuration, manifests and lockfiles to identify every declared ecosystem
and map each lockfile to the package manager that owns it. Do not treat
Dependabot's ecosystem names as manager names: its `npm` ecosystem includes
pnpm, yarn and bun, and its `pip` ecosystem includes Poetry, Pipenv and uv.
For each identified manager, use its documented, supported outdated or
dependency-discovery operation to find eligible upgrades and existing
constraints. Read that manager's manual when its discovery or bulk-upgrade
command is not already known; never guess at a command or omit a declared
manager because Dependabot did not report it.

**Upgrade every applicable manager on one branch.** One CI run over the whole
upgrade is the point. Use the bulk-upgrade command supported by the manager
that owns each lockfile:

| Lockfile in the tree | The bulk command |
| -------------------- | ---------------- |
| `uv.lock` | `uv lock --upgrade` |
| `poetry.lock` | `poetry update` |
| `Gemfile.lock` | `bundle update` |
| `package-lock.json` | `npm update` |
| `pnpm-lock.yaml` | `pnpm update` |
| `yarn.lock` | `yarn upgrade` |
| `Cargo.lock` | `cargo update` |
| `go.sum` | `go get -u ./...`, then `go mod tidy` |
| `composer.lock` | `composer update` |
| `packages.lock.json` | `dotnet list package --outdated`, then `dotnet add package` per row |

The table is a convenience, not the rule. The manager that wrote the lockfile
is the manager that updates it. For a manager missing from the table, consult
its manual rather than guessing. Maven, Gradle and Docker are common examples.
If the repository has a managed ecosystem but no lockfile, use its project
configuration and manager documentation to establish the supported path
before changing anything.

Some managed dependencies have no package manager to run. A GitHub Actions pin
and a Terraform provider lock are updated with the project's own tooling, such
as editing the pin and running `tofu init -upgrade`; do not hand-edit a
lockfile.

**Split the branch only under duress.** Where one ecosystem goes red and holds
the rest hostage, lift it out onto its own branch so the green ones can land.
That is a recovery, not the plan.


Majors are not in the pass
==========================

The bulk pass is the safe half: everything the manager moves within the
constraints already written down, where red CI means a real regression rather
than an API that changed underneath.

A major version is a behaviour change with a changelog to read and usually
code to edit. Folded into the batch it makes the branch un-bisectable the
moment CI goes red, and it turns an unattended run into one that edits code it
cannot review.

So the pass **reports** them, in the pull request body: every dependency the
bulk command would not move, and the constraint that held it. It opens no
issue for them — an issue is an outward action, and the boundary above allows
none. Taking one is a separate, attended decision, and `undertake` opens the
issue when it is taken.


The superseded pull requests are left alone
===========================================

Dependabot notices on its own schedule that the versions have landed, and
closes what it no longer needs. This skill neither closes those pull requests
nor comments on them. The only cost is latency until Dependabot's next run.

Prodding the bot to act sooner is not available and is not worth building: the
GitHub MCP server rewrites a literal `@` mention on every write path, issue
bodies and comments alike, so a session cannot post a working Dependabot
command at all. Doing it from a workflow on merge would work, and is machinery
to maintain in exchange for a week of waiting.

The pull request body names which Dependabot pull requests it supersedes, so a
reader can see they were not overlooked.
