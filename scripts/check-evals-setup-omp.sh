#!/usr/bin/env bash
# Drive scripts/evals-setup-omp.sh against a stub `omp` and a stub `curl` in a
# throwaway HOME. Offline: the real installer and the gateway are never reached.
#
# Without it these pass silently: a cloud container that exports only
# VERCEL_AI_GATEWAY_API_KEY, where Omp lists no gateway model; a reinstall over
# an `omp` that is already there; an `omp models find` substring hit
# (glm-5.3-flash for glm-5.3) taken as the exact model; an experiment list
# that yields no model, which checks nothing and passes; and a missing key that
# a later paid run discovers instead of this setup.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETUP="${REPO_ROOT}/scripts/evals-setup-omp.sh"
ROOT="$(mktemp -d)"
trap 'rm -rf "${ROOT}"' EXIT

BIN="${ROOT}/bin"
mkdir -p "${BIN}" "${ROOT}/home"

# Like the real `omp`: gateway models are listed only when AI_GATEWAY_API_KEY
# is set, `find` is a substring search, and no match still exits 0.
cat >"${BIN}/omp" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "--version" ]; then echo "omp/stub"; exit 0; fi
catalog="openai-codex/gpt-5.6-sol"
if [ -n "${AI_GATEWAY_API_KEY:-}" ]; then
	catalog="${catalog} vercel-ai-gateway/zai/glm-5.3-flash ${STUB_GATEWAY:-vercel-ai-gateway/zai/glm-5.3}"
fi
[ -z "${STUB_NO_CODEX:-}" ] || catalog="${catalog#openai-codex/gpt-5.6-sol}"
printf '{"models":['
sep=""
for m in ${catalog}; do
	case "${m}" in *"$3"*) printf '%s{"selector":"%s"}' "${sep}" "${m}"; sep=",";; esac
done
printf ']}\n'
EOF
# Any call to curl is an install attempt; record it and fail.
cat >"${BIN}/curl" <<EOF
#!/usr/bin/env bash
echo called >"${ROOT}/curl-called"
exit 1
EOF
chmod +x "${BIN}/omp" "${BIN}/curl"

cat >"${ROOT}/omp-a.yaml" <<'EOF'
variants:
  - agent:
    model: vercel-ai-gateway/zai/glm-5.3
EOF
cat >"${ROOT}/omp-b.yaml" <<'EOF'
    model: openai-codex/gpt-5.6-sol   # a comment
EOF

# run NAME EXPECTED_STATUS ENV...: run the setup with only ENV set, over
# EXPERIMENTS (default: the two files above). EXPECTED_STATUS `nz` accepts any
# failure, for an exit status that is sed's rather than the script's.
run() {
	local name="$1" expected="$2" status=0
	shift 2
	# shellcheck disable=SC2086 # EXPERIMENTS is a list of paths
	env -i HOME="${ROOT}/home" PATH="${BIN}:/usr/bin:/bin" "$@" \
		bash "${SETUP}" ${EXPERIMENTS:-"${ROOT}/omp-a.yaml" "${ROOT}/omp-b.yaml"} \
		>"${ROOT}/out" 2>&1 || status=$?
	if [ "${expected}" = nz ] && [ "${status}" -ne 0 ]; then
		expected="${status}"
	fi
	if [ "${status}" != "${expected}" ]; then
		echo "FAIL ${name}: exit ${status}, want ${expected}" >&2
		cat "${ROOT}/out" >&2
		exit 1
	fi
	echo "ok ${name}"
}

expect_out() {
	grep -qF -- "$1" "${ROOT}/out" || {
		echo "FAIL: output lacks: $1" >&2
		cat "${ROOT}/out" >&2
		exit 1
	}
}

run "AI_GATEWAY_API_KEY alone" 0 AI_GATEWAY_API_KEY=k
expect_out "ok: vercel-ai-gateway/zai/glm-5.3"
expect_out "ok: openai-codex/gpt-5.6-sol"

run "VERCEL_AI_GATEWAY_API_KEY alone" 0 VERCEL_AI_GATEWAY_API_KEY=k
expect_out "ok: vercel-ai-gateway/zai/glm-5.3"

run "neither key" 1
expect_out "AI_GATEWAY_API_KEY is not set (nor VERCEL_AI_GATEWAY_API_KEY)"

run "substring hit is not the model" 1 AI_GATEWAY_API_KEY=k STUB_GATEWAY=none
expect_out "error: Omp does not list vercel-ai-gateway/zai/glm-5.3"

run "codex arm unconfigured" 0 AI_GATEWAY_API_KEY=k STUB_NO_CODEX=1
expect_out "unconfigured: openai-codex/gpt-5.6-sol"

EXPERIMENTS="${ROOT}/missing.yaml" run "missing experiment file" nz AI_GATEWAY_API_KEY=k
expect_out "missing.yaml"

printf 'variants: []\n' >"${ROOT}/empty.yaml"
EXPERIMENTS="${ROOT}/empty.yaml" run "no model to check" 1 AI_GATEWAY_API_KEY=k
expect_out "error: no model: line"

if [ -e "${ROOT}/curl-called" ]; then
	echo "FAIL: the installer ran although omp was on PATH" >&2
	exit 1
fi
echo "ok omp present, no reinstall"
