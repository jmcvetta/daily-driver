# GitHub Repository Configuration

Manages the configuration of the `jmcvetta/daily-driver` repository
itself: merge strategy, branch protection, Dependabot alerts, and the issue
labels.

Modelled on `Green-Pagoda/pagoda`'s `infra/bootstrap/bootstrap-github`, minus
the parts that are specific to that monorepo.

## Depends On

Nothing. The repository must already exist — it is the thing this checkout
lives in.

## Why Local State

Same chicken-and-egg property as any bootstrap phase: the configuration that
protects `master` and defines the required status check cannot depend on CI
running inside that repository, or on remote state that does not exist yet.

State is local and committed to Git. It holds repository settings and branch
rules — all of it readable by anyone with repo access, and no secrets, by the
exclusion below.

## Resources Created

- **`github_repository`** — merge settings, visibility, feature toggles
- **`github_repository_vulnerability_alerts`** — Dependabot alerts
- **`github_workflow_repository_permissions`** — the default workflow token
  scope, and whether Actions may open a pull request (the release job's
  default-token fallback needs the latter)
- **`github_branch_protection`** on `master` — required `CI Success`,
  `validate-title`, and `preview` checks, linear history, conversation
  resolution, no force pushes or deletions
- **`github_issue_label`** ×7 — six issue kinds plus the `story` supplemental
  marker. The `issue-labels` skill defines their contract.

## Required Checks

Branch protection requires three status checks: `CI Success`, which aggregates
the repository's CI jobs; `validate-title`, which checks the Conventional
Commit pull-request title release-please consumes; and `preview`, which shows
what release-please will ship. Each check reports on applicable pull-request
heads, and release-please pull requests intentionally skip `preview`; GitHub
treats that skipped result as successful for branch protection.

Adding a CI job is therefore a change to the workflow, not to this
configuration, unless the job is a merge gate. The Tofu binds to each job
name, so jobs can be added under `CI Success`'s `needs` without touching
`branch_protection.tf`.

`ci.yml` carries no `paths:` filter, and must not grow one. A path-filtered
workflow does not report a *skipped* check, it reports nothing at all, so a
required context naming a filtered job leaves every unmatched pull request
pending forever. `infra.yml` is filtered precisely because it is not required;
requiring it later means dropping its filter in the same commit, and nothing
enforces that.

Three consequences worth knowing:

- A pull request whose branch predates a workflow will not report its check at
  all, and must pick up `master` before it can merge. Nothing forces that:
  `strict = false`, for the reason `branch_protection.tf` gives — requiring
  every branch to be up to date re-invalidates every open pull request each
  time another merges.
- `enforce_admins = false` leaves an escape hatch for the case where CI
  itself is what is broken.
- **The release pull request no longer needs that escape hatch.**
  `release-please.yml` authenticates as a GitHub App, which is a distinct
  identity, so the required checks report on the release pull request like any
  other. It did need the hatch while the release job ran on the default token:
  before 2026-06-11 GitHub created no workflow runs at all for
  `github-actions[bot]` pull requests, so checks sat "expected" indefinitely.
  Since that date the runs are created but held in `action_required` until
  someone with write access clicks **Approve workflows to run**.

## The Release Job's Fallback Depends on a Workflow Permission

The release job authenticates as an App and does not take this path. Its
fallback to `github.token` — reached by clearing `RELEASE_BOT_APP_ID`, which
is the one setting the App step is gated on — works only while **Settings ->
Actions -> General -> Allow GitHub Actions to create and approve pull
requests** is on. With it off,
release-please does all its work, pushes its release branch, and then fails on
the last call:

```
release-please failed: GitHub Actions is not permitted to create or approve
pull requests.
```

The branch it pushed stays behind, so the failure looks like a partial
success — which is how the first Release Please run on this repository
actually ended.

So `can_approve_pull_request_reviews` is declared, in `repository.tf`. It was
briefly argued here that it should not be, on the grounds that the release bot
App is the real fix and a Tofu-managed permission would only prop up the
fallback the App replaces. Half of that has since come true: the App is
configured, and the release job no longer depends on this permission. The
declaration stays anyway, because the other half was wrong then and is wrong
now — a setting the release job falls back on belongs written down next to the
reason it is needed, whether or not something better exists.

## The Provider Lock Has To Be What `init` Produces

`.terraform.lock.hcl` is committed, and `.github/workflows/infra.yml` fails a
pull request whose lock file `tofu init` would rewrite. That is stricter than
it sounds: initialising against the registry records an `h1:` hash for every
platform the provider publishes, so a lock file carrying fewer of them is
rewritten on the next init, on any machine. A file that init rewrites is not a
pin anyone reads — the diff appears, nobody asked for it, and it gets
committed unread.

So when the provider version changes, let init write the file and commit what
it wrote:

```bash
cd infra/github
tofu init -backend=false
git diff -- .terraform.lock.hcl
```

`.opentofu-version` pins the toolchain the same way, and is read by both a
version manager (`tenv`, `asdf`, `mise`) on a laptop and by
`opentofu/setup-opentofu` in CI, so both install the same OpenTofu from the
same file.

## The Issue Labels

`labels.tf` declares six issue kinds plus the supplemental `story` marker from
`skills/issue-labels/SKILL.md`. The kinds decide agent readiness. The marker
only makes a confirmed direct child of an epic visible in issue lists; it
never replaces its kind or its parent edge. The skill is the standard; this is
where all seven labels are declared.

Two properties are worth knowing before an apply:

- **Nothing is deleted.** Tofu owns only what it declares, so GitHub's stock
  labels (`enhancement`, `documentation`, and the rest) and the bot-owned ones
  (`dependencies`, `autorelease: pending`) survive untouched. That is
  deliberate: the standard governs what a skill applies to an issue, and
  claims no more of the namespace than that.
- **Pre-existing labels must be imported.** Every repository GitHub creates
  ships with `bug`, and creating an existing label fails rather than adopting
  it. `import.sh` carries `bug`. If `story` was created before this managed
  apply, import it with `tofu import 'github_issue_label.story'
  'daily-driver:story'` before planning.

The description strings are duplicated in the skill's tables, and
`scripts/check-labels.py` fails `make check` when they drift. That check is a
leg of `check` rather than of `check-infra`: it needs only Python, so a laptop
editing a skill runs it without OpenTofu installed.

After the human applies this stack, that person runs one backfill for existing
open stories. For each open issue, read its native direct parent and the
parent's labels. Add only `story` when the parent is confirmed and carries
`epic`; preserve every existing label. Do not infer a parent from issue text or
add a marker after a failed graph read. This rollout step waits on the same
human who applies the Tofu stack.

## Renaming the Repository

`local.repository` in `main.tf` is the repository's name, so a rename is an
edit there and an apply. The repository renames in place — `name` is not
`ForceNew`, and `Update` re-reads the id from the response — and branch
protection binds to the repository's `node_id`, which a rename does not
change. GitHub redirects the old path, so clones, links and open pull
requests keep working.

The labels do not rename in place. `github_issue_label` takes the repository
by *name* and marks that field `ForceNew`, and its `Read` never writes the
name back, so a refresh cannot reconcile it. The plan for a rename — measured
with provider 6.13.0 against this stack's committed state — is:

```
# github_issue_label.epic must be replaced
-/+ resource "github_issue_label" "epic" {
      ~ repository = "claude-daily-driver" -> "daily-driver" # forces replacement
```

for all seven labels, plus `github_repository_vulnerability_alerts`, which
holds nothing worth keeping. A destroyed label is stripped from every issue
carrying it, and creating it again does not put it back.

That replacement used to be harmless, which is why a rename may be remembered
as uneventful. Through provider 6.12 the label's `Create` looked the label up
first and *edited* it if it existed — the published docs still say so — so a
destroy that quietly failed to delete was papered over by a create that
quietly updated. From 6.13.0 `Create` is a bare `CreateLabel`, and the
fallback is gone: on this provider the apply either deletes the labels for
real, or fails with `already_exists` after dropping them from state.

So move the labels in state instead of letting the plan replace them:

```bash
cd infra/github
export GITHUB_TOKEN=$(gh auth token)

tofu apply -target=github_repository.this               # the rename, alone

for label in epic story task bug proposal research human; do
	tofu state rm "github_issue_label.${label//-/_}"
	tofu import "github_issue_label.${label//-/_}" "daily-driver:$label"
done

tofu plan                                               # expect: alerts replaced, nothing else
tofu apply
```

Commit `terraform.tfstate` afterwards, as with any other apply.

## Deliberate Exclusions

**Actions secrets.** The provider writes secret values into state, and this
state is committed. Set them by hand and leave them there.

**`RELEASE_BOT_APP_ID` and `RELEASE_BOT_PRIVATE_KEY`.** The variable would be
manageable here — it holds no secret — and is deliberately left out anyway.
`release-please.yml` switches to the App the moment the variable is set, so
setting it while the private key is missing or the App is not installed makes
the release job fail on its first step, which is worse than the fallback it
replaces. Both go in together, by hand, alongside installing the App — which
is how the `daily-driver-release-bot` App now serving this repository was set
up.

**Environments.** Nothing deploys from this repository.

## Prerequisites

A GitHub token with admin rights on the repository, exported as
`GITHUB_TOKEN`. A `gh` login with the `repo` scope suffices:

```bash
export GITHUB_TOKEN=$(gh auth token)
```

## Checking a Change Before Applying It

`tofu apply` is the first thing that parses these files, and it runs against
live branch protection — a bad moment to discover a typo. `make check-infra`,
from the repository root, moves that discovery earlier:

```bash
make check-infra
```

It runs `tofu fmt -check`, then `tofu init -backend=false`, then `tofu
validate`. The `-backend=false` is what keeps it credential-free: providers
are installed for validation, and neither state nor the GitHub API is touched.
`.github/workflows/infra.yml` runs it on every pull request that touches this
directory, so a syntax error or an attribute the provider does not have fails
in review.

It is not part of `make check`, which is what a laptop runs while editing a
skill and which must not start requiring OpenTofu to be installed.

This is not a substitute for reading `tofu plan` before an apply. Validation
knows the configuration is well-formed; only the plan knows what it will do.

## Usage

```bash
cd infra/github
export GITHUB_TOKEN=$(gh auth token)
tofu init
./import.sh   # adopts the pre-existing repository
tofu plan
tofu apply
```

The repository already exists, so it is **imported** rather than created — a
greenfield apply would try to create a repository that is already there.
Everything else is genuinely new, so the first plan reports changes rather
than the "No changes." a fully-imported stack would:

- `github_repository.this` updated in place — squash-only merges, PR title
  and body as the commit subject and message, branch deletion on merge, auto
  merge enabled
- `github_repository_vulnerability_alerts.this` created
- `github_workflow_repository_permissions.this` created
- `github_branch_protection.master` created
- `github_issue_label.bug` updated in place — the description replaced with the
  standard's — and the six other labels created

After applying, commit `terraform.tfstate` to Git.
