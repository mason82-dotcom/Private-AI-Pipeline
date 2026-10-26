#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo 'Docker fehlt'; exit 1; }
docker compose version >/dev/null || { echo 'Docker Compose v2 fehlt'; exit 1; }
[[ -f .env ]] || { echo 'Bitte erst ./scripts/init.sh ausführen'; exit 1; }
# Check config without displaying secrets.
docker compose config --quiet
port="$(sed -n 's/^WEBUI_PORT=//p' .env | head -n1)"
port="${port:-38880}"
if [[ "$port" =~ ^[0-9]+$ ]] && (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1; then
  echo "ACHTUNG: 127.0.0.1:$port ist bereits erreichbar; Portbelegung prüfen."
  exit 2
fi
echo "Konfiguration OK. UI-Port $port scheint frei; keine Dienste geändert."
