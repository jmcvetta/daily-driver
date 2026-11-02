#!/usr/bin/env bash
# Ensure the user-scoped Worktrunk CLI is available without upgrading it.
#
# A missing wt is installed from Worktrunk's prebuilt, checksum-verified release
# archive. The helper never compiles Worktrunk and never queries "latest": bump
# the pinned version below by hand.

WORKTRUNK_VERSION=0.81.0

# Install wt and git-wt from the pinned release archive into the install
# directory. It runs in a subshell, so its EXIT trap removes the temporary
# directory on every exit path.
_worktrunk_install_release() {
	local install_dir="$1"
	(
		release_url="https://github.com/max-sixty/worktrunk/releases/tag/v${WORKTRUNK_VERSION}"
		fail() {
			printf 'Worktrunk installation failed: %s. Install Worktrunk from %s, then retry.\n' "$1" "${release_url}" >&2
			exit 1
		}

		os="$(uname -s)"
		arch="$(uname -m)"
		case "${os}/${arch}" in
		Linux/x86_64) target=x86_64-unknown-linux-musl ;;
		Linux/aarch64 | Linux/arm64) target=aarch64-unknown-linux-musl ;;
		Darwin/x86_64) target=x86_64-apple-darwin ;;
		Darwin/arm64 | Darwin/aarch64) target=aarch64-apple-darwin ;;
		*) fail "no prebuilt release archive for ${os} ${arch}" ;;
		esac

		# GNU tar calls the xz binary; macOS tar reads .tar.xz itself.
		tools="curl tar"
		[ "${os}" != Linux ] || tools="${tools} xz"
		for tool in ${tools}; do
			command -v "${tool}" >/dev/null 2>&1 || fail "${tool} is required to install the release archive"
		done
		if command -v sha256sum >/dev/null 2>&1; then
			verify() { sha256sum -c "$1"; }
		elif command -v shasum >/dev/null 2>&1; then
			verify() { shasum -a 256 -c "$1"; }
		else
			fail "sha256sum or shasum is required to verify the release archive"
		fi

		archive="worktrunk-${target}.tar.xz"
		base_url="https://github.com/max-sixty/worktrunk/releases/download/v${WORKTRUNK_VERSION}"
		temp="$(mktemp -d)" || fail "mktemp could not create a temporary directory"
		trap 'rm -rf "${temp}"' EXIT

		cd "${temp}" || fail "cannot enter the temporary directory"
		curl -fsSL --connect-timeout 20 --retry 3 --retry-delay 2 -o "${archive}" "${base_url}/${archive}" || fail "downloading ${base_url}/${archive} failed"
		curl -fsSL --connect-timeout 20 --retry 3 --retry-delay 2 -o "${archive}.sha256" "${base_url}/${archive}.sha256" || fail "downloading ${base_url}/${archive}.sha256 failed"
		check_output="$(verify "${archive}.sha256" 2>&1)" || fail "checksum mismatch for ${archive} (${check_output//$'\n'/; })"
		tar -xJf "${archive}" || fail "extracting ${archive} failed"

		src="${temp}/worktrunk-${target}"
		[ -f "${src}/wt" ] || fail "${archive} does not contain wt"
		mkdir -p "${install_dir}" || fail "cannot create ${install_dir}"
		# wt goes last: a reused wt must mean the whole install finished.
		if [ -f "${src}/git-wt" ]; then
			install -m 755 "${src}/git-wt" "${install_dir}/git-wt" || fail "cannot install git-wt into ${install_dir}"
		fi
		install -m 755 "${src}/wt" "${install_dir}/wt" || fail "cannot install wt into ${install_dir}"
	)
}

ensure_worktrunk() {
	local install_bin brew_prefix release_bin
	if command -v wt >/dev/null 2>&1; then
		wt --version || {
			printf 'Worktrunk verification failed: wt --version returned a failure.\n' >&2
			return 1
		}
		return 0
	fi
	release_bin="${WORKTRUNK_INSTALL_DIR:-${HOME}/.local/bin}"

	install_bin=""
	if command -v brew >/dev/null 2>&1; then
		brew_prefix="$(brew --prefix)" || brew_prefix=""
		if [ -n "${brew_prefix}" ] && [ -x "${brew_prefix}/bin/wt" ]; then
			install_bin="${brew_prefix}/bin"
		fi
	fi
	if [ -z "${install_bin}" ] && [ -x "${CARGO_HOME:-${HOME}/.cargo}/bin/wt" ]; then
		install_bin="${CARGO_HOME:-${HOME}/.cargo}/bin"
	fi
	if [ -z "${install_bin}" ] && [ -x "${release_bin}/wt" ]; then
		install_bin="${release_bin}"
	fi
	if [ -n "${install_bin}" ]; then
		PATH="${install_bin}:${PATH}"
		export PATH
		wt --version || {
			printf 'Worktrunk verification failed: wt --version returned a failure from %s.\n' "${install_bin}" >&2
			return 1
		}
		return 0
	fi

	_worktrunk_install_release "${release_bin}" || return 1
	install_bin="${release_bin}"

	case ":${PATH}:" in
	*":${install_bin}:"*) ;;
	*) PATH="${install_bin}:${PATH}"; export PATH ;;
	esac

	if ! command -v wt >/dev/null 2>&1; then
		printf 'Worktrunk installation did not put wt on PATH (checked %s). Add its bin directory to PATH, then retry.\n' "${install_bin}" >&2
		return 1
	fi
	if ! wt --version; then
		printf 'Worktrunk verification failed: wt --version returned a failure after installation.\n' >&2
		return 1
	fi
}
