#!/usr/bin/env bash
# Offline backup of own volumes only. Requires running gateway and an existing WebUI container.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
command -v docker >/dev/null
command -v tar >/dev/null
command -v python3 >/dev/null
mkdir -p backups
stage="$(mktemp -d "${PWD}/backups/.backup-staging.XXXXXXXX")"
was_running=0
cleanup() {
  local code=$?
  if ((was_running)); then docker compose start webui >/dev/null || echo 'WARN: WebUI manuell starten' >&2; fi
  rm -rf -- "$stage"
  exit "$code"
}
trap cleanup EXIT
webui_id="$(docker compose ps -a -q webui)"
[[ -n "$webui_id" ]] || { echo 'WebUI-Container fehlt. Erst installieren.' >&2; exit 1; }
[[ -n "$(docker compose ps -q gateway)" ]] || { echo 'Gateway muss für die konsistente SQLite-Sicherung laufen.' >&2; exit 1; }
if [[ -n "$(docker compose ps -q webui)" ]]; then
  was_running=1
  docker compose stop webui >/dev/null
fi
mkdir -p "$stage/webui"
docker cp "$webui_id:/app/backend/data/." "$stage/webui/" >/dev/null
# SQLite backup API: coherent DB image even while gateway writes (no WAL copy).
docker compose exec -T gateway python -c '
import os, sqlite3, shutil, sys, tempfile
fd, path = tempfile.mkstemp(prefix=".backup-", suffix=".db", dir="/data")
os.close(fd)
try:
    src = sqlite3.connect("/data/memory.sqlite3")
    dst = sqlite3.connect(path)
    with dst: src.backup(dst)
    dst.close(); src.close()
    with open(path,"rb") as f: shutil.copyfileobj(f, sys.stdout.buffer)
finally:
    os.unlink(path)
' > "$stage/memory.sqlite3"
cp .env "$stage/config.env"
python3 - "$stage" <<'PY'
import json, pathlib, sys
from datetime import datetime, timezone
root = pathlib.Path(sys.argv[1])
(root / 'manifest.json').write_text(json.dumps({
    'schema': 'private-ai-pipeline-backup-v0.2',
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'includes': ['memory.sqlite3','webui/','config.env'],
    'caution': 'Contains private chat data and plaintext secrets; encrypt for off-host storage.'
}, ensure_ascii=False, indent=2), encoding='utf-8')
PY
archive="backups/private-ai-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
tar -C "$stage" -czf "$archive" .
chmod 600 "$archive"
sha256sum "$archive" > "$archive.sha256"
chmod 600 "$archive.sha256"
echo "Backup erstellt: $archive (persönliche Daten und Geheimnisse, UNVERSCHLÜSSELT)"
