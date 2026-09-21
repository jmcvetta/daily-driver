# The issue labels this toolkit recognises.
#
# Six issue-kind labels answer one question -- what kind of issue is this, and
# is it ready for an agent to work unattended -- and every issue carries
# exactly one. `story` is a supplemental marker for a confirmed direct child
# of an epic. It does not answer the readiness question.
# `skills/issue-labels/SKILL.md` is the standard; this file is where it is
# declared, so names, colours and descriptions come from a file under review.
#
# The `description` strings are duplicated in that skill's table on purpose:
# the skill is what a session reads and GitHub is what a person hovers, and
# both have to say the same thing. `scripts/check-labels.py` fails `make
# check` when they drift.
#
# Tofu owns only what it declares, so an apply leaves GitHub's stock labels
# (`enhancement`, `documentation`, and the rest) and the bot-owned ones
# (`dependencies`, `autorelease: pending`) untouched. That is deliberate --
# the standard governs what a skill applies to an issue, and claims no more
# of the namespace than that.
#
# `bug` pre-exists in every repository GitHub creates, and creating a label
# that already exists fails the apply rather than adopting it. `import.sh`
# carries the import; a repository starting from a clean namespace can drop
# that line.

resource "github_issue_label" "epic" {
  repository  = github_repository.this.name
  name        = "epic"
  color       = "5319e7"
  description = "Coordinates a sequence of other issues"
}

# A lighter purple than its epic parent distinguishes a story in issue lists.
resource "github_issue_label" "story" {
  repository  = github_repository.this.name
  name        = "story"
  color       = "d4c5f9"
  description = "Direct child of an epic"
}

resource "github_issue_label" "task" {
  repository  = github_repository.this.name
  name        = "task"
  color       = "0e8a16"
  description = "Discrete work, specified and ready for an agent"
}

# Red is GitHub's own colour for this label, kept so an imported `bug` reports
# no change on the first plan beyond its description.
resource "github_issue_label" "bug" {
  repository  = github_repository.this.name
  name        = "bug"
  color       = "d73a4a"
  description = "Bug report"
}

resource "github_issue_label" "proposal" {
  repository  = github_repository.this.name
  name        = "proposal"
  color       = "1d76db"
  description = "Proposed feature"
}

resource "github_issue_label" "research" {
  repository  = github_repository.this.name
  name        = "research"
  color       = "fbca04"
  description = "A question to settle"
}

# Not a status. `human` says the work itself is a person's -- credentials no
# agent holds, a decision only the user can make, an action outside the
# repository -- and an agent that stops on one stops because of what the work
# is, not because of where it got to.
resource "github_issue_label" "human" {
  repository  = github_repository.this.name
  name        = "human"
  color       = "006b75"
  description = "Work only a person can do"
}
