#!/bin/sh
# Keep a pull request current with its base branch, unattended.
#
# Usage: pr-keep-current.sh <pull-request-number>
#
# Each tick compares the actual pinned base and head, then revalidates before
# the server-side update. It never checks out a worktree or judges a review.
#
# Exits 0 when the pull request is merged or closed, 3 on a merge conflict
# (the call fails and changes nothing; the conflict stop is the session's),
# and 2 after thirty consecutive failed reads — a watch polling a repository
# it cannot read is noise, not a watch.
#
# `gh` resolves the repository from its working directory, so run this with
# its working directory set to any checkout of the repository the pull
# request lives in. `skills/pr/SKILL.md`'s `Keep it current` states the
# rules; this script is the Omp route's actor.

set -u

PR="${1:?usage: pr-keep-current.sh <pull-request-number>}"
INTERVAL="${KEEP_CURRENT_INTERVAL:-120}"
MAX_READ_FAILURES=30
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
pending_head=

failures=0

while :; do
    if pr_url=$(gh pr view "$PR" --json url --jq '.url') &&
        observation=$(python3 "$SCRIPT_DIR/pr-supervisor.py" currency --url "$pr_url") &&
        pr_state=$(printf '%s' "$observation" | jq -er '.state') &&
        currency=$(printf '%s' "$observation" | jq -r '.currency') &&
        head=$(printf '%s' "$observation" | jq -er '.head'); then
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

    case "$currency" in
        conflict)
            echo "pr-keep-current: pull request $PR conflicts with its base; watch ends for the conflict stop" >&2
            exit 3
            ;;
        current)
            pending_head=
            ;;
        update_candidate)
            if [ -n "$pending_head" ]; then
                if [ "$pending_head" = "$head" ]; then
                    echo "pr-keep-current: accepted update has not settled; observing without replay"
                    sleep "$INTERVAL"
                    continue
                fi
                pending_head=
            fi
            if ! latest=$(python3 "$SCRIPT_DIR/pr-supervisor.py" currency --url "$pr_url"); then
                echo "pr-keep-current: pre-update comparison failed; retrying next tick" >&2
                sleep "$INTERVAL"
                continue
            fi
            if [ "$observation" != "$latest" ]; then
                echo "pr-keep-current: PR changed before update; reconciling next tick"
                sleep "$INTERVAL"
                continue
            fi
            pending_head=$head
            endpoint=$(printf '%s' "$pr_url" | jq -Rr 'sub("^https://[^/]+/"; "") | sub("/pull/"; "/pulls/")')
            hostname=$(printf '%s' "$pr_url" | jq -Rr 'capture("^https://(?<host>[^/]+)/").host')
            echo "pr-keep-current: proven stale; requesting server-side update"
            if update_output=$(gh api --hostname "$hostname" --method PUT "repos/$endpoint/update-branch" -f "expected_head_sha=$head" 2>&1); then
                printf '%s\n' "$update_output"
            else
                printf '%s\n' "$update_output" >&2
                case "$update_output" in
                    *"Cannot update PR branch due to conflicts"*)
                        echo "pr-keep-current: pull request $PR conflicts with its base; watch ends for the conflict stop" >&2
                        exit 3
                        ;;
                esac
                echo "pr-keep-current: update-branch outcome uncertain; observing without replay" >&2
            fi
            ;;
    esac

    sleep "$INTERVAL"
done
