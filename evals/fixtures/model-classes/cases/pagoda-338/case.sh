#!/usr/bin/env bash
# Clones Green-Pagoda/pagoda#338 at its base SHA. See `../../shared/lib.sh`.
# shellcheck source=../../shared/lib.sh
source "$(dirname "$0")/lib.sh"
fixture_clone_base "Green-Pagoda/pagoda" "7eb6d254230e28036ed4a4f57adbd1eff67a0c3c"
