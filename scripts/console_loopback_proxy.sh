#!/usr/bin/env bash
# Loopback-only host bridge for a healthy Console on Docker's internal bridge.
# This intentionally does not attach Console to an egress-capable network.
set -euo pipefail

CONTAINER="${PAI_CONSOLE_CONTAINER:-private-ai-pipeline-console-1}"
NETWORK="private-ai-pipeline_pipeline"
command -v docker >/dev/null
command -v socat >/dev/null

ip=$(docker inspect --format   '{{with index .NetworkSettings.Networks "private-ai-pipeline_pipeline"}}{{.IPAddress}}{{end}}'   "$CONTAINER")

if [[ ! "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "Keine gültige Container-IP im Netzwerk $NETWORK" >&2
  exit 1
fi

# Verify the expected Console endpoint, not just a running container.
if ! curl --silent --show-error --fail --max-time 5   "http://${ip}:8085/health" >/dev/null; then
  echo "Console unter ${ip}:8085 nicht erreichbar" >&2
  exit 1
fi

echo "Private AI Console loopback proxy: 127.0.0.1:38881 -> ${ip}:8085"
# Never bind to 0.0.0.0. When Console is recreated (IP may change), restart
# this proxy service after the new container reaches healthy status.
exec socat   TCP4-LISTEN:38881,bind=127.0.0.1,reuseaddr,fork   "TCP4:${ip}:8085"
