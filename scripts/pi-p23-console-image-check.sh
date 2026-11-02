#!/usr/bin/env bash
# P2.3 non-deploying Compose/Image acceptance; no existing containers touched.
set -euo pipefail
cd "$(dirname "$0")/.."

# --build          Console-QA-Image private-ai-p23-console:qa-current (ohne Netz)
# --build-gateway  Gateway-QA-Image private-ai-p23-gateway:qa; laedt dabei NUR pypdf==5.9.0 (Wheel) von PyPI
# Beide Namen sind genau die, die scripts/pi-p23-docker-http-smoke.sh erwartet.
do_build=false
do_gateway=false
for arg in "$@"; do
  case "$arg" in
    --build) do_build=true ;;
    --build-gateway) do_gateway=true ;;
    *) echo "Usage: bash scripts/pi-p23-console-image-check.sh [--build] [--build-gateway]" >&2; exit 2 ;;
  esac
done

command -v docker >/dev/null
command -v python3 >/dev/null
envfile="$(mktemp /tmp/p23-compose-test.XXXXXXXX)"
trap 'rm -f "$envfile"' EXIT
chmod 600 "$envfile"
cat > "$envfile" <<'EOF'
PIPELINE_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WEBUI_SECRET_KEY=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
KNOWLEDGE_TOKEN=kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk
CONSOLE_PASSWORD_HASH=scrypt:00000000000000000000000000000000:0000000000000000000000000000000000000000000000000000000000000000
RAG_ENABLED=true
CONSOLE_PORT=38881
KNOWLEDGE_IMPORT_ENABLED=false
SEMANTIC_SEARCH_ENABLED=false
MEMORY_INJECTION=false
EOF

# No container start/restart/stop/pull and no production .env read or print.
docker compose --env-file "$envfile" \
  -f compose.yaml -f compose.console.yaml --profile console config --format json \
  | python3 -c '
import json,sys
c=json.load(sys.stdin)
services=c["services"]; console=services["console"]
assert console["environment"]["RAG_ENABLED"] in ("true",True)
assert console["environment"]["KNOWLEDGE_IMPORT_ENABLED"] in ("false",False)
assert console["environment"]["GATEWAY_URL"]=="http://gateway:8000"
assert console["read_only"] is True
assert console["security_opt"]==["no-new-privileges:true"]
assert "ALL" in console["cap_drop"]
assert any(p.get("host_ip")=="127.0.0.1" for p in console["ports"])
assert any(network.get("internal") is True for network in c["networks"].values())
print("P2.3 isolated Compose config: PASS (RAG opt-in, loopback, read-only, internal network)")
'

if ! "$do_build" && ! "$do_gateway"; then
  echo "P2.3 Compose config: PASS; Docker image build not requested."
  echo "Optional: bash scripts/pi-p23-console-image-check.sh --build [--build-gateway]"
  exit 0
fi

# Verify the base image is cached first, so the optional build cannot pull it.
# This deliberately fails if the host has not previously cached python:3.13-slim.
if ! docker image inspect python:3.13-slim >/dev/null 2>&1; then
  echo 'ABBRUCH: python:3.13-slim nicht lokal im Docker-Cache; kein Download erlaubt.' >&2
  exit 2
fi
if "$do_build"; then
# Build an isolated QA image only; never start a production service.
image=private-ai-p23-console:qa-current
docker build --pull=false --network=none --tag "$image" ./console
docker run --rm --network none --read-only \
  --user 10001:10001 --cap-drop ALL \
  --security-opt no-new-privileges \
  --entrypoint python "$image" -c '
from pathlib import Path
from rag import build_rag_messages
from server import check_gateway_url
assert Path("/app/static/app.js").is_file()
assert Path("/app/static/styles.css").is_file()
assert Path("/app/static/index.html").is_file()
assert check_gateway_url("http://gateway:8000") == "http://gateway:8000"
messages,sources=build_rag_messages(
    [{"role":"user","content":"Hydraulik?"}],
    {"results":[{"source":"upload:abc#0","filename":"local.txt",
                 "excerpt":"Die Pumpe erzeugt Oeldruck."}]}
)
assert len(sources)==1 and len(messages)>=2
print("P2.3 isolated Console image/runtime: PASS (non-root, read-only, network none)")
'
echo "P2.3 Console QA image: $image"
fi

if "$do_gateway"; then
  # --pull=false: das Basis-Image kommt nur aus dem Cache. Der RUN-Schritt braucht Netz fuer das gepinnte pypdf-Wheel.
  gateway_image=private-ai-p23-gateway:qa
  echo "Hinweis: Gateway-Build laedt pypdf==5.9.0 (nur Wheel) von PyPI."
  docker build --pull=false --tag "$gateway_image" ./gateway
  docker run --rm --network none --read-only \
    --user 10001:10001 --cap-drop ALL \
    --security-opt no-new-privileges \
    --entrypoint python "$gateway_image" -c '
import ast, pathlib, pypdf
for p in sorted(pathlib.Path("/app").glob("*.py")):
    ast.parse(p.read_text(encoding="utf-8"), str(p))
assert pypdf.__version__ == "5.9.0", pypdf.__version__
print("P2.3 isolated Gateway image/runtime: PASS (non-root, read-only, network none, pypdf 5.9.0)")
'
  echo "P2.3 Gateway QA image: $gateway_image"
fi
echo "P2.3 image build finished locally; no running Docker service changed."
