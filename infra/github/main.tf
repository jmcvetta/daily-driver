# GitHub repository configuration.
#
# Encodes the settings of the jmcvetta/daily-driver repository itself:
# merge strategy and branch protection. Run with a token carrying repo admin
# rights. State is local and committed to Git.
#
# Depends on: nothing. The repository is the one thing that must already
# exist for any of this to be checked out.
#
# Actions *secrets* are deliberately absent — the provider would write their
# plaintext into this committed state. Set them by hand and leave them there.

provider "github" {
  owner = local.owner
}

locals {
  owner      = "jmcvetta"
  repository = "daily-driver"
}
