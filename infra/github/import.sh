#!/usr/bin/env bash
#
# Import the live GitHub configuration into local state.
#
# Only the repository itself pre-exists; branch protection and Dependabot
# alerts are created by the first apply. So unlike a fully-imported stack,
# the first `tofu plan` here reports changes — see README.md for what they
# should be.
#
# Idempotent: each import is skipped if that address is already in state, so
# this is safe to re-run after adding a resource.
#
# Usage:
#   export GITHUB_TOKEN=$(gh auth token)
#   ./import.sh

set -euo pipefail

readonly REPO="daily-driver"

# import <address> <id> — no-op if the address is already in state.
import() {
	local address="$1" id="$2"
	if tofu state list "$address" >/dev/null 2>&1 &&
		[[ -n "$(tofu state list "$address")" ]]; then
		echo "== skip $address (already in state)"
		return
	fi
	echo "== import $address"
	tofu import "$address" "$id"
}

import 'github_repository.this' "$REPO"

# `bug` ships with every repository GitHub creates, so it is adopted rather
# than created; every other label in labels.tf is new and needs no import.
# The id is `<repository>:<label name>`.
import 'github_issue_label.bug' "$REPO:bug"

echo
echo "Import complete. Verify with: tofu plan"
