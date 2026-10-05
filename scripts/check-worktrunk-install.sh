#!/usr/bin/env bash
# Catch setup that skips conditional install, upgrades an existing wt, or hides install failures.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "${TEMP}"' EXIT
HELPER="${ROOT}/scripts/ensure-worktrunk.sh"

make_wt() {
	printf '#!/bin/sh\nprintf "wt vtest\\n"\n' >"$1"
	chmod +x "$1"
}

run_success() {
	local path="$1"
	PATH="${path}" /bin/bash -c 'source "$1"; ensure_worktrunk' _ "${HELPER}"
}

run_failure() {
	local path="$1" expected="$2" output
	if output="$(PATH="${path}" /bin/bash -c 'source "$1"; ensure_worktrunk' _ "${HELPER}" 2>&1)"; then
		printf 'expected Worktrunk setup failure, got success\n' >&2
		return 1
	fi
	case "${output}" in
	*"${expected}"*) ;;
	*) printf 'missing failure detail %s in: %s\n' "${expected}" "${output}" >&2; return 1 ;;
	esac
}

# Existing wt is verified, but must not trigger package installation.
EXISTING="${TEMP}/existing"
mkdir -p "${EXISTING}"
make_wt "${EXISTING}/wt"
printf '#!/bin/sh\nprintf called >"%s"\nexit 99\n' "${TEMP}/unexpected-installer" >"${EXISTING}/brew"
chmod +x "${EXISTING}/brew"
run_success "${EXISTING}"
[ ! -e "${TEMP}/unexpected-installer" ]

# Missing wt uses Homebrew, exposes the installed user binary on PATH, then verifies it.
BREW="${TEMP}/brew"
mkdir -p "${BREW}/bin"
cat >"${BREW}/brew" <<'EOF'
#!/bin/sh
case "$*" in
	"install worktrunk")
		printf installed >>"${FAKE_LOG}"
		printf '#!/bin/sh\nprintf "wt vtest\\n"\n' >"${FAKE_PREFIX}/bin/wt"
		/bin/chmod +x "${FAKE_PREFIX}/bin/wt"
		;;
	--prefix) printf '%s\n' "${FAKE_PREFIX}" ;;
	*) exit 31 ;;
esac
EOF
chmod +x "${BREW}/brew"
FAKE_LOG="${TEMP}/brew-called" FAKE_PREFIX="${BREW}" run_success "${BREW}:/usr/bin:/bin"
FAKE_LOG="${TEMP}/brew-called" FAKE_PREFIX="${BREW}" run_success "${BREW}:/usr/bin:/bin"
[ "$(cat "${TEMP}/brew-called")" = installed ]
[ -e "${TEMP}/brew-called" ]

# Missing wt uses Cargo when Homebrew is absent.
CARGO="${TEMP}/cargo"
mkdir -p "${CARGO}/bin"
cat >"${CARGO}/cargo" <<'EOF'
#!/bin/sh
[ "$*" = "install --locked worktrunk" ] || exit 32
printf installed >>"${FAKE_LOG}"
printf '#!/bin/sh\nprintf "wt vtest\\n"\n' >"${FAKE_PREFIX}/bin/wt"
/bin/chmod +x "${FAKE_PREFIX}/bin/wt"
EOF
chmod +x "${CARGO}/cargo"
HOME="${TEMP}" CARGO_HOME="${CARGO}" FAKE_LOG="${TEMP}/cargo-called" FAKE_PREFIX="${CARGO}" run_success "${CARGO}:/usr/bin:/bin"
HOME="${TEMP}" CARGO_HOME="${CARGO}" FAKE_LOG="${TEMP}/cargo-called" FAKE_PREFIX="${CARGO}" run_success "${CARGO}:/usr/bin:/bin"
[ "$(cat "${TEMP}/cargo-called")" = installed ]
[ -e "${TEMP}/cargo-called" ]

# No supported installer and a failing installer both stop with the cause.
EMPTY="${TEMP}/empty"
mkdir -p "${EMPTY}"
run_failure "${EMPTY}" 'Worktrunk is unavailable'
FAIL="${TEMP}/fail"
mkdir -p "${FAIL}"
printf '#!/bin/sh\nexit 17\n' >"${FAIL}/brew"
chmod +x "${FAIL}/brew"
run_failure "${FAIL}" 'brew install worktrunk returned a failure'

# An installer that reports success without exposing a binary must not continue.
NO_BINARY="${TEMP}/no-binary"
mkdir -p "${NO_BINARY}/bin"
cat >"${NO_BINARY}/brew" <<'EOF'
#!/bin/sh
case "$*" in
	"install worktrunk") exit 0 ;;
	--prefix) printf '%s\n' "${FAKE_PREFIX}" ;;
	*) exit 33 ;;
esac
EOF
chmod +x "${NO_BINARY}/brew"
FAKE_PREFIX="${NO_BINARY}" run_failure "${NO_BINARY}:/usr/bin:/bin" 'did not put wt on PATH'

# An installed binary with a failing version check is not accepted.
BAD_VERSION="${TEMP}/bad-version"
mkdir -p "${BAD_VERSION}/bin"
cat >"${BAD_VERSION}/brew" <<'EOF'
#!/bin/sh
case "$*" in
	"install worktrunk")
		printf '#!/bin/sh\nexit 19\n' >"${FAKE_PREFIX}/bin/wt"
		/bin/chmod +x "${FAKE_PREFIX}/bin/wt"
		;;
	--prefix) printf '%s\n' "${FAKE_PREFIX}" ;;
	*) exit 34 ;;
esac
EOF
chmod +x "${BAD_VERSION}/brew"
FAKE_PREFIX="${BAD_VERSION}" run_failure "${BAD_VERSION}:/usr/bin:/bin" 'wt --version returned a failure'
printf 'Worktrunk installer fixtures verify existing CLI, Homebrew, Cargo and failure paths\n'
