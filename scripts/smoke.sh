#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
echo 'Prüfung: Gateway-Status und lokale Ollama-Modellliste ...'
docker compose exec -T gateway python - <<'PY'
import json
import os
import urllib.error
import urllib.request
base = 'http://127.0.0.1:8000'
with urllib.request.urlopen(base + '/health', timeout=5) as r:
    assert json.load(r)['status'] == 'ok'
print('Gateway: OK')
req = urllib.request.Request(base + '/v1/models', headers={'Authorization': 'Bearer ' + os.environ['PIPELINE_TOKEN']})
try:
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
        assert isinstance(data['data'], list)
        print('Ollama: erreichbar; geladene Modelle:', ', '.join(x.get('id','?') for x in data['data']) or '(keine)')
except urllib.error.HTTPError as exc:
    print('Ollama/Gateway: Fehlerstatus', exc.code)
    raise SystemExit(1)
PY
