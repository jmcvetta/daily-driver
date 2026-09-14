#!/usr/bin/env bash
# Build the clean repository a task-worktree behavior row starts in.

set -euo pipefail

mode="${1:-linked}"
case "${mode}" in
linked | detached) ;;
*)
	printf 'unknown fixture mode: %s\n' "${mode}" >&2
	exit 2
	;;
esac

git init -b master >/dev/null
git config user.name "Eval Fixture"
git config user.email "fixture@example.invalid"

mkdir -p src
cat >src/parser.py <<'EOF'
"""Parser fixture."""


def parse(value: str) -> str:
    return value.strip()
EOF

cat >.gitignore <<'EOF'
.fixture/upstream.git/
.fixture/verification.txt
EOF

git add .gitignore .fixture/setup.sh .fixture/verify.sh src/parser.py
git commit -m "Add parser fixture" >/dev/null

git init --bare -b master .fixture/upstream.git >/dev/null
git remote add upstream "$(pwd)/.fixture/upstream.git"
git push -u upstream master >/dev/null
git remote set-head upstream -a >/dev/null

# Make the current local branch the wrong start point. A correct task branch
# starts from the remote default and therefore never contains this commit.
printf 'not part of the remote base\n' >local-only.txt
git add local-only.txt
git commit -m "Advance only the current checkout" >/dev/null

if [ "${mode}" = "detached" ]; then
	git switch --detach upstream/master >/dev/null
fi
