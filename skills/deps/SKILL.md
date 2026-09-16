---
name: deps
description: >-
  This skill should be used whenever a repository's dependencies are being
  upgraded in bulk, or whenever open Dependabot pull requests are the thing to
  answer — including when the user says "/deps", "dependabot is complaining",
  "upgrade the deps", "these dependency PRs are piling up", or "bump
  everything". Noticing open Dependabot pull requests during other work is
  worth a line to the user and is not itself a trigger: a bulk upgrade started
  mid-task is scope nobody asked for. Supplies the one-branch bulk upgrade,
  the bulk command each manager already has, green CI as the whole acceptance
  test, and the boundary an unattended run stays inside — no merge, no code
  edited around a breaking change, and nothing outside the pull request it
  opens. Not for a single
  named dependency, which is ordinary work, and not for a major version bump,
  which this skill reports and hands to `undertake`.
---

# Bulk dependency upgrade

Dependabot files one pull request per dependency: a branch each, a CI run
each, a review each. This skill does the opposite. **One branch carries every
upgrade, and one CI run says whether the result holds together.**

The upgrades themselves are the package manager's work, never a hand-edited
manifest or lockfile. That rule is the constitution's, under `Dependencies`,
and it is not restated here.

**The routes are per harness, and they live beside this file.** Every
operation below is named in words here and resolved to a call there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi,
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before the first search or write call.


Green CI is the acceptance test
===============================

**If the tests pass, the upgrade worked.** That is the whole gate.

The suite is the only thing that can say whether a new version broke
something; reading a lockfile diff by eye says nothing. So this skill runs no
review round and is not `undertake` work — a review of a lockfile spends quota
for no finding. It opens the pull request through `pr` and waits on CI.

A red suite is the upgrade talking. It is answered by finding which upgrade
broke what, and never by pinning around the failure, skipping the test, or
silencing it — the constitution's *Fix problems, do not hide them*.


The run is unattended
=====================

Nobody is watching, so the boundary is the substance of the skill. Inside a
run:

- **Never merge.** The pull request is the end of the run.
- **Never edit code to accommodate a breaking change.** See `Majors are not in
  the pass` below.
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

**Read what is behind from the open Dependabot pull requests**, rather than
guessing at it from the manifest. A search for open pull requests authored
by Dependabot is the list, and each title names the dependency and the
version it wants — not a plain listing of pull requests, which cannot
filter by author, and not the manifest. The reference file for the harness
in use names the exact search call, and the trap in reaching for the wrong
one instead.

**Upgrade every ecosystem the repository declares, on one branch.** One CI run
over the whole upgrade is the point. `.github/dependabot.yml` says which
ecosystems a repository declares, and the **lockfile in the tree** says which
manager owns each one. Read the second before running anything: Dependabot's
`npm` ecosystem covers pnpm, yarn and bun, and its `pip` ecosystem covers
Poetry, Pipenv and uv, so the ecosystem name alone picks the wrong command
about as often as the right one. A `pnpm-lock.yaml` answered with
`npm update` writes a stray `package-lock.json` and upgrades nothing.

The command is whatever that manager calls its bulk upgrade:

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

**The table is a convenience, not the rule.** The rule is *the manager that
wrote the lockfile is the manager that updates it*, and a manager missing from
the table is looked up in its own manual rather than guessed at — the
constitution's *RTFM*. Maven, Gradle and Docker are the common ones absent
here.

Some ecosystems have no package manager to run at all. A GitHub Actions pin
and a Terraform provider lock are moved by editing the pin and re-locking with
the project's own tooling — `tofu init -upgrade` and its kind — which is that
ecosystem's package manager rather than a hand edit.

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
