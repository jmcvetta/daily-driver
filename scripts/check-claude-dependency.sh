#!/usr/bin/env bash
# Catch a marketplace install that omits its Claude dependency or leaves the legacy identity enabled.

set -euo pipefail

if ! command -v claude >/dev/null 2>&1; then
	printf 'Claude Code CLI required for dependency fixtures\n' >&2
	exit 1
fi

ROOT="$(mktemp -d)"
trap 'rm -rf "${ROOT}"' EXIT
CATALOG="${ROOT}/daily-driver"
LEGACY="${ROOT}/legacy-worktrunk"
mkdir -p \
	"${CATALOG}/.claude-plugin" \
	"${CATALOG}/plugins/daily-driver/.claude-plugin" \
	"${CATALOG}/plugins/worktrunk/.claude-plugin" \
	"${LEGACY}/.claude-plugin" \
	"${LEGACY}/plugins/worktrunk/.claude-plugin"

cat >"${CATALOG}/.claude-plugin/marketplace.json" <<'EOF'
{
  "name": "daily-driver",
  "owner": {"name": "Fixture"},
  "plugins": [
    {"name": "daily-driver", "source": "./plugins/daily-driver"},
    {"name": "worktrunk", "source": "./plugins/worktrunk"}
  ]
}
EOF
cat >"${CATALOG}/plugins/daily-driver/.claude-plugin/plugin.json" <<'EOF'
{"name":"daily-driver","version":"1.0.0","description":"fixture","dependencies":["worktrunk"]}
EOF
cat >"${CATALOG}/plugins/worktrunk/.claude-plugin/plugin.json" <<'EOF'
{"name":"worktrunk","version":"1.0.0","description":"fixture"}
EOF
cat >"${LEGACY}/.claude-plugin/marketplace.json" <<'EOF'
{
  "name": "worktrunk",
  "owner": {"name": "Fixture"},
  "plugins": [
    {"name": "worktrunk", "source": "./plugins/worktrunk"}
  ]
}
EOF
cat >"${LEGACY}/plugins/worktrunk/.claude-plugin/plugin.json" <<'EOF'
{"name":"worktrunk","version":"1.0.0","description":"fixture"}
EOF

assert_enabled() {
	claude plugin list --json | python3 -c '
import json, sys
expected = set(sys.argv[1:])
plugins = json.load(sys.stdin)
enabled = {plugin["id"] for plugin in plugins if plugin.get("enabled")}
if not expected <= enabled:
    raise SystemExit(f"missing enabled plugins: {sorted(expected - enabled)}")
worktrunk = {plugin["id"] for plugin in plugins
             if plugin["id"].startswith("worktrunk@") and plugin.get("enabled")}
if len(worktrunk) != 1:
    raise SystemExit(f"expected exactly one enabled Worktrunk identity, found {sorted(worktrunk)}")
legacy = {plugin["id"] for plugin in plugins if plugin["id"] == "worktrunk@worktrunk"}
if legacy:
    raise SystemExit(f"legacy Worktrunk identity remains installed: {sorted(legacy)}")
for plugin in plugins:
    if plugin.get("id") in expected:
        from pathlib import Path
        manifest = Path(plugin["installPath"]) / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            raise SystemExit(f"cached plugin manifest missing: {manifest}")
' "${@}"
}

cd "${ROOT}"

# A clean install must enable the dependency from the same marketplace.
export HOME="${ROOT}/home-clean"
export CLAUDE_CONFIG_DIR="${ROOT}/config-clean"
mkdir -p "${HOME}" "${CLAUDE_CONFIG_DIR}"
claude plugin marketplace add "${CATALOG}"
claude plugin install daily-driver@daily-driver --scope user
assert_enabled daily-driver@daily-driver worktrunk@daily-driver

# The migration must remove the old marketplace identity before enabling the new one.
export HOME="${ROOT}/home-migration"
export CLAUDE_CONFIG_DIR="${ROOT}/config-migration"
mkdir -p "${HOME}" "${CLAUDE_CONFIG_DIR}"
claude plugin marketplace add "${LEGACY}"
claude plugin marketplace add "${CATALOG}"
claude plugin install worktrunk@worktrunk --scope user
claude plugin disable worktrunk@worktrunk --scope user
claude plugin uninstall worktrunk@worktrunk --scope user
claude plugin install daily-driver@daily-driver --scope user
assert_enabled daily-driver@daily-driver worktrunk@daily-driver

printf 'Claude marketplace dependency install and legacy migration pass in isolated configuration\n'
