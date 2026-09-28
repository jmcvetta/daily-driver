#!/usr/bin/env bash
#
# Clones one source repository at its base SHA into the sandbox root. The
# task's `pre_run` calls it as
#     bash .fixture/clone-base.sh owner/repo <base-sha>
# See `lib.sh` for what the clone leaves behind.

set -euo pipefail

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"
fixture_clone_base "$1" "$2"
