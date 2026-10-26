#!/usr/bin/env bash
# Disaster restore: destructive, limited strictly to this Compose project's own named volumes.
# Important: run a backup first. Encrypted/off-host storage is the operator's responsibility.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
umask 077
if [[ $# != 2 || "$2" != '--yes' ]]; then
  echo 'Aufruf: ./scripts/restore.sh backups/private-ai-....tar.gz --yes' >&2
  echo 'ACHTUNG: Ersetzt das vorhandene Gedächtnis und sämtliche Open-WebUI-Dateien!' >&2
  exit 2
fi
archive="$(realpath -- "$1")"
[[ -f "$archive" ]] || { echo 'Archiv nicht gefunden' >&2; exit 1; }
if [[ -f "$archive.sha256" ]]; then (cd "$(dirname "$archive")" && sha256sum -c "$(basename "$archive").sha256"); fi
stage="$(mktemp -d)"
was_ui=0; was_gateway=0
cleanup() {
  local code=$?
  if ((was_gateway)); then docker compose start gateway >/dev/null || true; fi
  if ((was_ui)); then docker compose start webui >/dev/null || true; fi
  rm -rf -- "$stage"
  exit "$code"
}
trap cleanup EXIT
# Reject hostile tar entries, symlinks and devices before extraction.
python3 - "$archive" "$stage" <<'PY'
import json, pathlib, sys, tarfile
archive, target = sys.argv[1:]
with tarfile.open(archive, 'r:gz') as tar:
    for member in tar.getmembers():
        p = pathlib.PurePosixPath(member.name)
        if p.is_absolute() or '..' in p.parts or not (member.isdir() or member.isfile()):
            raise SystemExit('Unsichere Archivstruktur; Wiederherstellung abgebrochen')
    tar.extractall(target, filter='data')
root = pathlib.Path(target)
info = json.loads((root / 'manifest.json').read_text())
assert info.get('schema') == 'private-ai-pipeline-backup-v0.2'
assert (root / 'memory.sqlite3').is_file() and (root / 'webui').is_dir()
PY
gw_cid="$(docker compose ps -a -q gateway)"
ui_cid="$(docker compose ps -a -q webui)"
[[ -n "$gw_cid" && -n "$ui_cid" ]] || { echo 'Container fehlen; zuerst docker compose up -d ausführen' >&2; exit 1; }
gw_vol="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}' "$gw_cid")"
ui_vol="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/backend/data"}}{{.Name}}{{end}}{{end}}' "$ui_cid")"
[[ -n "$gw_vol" && -n "$ui_vol" ]] || { echo 'Eigene Volumes nicht eindeutig gefunden' >&2; exit 1; }
image="$(docker inspect --format '{{.Image}}' "$gw_cid")"
if [[ -n "$(docker compose ps -q webui)" ]]; then was_ui=1; docker compose stop webui >/dev/null; fi
if [[ -n "$(docker compose ps -q gateway)" ]]; then was_gateway=1; docker compose stop gateway >/dev/null; fi
# A locally-built gateway image is reused offline; no alpine/other pulls.
docker run --rm --network none --user 0:0 \
  --mount "type=volume,src=$gw_vol,dst=/target" \
  --mount "type=bind,src=$stage/memory.sqlite3,dst=/source.db,readonly" \
  --entrypoint python "$image" -c '
import glob,os,shutil
for p in glob.glob("/target/memory.sqlite3*"):
    if os.path.isfile(p): os.remove(p)
shutil.copyfile("/source.db","/target/memory.sqlite3")
os.chown("/target",10001,10001)
os.chown("/target/memory.sqlite3",10001,10001)
os.chmod("/target/memory.sqlite3",0o600)
'
docker run --rm --network none --user 0:0 \
  --mount "type=volume,src=$ui_vol,dst=/target" \
  --mount "type=bind,src=$stage/webui,dst=/source,readonly" \
  --entrypoint python "$image" -c '
import os,shutil
for name in os.listdir("/target"):
    p=os.path.join("/target",name)
    if os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p)
    else: os.unlink(p)
for name in os.listdir("/source"):
    src=os.path.join("/source",name); dest=os.path.join("/target",name)
    if os.path.isdir(src) and not os.path.islink(src): shutil.copytree(src,dest,symlinks=False)
    else: shutil.copy2(src,dest)
'
# Never silently replace the user's current .env and rotate live secrets.
cp "$stage/config.env" "${archive}.restored-config.env"
chmod 600 "${archive}.restored-config.env"
echo 'Daten wiederhergestellt. Konfiguration wurde nur daneben gespeichert:'
echo "${archive}.restored-config.env"
echo 'Secrets und WebUI-Dateiberechtigungen vor produktiver Nutzung prüfen.'
