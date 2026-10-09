# Classic branch protection on master.
#
# Deliberately classic rather than a ruleset, matching the pattern this
# configuration was modelled on. Migrating to a ruleset is a separate change
# with its own plan.
#
# The required checks are `Checks`, the one CI validation job, and Release
# Projection. The latter validates the title release-please consumes, then projects the release
# from the same runner. It reports on every pull-request head; release-please
# pull requests skip only projection, leaving title validation as the gate.
#
# Adding a CI step still does not require touching this file unless it is a
# merge gate. The contract for each gate is its job name, not its workflow.
#
# Two settings are deliberately loose for a solo repository: zero required
# approving reviews, since requiring one would block every PR, and
# `enforce_admins = false`, which leaves an escape hatch when CI itself is
# what is broken.
#
# `strict = true` makes every branch meet the same gate as the base it will
# merge into: a branch that is behind is blocked until it is updated and the
# required checks run again on the result.
#
# The contexts are job display names. Renaming a job needs this file applied in
# step with the workflow change, or pull requests wait on a check nothing
# reports.
resource "github_branch_protection" "master" {
  repository_id = github_repository.this.node_id
  pattern       = "master"

  required_status_checks {
    strict   = true
    contexts = ["Checks", "Release Projection"]
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
