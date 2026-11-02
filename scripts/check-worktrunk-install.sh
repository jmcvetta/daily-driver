#!/usr/bin/env bash
# Catch setup that skips conditional install, upgrades an existing wt, compiles Worktrunk,
# skips checksum verification, or hides install failures. Makes no network calls: curl
# and uname are stubs, and the release archive is a local fixture.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "${TEMP}"' EXIT
HELPER="${ROOT}/scripts/ensure-worktrunk.sh"
VERSION="$(sed -n 's/^WORKTRUNK_VERSION=//p' "${HELPER}")"
BASE_URL="https://github.com/max-sixty/worktrunk/releases/download/v${VERSION}"

# Nothing below may reach the real home directory, temp directory or install location.
export HOME="${TEMP}/home"
export TMPDIR="${TEMP}/tmp"
export WORKTRUNK_INSTALL_DIR="${TEMP}/install/bin"
mkdir -p "${HOME}" "${TMPDIR}"
unset CARGO_HOME

# A directory holding only the tools the helper needs, so a wt, brew or cargo on the
# machine running this check cannot leak in. Extra arguments name tools to leave out; a
# tool the machine lacks (xz and sha256sum on stock macOS) is left out too.
make_tools() {
	local dir="$1" tool path
	shift
	mkdir -p "${dir}"
	for tool in mktemp tar xz sha256sum install rm mkdir cat chmod; do
		case " $* " in *" ${tool} "*) continue ;; esac
		path="$(command -v "${tool}")" || continue
		ln -s "${path}" "${dir}/${tool}"
	done
}

# Write the checksum file the way Worktrunk publishes it: "<hex> *<file>".
write_checksum() {
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum --binary "$1" >"$1.sha256"
	else
		shasum -a 256 --binary "$1" >"$1.sha256"
	fi
}

make_wt() {
	printf '#!/bin/sh\nprintf "wt v%s\\n"\n' "${VERSION}" >"$1"
	chmod +x "$1"
}

make_stubs() {
	local dir="$1"
	mkdir -p "${dir}"
	cat >"${dir}/uname" <<'EOF'
#!/bin/sh
case "$1" in
	-s) printf '%s\n' "${FAKE_OS:-Linux}" ;;
	-m) printf '%s\n' "${FAKE_ARCH:-x86_64}" ;;
	*) exit 64 ;;
esac
EOF
	# Serves ${FIXTURE}/<basename of the URL> and records every URL it is asked for.
	cat >"${dir}/curl" <<'EOF'
#!/bin/sh
out="" url=""
printf '%s\n' "$*" >>"${CURL_LOG}.args"
while [ "$#" -gt 0 ]; do
	case "$1" in
		-o) out="$2"; shift ;;
		--connect-timeout | --retry | --retry-delay) shift ;;
		-*) ;;
		*) url="$1" ;;
	esac
	shift
done
printf '%s\n' "${url}" >>"${CURL_LOG}"
[ -z "${FAKE_CURL_FAIL:-}" ] || exit 22
[ -f "${FIXTURE}/${url##*/}" ] || exit 22
/bin/cp "${FIXTURE}/${url##*/}" "${out}"
EOF
	chmod +x "${dir}/uname" "${dir}/curl"
}

# Pack the staged release directory for one target into an archive, with its .sha256.
pack_release() {
	local fixture="$1" target="$2"
	mkdir -p "${fixture}"
	tar -C "${TEMP}/stage-${target}" -cJf "${fixture}/worktrunk-${target}.tar.xz" "worktrunk-${target}"
	(cd "${fixture}" && write_checksum "worktrunk-${target}.tar.xz")
}

# Build a release archive and its .sha256 for one target triple, as Worktrunk publishes them.
make_release() {
	local fixture="$1" target="$2" stage
	stage="${TEMP}/stage-${target}/worktrunk-${target}"
	rm -rf "${TEMP}/stage-${target}"
	mkdir -p "${stage}"
	make_wt "${stage}/wt"
	make_wt "${stage}/git-wt"
	printf 'README\n' >"${stage}/README.md"
	pack_release "${fixture}" "${target}"
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

reset_install() {
	rm -rf "${TEMP}/install" "${TMPDIR}" "${CURL_LOG}.args"
	mkdir -p "${TMPDIR}"
	: >"${CURL_LOG}"
}

assert_nothing_installed() {
	[ ! -e "${WORKTRUNK_INSTALL_DIR}/wt" ]
	[ ! -e "${WORKTRUNK_INSTALL_DIR}/git-wt" ]
}

assert_temp_clean() {
	[ -z "$(ls -A "${TMPDIR}")" ]
}

export CURL_LOG="${TEMP}/curl-log"
TOOLS="${TEMP}/tools"
make_tools "${TOOLS}"
STUBS="${TEMP}/stubs"
make_stubs "${STUBS}"
export FIXTURE="${TEMP}/fixture"
for target in x86_64-unknown-linux-musl aarch64-unknown-linux-musl x86_64-apple-darwin aarch64-apple-darwin; do
	make_release "${FIXTURE}" "${target}"
done
RUN_PATH="${STUBS}:${TOOLS}"

# Missing wt installs the pinned release archive after verifying its checksum, exposes the
# installed binary on PATH, verifies it, and leaves no temporary files behind.
reset_install
output="$(run_success "${RUN_PATH}")"
case "${output}" in *"wt v${VERSION}"*) ;; *) printf 'unexpected output: %s\n' "${output}" >&2; exit 1 ;;esac
[ -x "${WORKTRUNK_INSTALL_DIR}/wt" ]
[ -x "${WORKTRUNK_INSTALL_DIR}/git-wt" ]
[ "$(stat -c '%a' "${WORKTRUNK_INSTALL_DIR}/wt" 2>/dev/null || stat -f '%Lp' "${WORKTRUNK_INSTALL_DIR}/wt")" = 755 ]
[ "$(cat "${CURL_LOG}")" = "$(printf '%s\n%s' "${BASE_URL}/worktrunk-x86_64-unknown-linux-musl.tar.xz" "${BASE_URL}/worktrunk-x86_64-unknown-linux-musl.tar.xz.sha256")" ]
assert_temp_clean
# Every download bounds its connection and retries a transient failure.
[ "$(grep -c -- '--connect-timeout 20 --retry 3' "${CURL_LOG}.args")" = 2 ]

# The installed binary is reused on the next call, without another download.
: >"${CURL_LOG}"
run_success "${RUN_PATH}" >/dev/null
[ ! -s "${CURL_LOG}" ]

# Each supported platform maps to its own release archive.
for platform in "Linux aarch64 aarch64-unknown-linux-musl" "Darwin x86_64 x86_64-apple-darwin" "Darwin arm64 aarch64-apple-darwin"; do
	# shellcheck disable=SC2086
	set -- ${platform}
	reset_install
	FAKE_OS="$1" FAKE_ARCH="$2" run_success "${RUN_PATH}" >/dev/null
	[ -x "${WORKTRUNK_INSTALL_DIR}/wt" ]
	[ "$(head -n 1 "${CURL_LOG}")" = "${BASE_URL}/worktrunk-$3.tar.xz" ]
done

# Without sha256sum, shasum -a 256 verifies the archive. The stub is backed by sha256sum,
# so a machine that only has shasum (stock macOS) skips this case.
if command -v sha256sum >/dev/null 2>&1; then
	SHASUM_TOOLS="${TEMP}/shasum-tools"
	make_tools "${SHASUM_TOOLS}" sha256sum
	SHASUM_STUBS="${TEMP}/shasum-stubs"
	make_stubs "${SHASUM_STUBS}"
	# shellcheck disable=SC2016  # the stub script keeps its own $-expansions
	printf '#!/bin/sh\n[ "$1 $2 $3" = "-a 256 -c" ] || exit 64\nexec %s -c "$4"\n' "$(command -v sha256sum)" >"${SHASUM_STUBS}/shasum"
	chmod +x "${SHASUM_STUBS}/shasum"
	reset_install
	run_success "${SHASUM_STUBS}:${SHASUM_TOOLS}" >/dev/null
	[ -x "${WORKTRUNK_INSTALL_DIR}/wt" ]
fi

# A wrong checksum fails with the mismatch, names the release, and installs nothing.
BAD_SUM="${TEMP}/bad-sum"
make_release "${BAD_SUM}" x86_64-unknown-linux-musl
printf '%064d *worktrunk-x86_64-unknown-linux-musl.tar.xz\n' 0 >"${BAD_SUM}/worktrunk-x86_64-unknown-linux-musl.tar.xz.sha256"
reset_install
FIXTURE="${BAD_SUM}" run_failure "${RUN_PATH}" 'checksum mismatch for worktrunk-x86_64-unknown-linux-musl.tar.xz'
# The verifier's own output rides along, so a malformed .sha256 is not mistaken for tampering.
FIXTURE="${BAD_SUM}" run_failure "${RUN_PATH}" 'FAILED'
FIXTURE="${BAD_SUM}" run_failure "${RUN_PATH}" "https://github.com/max-sixty/worktrunk/releases/tag/v${VERSION}"
assert_nothing_installed
assert_temp_clean

# A tampered archive no longer matches its checksum.
TAMPERED="${TEMP}/tampered"
make_release "${TAMPERED}" x86_64-unknown-linux-musl
printf 'tampered' >>"${TAMPERED}/worktrunk-x86_64-unknown-linux-musl.tar.xz"
reset_install
FIXTURE="${TAMPERED}" run_failure "${RUN_PATH}" 'checksum mismatch'
assert_nothing_installed

# A failed download stops with the cause and the release URL, and installs nothing.
reset_install
FAKE_CURL_FAIL=1 run_failure "${RUN_PATH}" "downloading ${BASE_URL}/worktrunk-x86_64-unknown-linux-musl.tar.xz failed"
assert_nothing_installed
assert_temp_clean

# A missing checksum file is a failed download, not a skipped verification.
NO_SUM="${TEMP}/no-sum"
make_release "${NO_SUM}" x86_64-unknown-linux-musl
rm "${NO_SUM}/worktrunk-x86_64-unknown-linux-musl.tar.xz.sha256"
reset_install
FIXTURE="${NO_SUM}" run_failure "${RUN_PATH}" '.sha256 failed'
assert_nothing_installed

# An unsupported platform fails with the platform and the release URL.
reset_install
FAKE_OS=FreeBSD run_failure "${RUN_PATH}" 'no prebuilt release archive for FreeBSD x86_64'
FAKE_ARCH=riscv64 run_failure "${RUN_PATH}" 'no prebuilt release archive for Linux riscv64'
FAKE_OS=FreeBSD run_failure "${RUN_PATH}" "https://github.com/max-sixty/worktrunk/releases/tag/v${VERSION}"
[ ! -s "${CURL_LOG}" ]
assert_nothing_installed

# The xz binary is required only on Linux: macOS tar reads .tar.xz itself, so a Mac without
# xz must get past the tool check. (GNU tar still needs xz here, so extraction may fail.)
reset_install
XZ_TOOLS="${TEMP}/darwin-no-xz-tools"
make_tools "${XZ_TOOLS}" xz
darwin_output="$(FAKE_OS=Darwin FAKE_ARCH=arm64 PATH="${STUBS}:${XZ_TOOLS}" /bin/bash -c 'source "$1"; ensure_worktrunk' _ "${HELPER}" 2>&1 || true)"
case "${darwin_output}" in *'xz is required'*) printf 'Darwin must not require xz: %s\n' "${darwin_output}" >&2; exit 1 ;; esac

# A failed git-wt install must not leave wt behind to be reused as a finished install.
PARTIAL_TOOLS="${TEMP}/partial-tools"
make_tools "${PARTIAL_TOOLS}" install
# shellcheck disable=SC2016  # the stub script keeps its own $-expansions
printf '#!/bin/sh\nfor last; do :; done\ncase "$last" in */git-wt) exit 1 ;; esac\nexec %s "$@"\n' "$(command -v install)" >"${PARTIAL_TOOLS}/install"
chmod +x "${PARTIAL_TOOLS}/install"
reset_install
run_failure "${STUBS}:${PARTIAL_TOOLS}" 'cannot install git-wt'
assert_nothing_installed
assert_temp_clean

# A caller that runs with HOME unset still reaches an existing wt.
NO_HOME="${TEMP}/no-home"
mkdir -p "${NO_HOME}"
make_wt "${NO_HOME}/wt"
reset_install
# shellcheck disable=SC2016  # the inner script expands its own $1
env -u HOME PATH="${NO_HOME}:${RUN_PATH}" /bin/bash -uc 'source "$1"; ensure_worktrunk' _ "${HELPER}" >/dev/null
[ ! -s "${CURL_LOG}" ]

# A missing download or extraction tool names the requirement and never falls back to compiling.
for tool in curl tar xz; do
	reset_install
	MISSING_TOOLS="${TEMP}/missing-${tool}-tools"
	make_tools "${MISSING_TOOLS}" "${tool}"
	MISSING_STUBS="${TEMP}/missing-${tool}-stubs"
	make_stubs "${MISSING_STUBS}"
	[ "${tool}" != curl ] || rm "${MISSING_STUBS}/curl"
	run_failure "${MISSING_STUBS}:${MISSING_TOOLS}" "${tool} is required"
	assert_nothing_installed
done

# Without sha256sum or shasum the archive cannot be verified, so nothing is installed.
reset_install
NO_SUM_TOOLS="${TEMP}/no-sum-tools"
make_tools "${NO_SUM_TOOLS}" sha256sum
run_failure "${STUBS}:${NO_SUM_TOOLS}" 'sha256sum or shasum is required'
assert_nothing_installed

# An existing wt is verified, but must not trigger a download.
EXISTING="${TEMP}/existing"
mkdir -p "${EXISTING}"
make_wt "${EXISTING}/wt"
reset_install
run_success "${EXISTING}:${RUN_PATH}" >/dev/null
[ ! -s "${CURL_LOG}" ]
assert_nothing_installed

# An existing Homebrew wt is used as-is, without a download.
BREW="${TEMP}/brew"
mkdir -p "${BREW}/bin"
make_wt "${BREW}/bin/wt"
cat >"${BREW}/brew" <<'EOF'
#!/bin/sh
case "$*" in
	--prefix) printf '%s\n' "${FAKE_PREFIX}" ;;
	*) exit 31 ;;
esac
EOF
chmod +x "${BREW}/brew"
reset_install
FAKE_PREFIX="${BREW}" run_success "${BREW}:${RUN_PATH}" >/dev/null
[ ! -s "${CURL_LOG}" ]
assert_nothing_installed

# An existing Cargo wt is used as-is, without a download or a compile.
CARGO="${TEMP}/cargo"
mkdir -p "${CARGO}/bin"
make_wt "${CARGO}/bin/wt"
printf '#!/bin/sh\nprintf called >"%s"\nexit 99\n' "${TEMP}/unexpected-cargo" >"${CARGO}/cargo"
chmod +x "${CARGO}/cargo"
reset_install
CARGO_HOME="${CARGO}" run_success "${CARGO}:${RUN_PATH}" >/dev/null
[ ! -s "${CURL_LOG}" ]
[ ! -e "${TEMP}/unexpected-cargo" ]
assert_nothing_installed

# A missing wt never reaches Homebrew, Cargo or rustup to install it.
INSTALLERS="${TEMP}/installers"
mkdir -p "${INSTALLERS}"
for installer in brew cargo rustup; do
	# The helper may ask brew for its prefix; only an install is unexpected.
	# shellcheck disable=SC2016  # the stub script keeps its own $-expansions
	printf '#!/bin/sh\n[ "$1" = --prefix ] && exit 1\nprintf called >"%s/%s"\nexit 99\n' "${TEMP}" "unexpected-${installer}" >"${INSTALLERS}/${installer}"
	chmod +x "${INSTALLERS}/${installer}"
done
reset_install
run_success "${INSTALLERS}:${RUN_PATH}" >/dev/null
[ ! -e "${TEMP}/unexpected-brew" ]
[ ! -e "${TEMP}/unexpected-cargo" ]
[ ! -e "${TEMP}/unexpected-rustup" ]

# An archive without wt must not continue.
NO_BINARY="${TEMP}/no-binary"
make_release "${NO_BINARY}" x86_64-unknown-linux-musl
rm "${TEMP}/stage-x86_64-unknown-linux-musl/worktrunk-x86_64-unknown-linux-musl/wt"
pack_release "${NO_BINARY}" x86_64-unknown-linux-musl
reset_install
FIXTURE="${NO_BINARY}" run_failure "${RUN_PATH}" 'does not contain wt'
assert_nothing_installed

# An installed binary with a failing version check is not accepted.
BAD_VERSION="${TEMP}/bad-version"
make_release "${BAD_VERSION}" x86_64-unknown-linux-musl
printf '#!/bin/sh\nexit 19\n' >"${TEMP}/stage-x86_64-unknown-linux-musl/worktrunk-x86_64-unknown-linux-musl/wt"
chmod +x "${TEMP}/stage-x86_64-unknown-linux-musl/worktrunk-x86_64-unknown-linux-musl/wt"
pack_release "${BAD_VERSION}" x86_64-unknown-linux-musl
reset_install
FIXTURE="${BAD_VERSION}" run_failure "${RUN_PATH}" 'wt --version returned a failure after installation'

printf 'Worktrunk installer fixtures verify the release install, checksum, platform, tool, reuse and failure paths offline\n'
