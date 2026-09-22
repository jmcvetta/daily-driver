# Classic branch protection on master.
#
# Deliberately classic rather than a ruleset, matching the pattern this
# configuration was modelled on. Migrating to a ruleset is a separate change
# with its own plan.
#
# The required checks are the CI aggregate, the PR title validation, and the
# release projection. The latter two are separate workflows because each
# checks a merge input rather than a CI area; both report on every applicable
# pull-request head, and release-please pull requests intentionally report
# `preview` as skipped, which GitHub treats as successful for protection.
#
# Adding a job to CI still does not require touching this file unless it is a
# merge gate. The contract for each gate is its job name, not its workflow.
#
# Three settings are deliberately loose for a solo repository: zero required
# approving reviews, since requiring one would block every PR;
# `enforce_admins = false`, which leaves an escape hatch when CI itself is
# what is broken; and `strict = false`, since requiring a branch to be up to
# date re-invalidates every open PR each time another merges — a rebase tax
# paid most often by the long-lived release-please PR, in exchange for little
# on a repository where PRs rarely conflict.
resource "github_branch_protection" "master" {
  repository_id = github_repository.this.node_id
  pattern       = "master"

  required_status_checks {
    strict   = false
    contexts = ["CI Success", "validate-title", "preview"]
  }

  required_pull_request_reviews {
    required_approving_review_count = 0
    dismiss_stale_reviews           = false
    require_code_owner_reviews      = false
    require_last_push_approval      = false
  }

  required_linear_history         = true
  require_conversation_resolution = true
  allows_force_pushes             = false
  allows_deletions                = false
  enforce_admins                  = false
  lock_branch                     = false
}
