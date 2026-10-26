#!/usr/bin/env bash
# P2.3 full HTTP over NEW private, internal Docker network using cached QA images.
# Never touches Compose, production containers, volumes, .env or published ports.
set -Eeuo pipefail
if [[ "$#" -ne 0 ]]; then
  echo "Usage: bash scripts/pi-p23-docker-http-smoke.sh" >&2
  exit 2
fi
cd "$(dirname "$0")/.."
command -v docker >/dev/null
command -v python3 >/dev/null
for image in private-ai-p23-console:qa-current private-ai-p23-gateway:qa; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    echo "ABBRUCH: QA-Image lokal nicht vorhanden: $image" >&2
    exit 2
  fi
done
for script in scripts/pi-p23-docker-ollama-mock.py scripts/pi-p23-docker-http-client.py; do
  test -f "$script" || { echo "ABBRUCH: $script fehlt" >&2; exit 2; }
done

suffix="$(python3 -c 'import secrets;print(secrets.token_hex(6))')"
network="pai-p23-qa-$suffix"
mock="pai-p23-mock-$suffix"
gateway="pai-p23-gateway-$suffix"
console="pai-p23-console-$suffix"
created_network=false
started_mock=false
started_gateway=false
started_console=false
cleanup() {
  rc=$?
  trap - EXIT INT TERM
  if "$started_console"; then docker rm -f "$console" >/dev/null 2>&1 || true; fi
  if "$started_gateway"; then docker rm -f "$gateway" >/dev/null 2>&1 || true; fi
  if "$started_mock"; then docker rm -f "$mock" >/dev/null 2>&1 || true; fi
  if "$created_network"; then docker network rm "$network" >/dev/null 2>&1 || true; fi
  echo "P2.3 QA cleanup finished (disposable resources only)."
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

read -r pipeline_token knowledge_token password password_hash < <(
  python3 -c '
import hashlib,secrets
password=secrets.token_urlsafe(24)
salt=secrets.token_bytes(16)
derived=hashlib.scrypt(password.encode(),salt=salt,n=2**14,r=8,p=1,dklen=32)
print(secrets.token_urlsafe(48),secrets.token_urlsafe(48),password,
      "scrypt:"+salt.hex()+":"+derived.hex())'
)
if [[ -z "$password_hash" || -z "$knowledge_token" ]]; then
  echo "ABBRUCH: Temporäre QA-Zugangsdaten nicht erzeugt." >&2
  exit 1
fi

docker network create --driver bridge --internal "$network" >/dev/null
created_network=true
echo "P2.3 isolated internal network created (no host ports)."

docker run --rm -d \
  --name "$mock" --network "$network" --network-alias ollama \
  --read-only --memory 96m --pids-limit 64 \
  --user 10001:10001 --cap-drop ALL \
  --security-opt no-new-privileges \
  --entrypoint python private-ai-p23-gateway:qa \
  -u -c "$(cat scripts/pi-p23-docker-ollama-mock.py)" >/dev/null
started_mock=true

# Disposable SQLite database exists only on an in-container tmpfs.
docker run --rm -d \
  --name "$gateway" --network "$network" --network-alias gateway \
  --read-only \
  --tmpfs /data:rw,nosuid,nodev,size=32m,uid=10001,gid=10001 \
  --memory 256m --pids-limit 100 \
  --user 10001:10001 --cap-drop ALL \
  --security-opt no-new-privileges \
  -e PIPELINE_TOKEN="$pipeline_token" \
  -e KNOWLEDGE_TOKEN="$knowledge_token" \
  -e KNOWLEDGE_NAMESPACE=p23-docker-qa \
  -e KNOWLEDGE_IMPORT_ENABLED=true \
  -e SEMANTIC_SEARCH_ENABLED=false \
  -e MEMORY_INJECTION=false \
  -e MEMORY_DB=/data/memory.sqlite3 \
  -e OLLAMA_URL=http://ollama:11434 \
  private-ai-p23-gateway:qa >/dev/null
started_gateway=true

docker run --rm -d \
  --name "$console" --network "$network" \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=8m \
  --memory 128m --pids-limit 80 \
  --user 10001:10001 --cap-drop ALL \
  --security-opt no-new-privileges \
  -e PIPELINE_TOKEN="$pipeline_token" \
  -e KNOWLEDGE_TOKEN="$knowledge_token" \
  -e CONSOLE_PASSWORD_HASH="$password_hash" \
  -e CONSOLE_SECURE_COOKIE=false \
  -e KNOWLEDGE_IMPORT_ENABLED=true \
  -e RAG_ENABLED=true \
  -e GATEWAY_URL=http://gateway:8000 \
  private-ai-p23-console:qa-current >/dev/null
started_console=true

# No host-published port: probes execute inside the disposable Console.
ready=false
for attempt in $(seq 1 48); do
  if docker exec "$console" python -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8085/health",timeout=2).read()' \
    >/dev/null 2>&1 \
    && docker exec "$gateway" python -c \
    'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health",timeout=2).read(); urllib.request.urlopen("http://ollama:11434/v1/models",timeout=2).read()' \
    >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.25
done
if ! "$ready"; then
  echo "P2.3 QA FAIL: Console did not become ready." >&2
  docker inspect --format '{{.State.Status}}' "$console" "$gateway" "$mock" >&2 || true
  exit 1
fi

echo "P2.3 QA services ready, running authenticated Console HTTP client."
docker exec -i -e P23_QA_PASSWORD="$password" "$console" \
  python - < scripts/pi-p23-docker-http-client.py
echo "P2.3 QA: PASS (cleanup now removes disposable containers/network)."
