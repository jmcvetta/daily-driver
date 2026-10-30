#!/usr/bin/env bash
set -euo pipefail
case_id="${1:?case id required}"
python3 .fixture/bootstrap.py "$case_id" .case/case.json
base=$(awk -F= '$1 == "base" {print $2}' .review-commits)
review=$(awk -F= '$1 == "review" {print $2}' .review-commits)
current=$(awk -F= '$1 == "current" {print $2}' .review-commits)
git diff "$base...$review" >.review-diff
git diff "$base...$current" >.review-current-diff
git diff "$review...$current" >.review-delta
rm -rf -- .fixture .case
