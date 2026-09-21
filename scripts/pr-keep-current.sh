#!/bin/sh
# Keep a pull request current with its base branch, unattended.
#
# Usage: pr-keep-current.sh <pull-request-number>
#
# Runs until one of its exits, one tick every two minutes. Each tick reads
# the pull request's state, merge status, and check rollup through `gh`;
# skips the tick while a run on the head is in flight; and otherwise merges
# the base branch in server-side with `gh pr update-branch`. The only write
# this script ever performs is that one call: it never checks out a
# worktree, never rebases, and never judges a review.
#
# Exits 0 when the pull request is merged or closed, 3 on a merge conflict
# (the call fails and changes nothing; the conflict stop is the session's),
# and 2 after thirty consecutive failed reads — a watch polling a repository
# it cannot read is noise, not a watch.
#
# `gh` resolves the repository from its working directory, so run this with
# its working directory set to any checkout of the repository the pull
# request lives in. `SKILL.md`'s `Keep it current` states the rules; this
# script is the Omp route's actor.

set -u

PR="${1:?usage: pr-keep-current.sh <pull-request-number>}"
INTERVAL="${KEEP_CURRENT_INTERVAL:-120}"
MAX_READ_FAILURES=30

failures=0

while :; do
    if pr_state=$(gh pr view "$PR" --json state --jq '.state') &&
        merge_state=$(gh pr view "$PR" --json mergeStateStatus --jq '.mergeStateStatus') &&
        in_flight=$(gh pr view "$PR" --json statusCheckRollup --jq \
            '[.statusCheckRollup[]? | select(.status == "PENDING" or .status == "IN_PROGRESS" or .status == "QUEUED" or .state == "PENDING")] | length'); then
        failures=0
    else
        failures=$((failures + 1))
        echo "pr-keep-current: read failed ($failures/$MAX_READ_FAILURES); retrying next tick"
        if [ "$failures" -ge "$MAX_READ_FAILURES" ]; then
            echo "pr-keep-current: giving up after $MAX_READ_FAILURES consecutive failed reads" >&2
            exit 2
        fi
        sleep "$INTERVAL"
        continue
    fi

    case "$pr_state" in
        MERGED | CLOSED)
            echo "pr-keep-current: pull request $PR is $pr_state; watch ends"
            exit 0
            ;;
    esac

    case "$merge_state" in
        DIRTY)
            echo "pr-keep-current: pull request $PR conflicts with its base; watch ends for the conflict stop" >&2
            exit 3
            ;;
    esac

    if [ "$in_flight" -gt 0 ]; then
        echo "pr-keep-current: run in flight on the head; floor holds this tick"
        sleep "$INTERVAL"
        continue
    fi

    if [ "$merge_state" = "BEHIND" ]; then
        echo "pr-keep-current: behind its base; merging the base branch in"
        if ! gh pr update-branch "$PR"; then
            echo "pr-keep-current: update-branch failed; retrying next tick"
        fi
    fi

    sleep "$INTERVAL"
done
