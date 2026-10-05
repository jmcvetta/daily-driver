#!/usr/bin/env bash
# Ensure the user-scoped Worktrunk CLI is available without upgrading it.

ensure_worktrunk() {
	local install_bin brew_prefix
	if command -v wt >/dev/null 2>&1; then
		wt --version || {
			printf 'Worktrunk verification failed: wt --version returned a failure.\n' >&2
			return 1
		}
		return 0
	fi

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
	if [ -n "${install_bin}" ]; then
		PATH="${install_bin}:${PATH}"
		export PATH
		wt --version || {
			printf 'Worktrunk verification failed: wt --version returned a failure from %s.\n' "${install_bin}" >&2
			return 1
		}
		return 0
	fi
	if command -v brew >/dev/null 2>&1; then
		if ! brew install worktrunk; then
			printf 'Worktrunk installation failed: brew install worktrunk returned a failure.\n' >&2
			return 1
		fi
		brew_prefix="$(brew --prefix)" || {
			printf 'Worktrunk installation succeeded, but brew --prefix failed; cannot locate its bin directory.\n' >&2
			return 1
		}
		install_bin="${brew_prefix}/bin"
	elif command -v cargo >/dev/null 2>&1; then
		if ! cargo install --locked worktrunk; then
			printf 'Worktrunk installation failed: cargo install --locked worktrunk returned a failure.\n' >&2
			return 1
		fi
		install_bin="${CARGO_HOME:-${HOME}/.cargo}/bin"
	else
		printf 'Worktrunk is unavailable: install it with Homebrew (brew install worktrunk) or Cargo (cargo install --locked worktrunk), then retry.\n' >&2
		return 1
	fi

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
