# The repository itself.
#
# The squash-only + PR_TITLE pairing is load-bearing, not taste. Conventional
# Commits go on PR titles rather than on individual commits, and anything that
# parses history — changelog generation, release tooling — reads commit
# subjects on master. Those cohere only because squash-merge makes the PR
# title become the master commit subject. Re-enabling merge commits would
# quietly break that.
#
# Public, because the plugin marketplace manifest is meant to be fetched by
# anyone installing the plugin.
resource "github_repository" "this" {
  name        = local.repository
  description = "Daily-driver skills for Claude Code, packaged as a plugin."
  visibility  = "public"

  has_issues   = true
  has_projects = true
  has_wiki     = true

  allow_squash_merge          = true
  allow_merge_commit          = false
  allow_rebase_merge          = false
  allow_auto_merge            = true
  allow_update_branch         = false
  delete_branch_on_merge      = true
  squash_merge_commit_title   = "PR_TITLE"
  squash_merge_commit_message = "PR_BODY"

  # Inert while merge commits are disabled, but the API reports these values,
  # so declaring them keeps the plan quiet.
  merge_commit_title   = "MERGE_MESSAGE"
  merge_commit_message = "PR_TITLE"
}

# Dependabot alerts. Its own resource rather than the repository's deprecated
# vulnerability_alerts field.
resource "github_repository_vulnerability_alerts" "this" {
  repository = github_repository.this.name
  enabled    = true
}

# Dependabot security updates: pull requests that fix vulnerable dependencies.
# They need the alerts above, so the order is explicit.
resource "github_repository_dependabot_security_updates" "this" {
  repository = github_repository.this.name
  enabled    = true

  depends_on = [github_repository_vulnerability_alerts.this]
}

# Settings -> Actions -> General -> Workflow permissions, which is the setting
# the release job actually depends on.
#
# `can_approve_pull_request_reviews` is GitHub's "Allow GitHub Actions to
# create and approve pull requests", and the create half is the one that
# matters. With it off, release-please does all its work, pushes its release
# branch, and then fails the run on the call that opens the pull request -- so
# the failure reads as a partial success and no release ever gets cut.
#
# That is not hypothetical here. It is exactly how the first Release Please
# run ended: `release-please--branches--master` pushed, no pull request on it,
# and a red run whose log says everything worked until the last call.
#
# This repository releases itself, so the switch is part of its configuration
# rather than a preference. Configuring the release bot App makes the release
# job stop depending on it, but does not make it wrong to declare.
#
# `default_workflow_permissions` stays at read. Every workflow here declares
# the scopes its jobs need, so a permissive default would only widen the token
# for a workflow that forgot to.
resource "github_workflow_repository_permissions" "this" {
  repository                       = github_repository.this.name
  default_workflow_permissions     = "read"
  can_approve_pull_request_reviews = true
}
