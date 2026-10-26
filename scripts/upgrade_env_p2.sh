#!/usr/bin/env bash
# Non-destructive additive environment migration: never replace an existing secret.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -f .env ]]; then
  echo 'Keine .env: zuerst scripts/init.sh ausführen.' >&2
  exit 2
fi
python3 - <<'PY'
from pathlib import Path
from secrets import token_hex
import os
import stat
p=Path('.env')
if not p.is_file() or p.is_symlink():
    raise SystemExit('Ungültige .env-Datei')
original=p.read_text(encoding='utf-8')
lines=original.splitlines()
values={k.strip():v.strip() for line in lines if '=' in line and not line.lstrip().startswith('#') for k,v in [line.split('=',1)]}
key=values.get('KNOWLEDGE_TOKEN')
if key is not None and (key=='GENERATE_ME' or len(key)<32):
    raise SystemExit('KNOWLEDGE_TOKEN ist unbrauchbar. Bitte manuell erneuern; andere Secrets bleiben unverändert.')
added=[]
if key is None:added.append('KNOWLEDGE_TOKEN='+token_hex(32))
if 'KNOWLEDGE_NAMESPACE' not in values:added.append('KNOWLEDGE_NAMESPACE=personal')
if 'KNOWLEDGE_IMPORT_ENABLED' not in values:added.append('KNOWLEDGE_IMPORT_ENABLED=false')
if added:
    # Preserve existing credentials; only add missing P2 fields.
    with p.open('a', encoding='utf-8') as f:
        if original and not original.endswith('\n'):f.write('\n')
        f.write('\n# Added by upgrade_env_p2.sh\n'+'\n'.join(added)+'\n')
os.chmod(p,stat.S_IRUSR|stat.S_IWUSR)
print(f'P2-Konfiguration geprüft; {len(added)} fehlende Einträge ergänzt. Keine bestehenden Tokens verändert.')
PY
