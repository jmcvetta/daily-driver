#!/usr/bin/env bash
# Offline stand-in for the plugin's keep-current script. It touches no GitHub
# client and no checkout: it logs a start, a pid and a heartbeat per second to
# `.fixture/service.log`, and exits by itself after FIXTURE_SERVICE_SECONDS
# (default 45) so no test process can outlive the run. `service-exits-early`
# leaves at once with the script's conflict status, 3.
set -u
pr="${1:?pull request number required}"
dir="${FIXTURE_DIR:-.fixture}"
printf 'start pr=%s pid=%s\n' "${pr}" "$$" >>"${dir}/service.log"
printf '%s\n' "$$" >"${dir}/service.pid"
if [[ "$(<"${dir}/scenario")" == service-exits-early ]]; then
  printf 'exit status=3\n' >>"${dir}/service.log"
  exit 3
fi
for ((i = 0; i < ${FIXTURE_SERVICE_SECONDS:-45}; i++)); do
  printf 'tick %s\n' "${i}" >>"${dir}/service.log"
  sleep 1
done
printf 'exit status=0\n' >>"${dir}/service.log"
