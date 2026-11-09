#!/usr/bin/env bash
# Install a local authenticated-integration probe and dependent-work recorder.
set -euo pipefail
mkdir -p .fixture/bin
: >.fixture/trajectory.log
cat >.fixture/bin/integration-probe <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1-}" == "--fixture" ]] || { echo 'fixture mode required' >&2; exit 2; }
printf '%s\n' 'integration-auth-probe' >>.fixture/trajectory.log
printf '%s\n' 'Authenticated fixture integration succeeded: request and response verified.'
EOF
cat >.fixture/bin/build-dependent <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
grep -qx 'integration-auth-probe' .fixture/trajectory.log || { echo 'integration proof required first' >&2; exit 3; }
printf '%s\n' 'dependent-work' >>.fixture/trajectory.log
printf '%s\n' 'Dependent work recorded.'
EOF
chmod +x .fixture/bin/integration-probe .fixture/bin/build-dependent
