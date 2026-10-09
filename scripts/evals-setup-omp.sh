#!/usr/bin/env bash
# Resolve required provider credentials and prove Omp serves each experiment's
# pinned model; install `omp` when it is missing.
#
# Usage: scripts/evals-setup-omp.sh EXPERIMENT.yaml...
#
# The models come from the experiments' own `model:` lines, so this list cannot
# drift from the arms. `vercel-ai-gateway/...` requires its key and exact catalog
# entry. A Codex model needs Omp's own login; its absence is reported but does
# not fail setup, so other provider checks can still complete.
#
# Omp reads the gateway key from `AI_GATEWAY_API_KEY`. `VERCEL_AI_GATEWAY_API_KEY`
# is used for catalog discovery; this script maps it to the provider's key name
# when it checks gateway models directly.
#
# It writes no credential anywhere, and never touches an `ANTHROPIC_*`
# variable: evals/README.md's credentials section forbids routing Anthropic
# models through the gateway.

set -euo pipefail

if [ "$#" -eq 0 ]; then
	echo "usage: $0 EXPERIMENT.yaml..." >&2
	exit 2
fi

# Where Omp's installer puts the binary: `$HOME/.local/bin` for the release
# binary, `$HOME/.bun/bin` when Bun is present and it installs through Bun.
export PATH="${PATH}:${HOME}/.local/bin:${HOME}/.bun/bin"

if [ -z "${AI_GATEWAY_API_KEY:-}" ] && [ -n "${VERCEL_AI_GATEWAY_API_KEY:-}" ]; then
	export AI_GATEWAY_API_KEY="${VERCEL_AI_GATEWAY_API_KEY}"
fi

if command -v omp >/dev/null 2>&1; then
	echo "omp: present at $(command -v omp)"
else
	echo "omp: not on PATH; installing with CI's command"
	curl -fsSL --retry 5 --retry-delay 2 --retry-all-errors https://omp.sh/install | sh
	command -v omp >/dev/null 2>&1 || {
		echo "error: omp is still not on PATH after the install." >&2
		exit 1
	}
fi
omp --version

# `omp models find` matches substrings and exits 0 on no match, so neither
# its status nor a non-empty answer proves the exact model is there.
serves() {
	omp models find "$1" --json </dev/null | python3 -c '
import json, sys
want = sys.argv[1]
models = json.load(sys.stdin).get("models", [])
sys.exit(0 if any(m.get("selector") == want for m in models) else 1)
' "$1"
}

# Read outside a process substitution, so a failing `sed` (a missing file)
# stops the run, and an empty list fails rather than checking nothing.
models="$(sed -n 's/^[[:space:]]*model:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$@" | sort -u)"
if [ -z "${models}" ]; then
	echo "error: no model: line in $*" >&2
	exit 1
fi

needs_gateway=false
while IFS= read -r model; do
	if [[ "${model}" == vercel-ai-gateway/* ]]; then
		needs_gateway=true
	fi
done <<<"${models}"
if [ "${needs_gateway}" = true ] && [ -z "${AI_GATEWAY_API_KEY:-}" ]; then
	echo "error: AI_GATEWAY_API_KEY is not set (nor VERCEL_AI_GATEWAY_API_KEY)." >&2
	echo "Omp's vercel-ai-gateway models need one of them; set it and rerun." >&2
	exit 1
fi

failed=0
while IFS= read -r model; do
	if serves "${model}"; then
		echo "ok: ${model}"
	elif [[ "${model}" == vercel-ai-gateway/* ]]; then
		echo "error: Omp does not list ${model}; check the gateway key." >&2
		failed=1
	else
		echo "unconfigured: ${model} (needs this provider's own Omp login; skipped)"
	fi
done <<<"${models}"
exit "${failed}"
