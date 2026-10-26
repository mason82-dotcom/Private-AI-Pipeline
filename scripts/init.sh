#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ -e .env ]]; then
  echo 'Die bestehende .env bleibt unverändert.'
  exit 0
fi
python3 - <<'PY'
from pathlib import Path
import secrets
p = Path('.env.example').read_text(encoding='utf-8')
p = p.replace('PIPELINE_TOKEN=GENERATE_ME', 'PIPELINE_TOKEN=' + secrets.token_hex(32))
p = p.replace('WEBUI_SECRET_KEY=GENERATE_ME', 'WEBUI_SECRET_KEY=' + secrets.token_hex(32))
p = p.replace('KNOWLEDGE_TOKEN=GENERATE_ME', 'KNOWLEDGE_TOKEN=' + secrets.token_hex(32))
Path('.env').write_text(p, encoding='utf-8')
Path('.env').chmod(0o600)
PY
echo '.env mit zufälligen Geheimnissen erzeugt (Dateirechte 0600).'
