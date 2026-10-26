# Private AI Pipeline

Lokale, datenschutzorientierte KI-Plattform für einen Raspberry Pi 5 (ARM64) und optional einen ausdrücklich freigegebenen Ollama-Rechner im privaten Netzwerk. **Kein automatischer Cloud-Fallback.**

**Implementierungsstand: v0.5 / P2.3 (Entwicklung, 26.10.2026). Kein produktiver v1.0-Release.** Ein erfolgreicher Merge nach `main` ist eine Quellcode-Integration, keine Freigabe des produktiven Pi-Stacks. Die zugehörigen Freigabekriterien stehen in [Sicherheit](docs/SECURITY.md) und [P2.3-Testnachweisen](docs/V05_P23_RAG_CHAT.md).

## Architektur

```text
Browser
  ├─ Open WebUI ───────────────┐
  └─ Light Console (BFF) ─────┤ Authentifizierung / serverseitige Tokens
                              ▼
                    Private AI Gateway
                      ├─ /v1/models, /v1/chat/completions, /v1/embeddings
                      ├─ /private/knowledge (separates Knowledge-Token)
                      ├─ SQLite FTS5 / projektspezifische Namespaces
                      ├─ optionale lokale semantische Vektorsuche
                      └─ Ollama, nur fest konfigurierter privater Endpunkt

Separate CLI: lokales MCP stdio (standardmäßig nur lesen)
```

Die Browser-Oberfläche erhält weder `PIPELINE_TOKEN` noch `KNOWLEDGE_TOKEN`. Für die Light Console sind Login (scrypt), Session-Cookies, CSRF-/Origin-Prüfung und SSE-Streaming implementiert. Open WebUI besitzt eine eigene Benutzerverwaltung und unabhängigen Chatverlauf. Console-Chats verbleiben im aktuellen Browser-Tab.

## Funktionen und Grenzen

| Modul | Ist-Stand |
| --- | --- |
| Gateway und Modellinferenz | OpenAI-kompatible API zum lokalen Ollama, SSE, Modellliste, begrenzte Payloads |
| Light Console | Anmeldung, Statusdiagnose, Modellwahl, Chat, Dokumentensuche und opt-in Import |
| Gedächtnis | SQLite FTS5, Namensräume, Legacy-Migration, MCP stdio read-only als Standard |
| P2.1 PDF | Textbasierte PDFs mit max. 1 MiB, 16 Seiten und 96 KiB extrahiertem Text, Seitenprovenienz |
| P2.2 Semantik | Opt-in Embeddings (`nomic-embed-text` oder `bge-m3`), explizite CLI-Indizierung |
| P2.3 RAG | Opt-in Chat mit bis zu drei Dokumentfundstellen, SSE `rag_sources`, Quellcodes `[Q1]` ff. |
| Projektübergreifende Rechte | Nicht implementiert; **Single-Operator** und fester Knowledge-Namensraum |
| Scans/OCR, Tabellenanalyse | Noch nicht implementiert |
| Agenten-Schreibrechte | Nicht produktiv freigegeben |

**Wichtig:** Quellenkennungen belegen nur, welche Textausschnitte abgerufen wurden. Sie garantieren weder die Richtigkeit noch die Belegbarkeit jedes Satzes der generierten Antwort. Dokumentinhalt ist als unvertrauenswürdig zu behandeln.

## Sicherheitskonfiguration

Sichere Standardwerte aus `.env.example`:

```dotenv
MEMORY_INJECTION=false
MCP_READONLY=true
KNOWLEDGE_IMPORT_ENABLED=false
SEMANTIC_SEARCH_ENABLED=false
RAG_ENABLED=false
```

- Standard-Compose nutzt ein internes Docker-Netz und veröffentlicht keinen Gateway-Port; WebUI und Console sollen nur über Loopback erreichbar sein.
- `compose.lan.yaml` erlaubt bewusst einen zusätzlichen Netzwerkpfad. **Ohne Host-Firewall ist dies keine LAN-Allowlist und keine WAN-Isolation.**
- Es gibt keinen automatischen Embedding-Download beim Import; die semantische Indizierung wird ausdrücklich per CLI gestartet.
- Backup-Archive enthalten personenbezogene Daten und Konfigurationsschlüssel im Klartext. Sie sind bis zu einer gesicherten Off-Host-Verschlüsselung vertraulich zu behandeln.
- Keine automatischen Agenten-Schreibfreigaben; kein Docker-Socket in KI-Containern.

## Einrichtung (nur nach Host- und Backup-Prüfung)

```bash
# In einem geprüften lokalen Checkout, keine fremden Volumes löschen:
./scripts/init.sh
python3 console/set_password.py
./scripts/preflight.sh

# Vor dem Start: Konfiguration kontrollieren; erzeugt keine Container
docker compose -f compose.yaml -f compose.console.yaml --profile console config
```

Bei bestehenden Installationen vor einem Neustart `bash scripts/upgrade_env_p2.sh` durchführen und vorher `.env` sowie persistente Volumes sichern. **Nicht `docker compose down -v` verwenden.** Der produktive Pi kann bestehende lokale Bridge-/Loopback-Proxies benötigen; die Docker-Konfiguration allein beweist keine erfolgreiche Host-Portfreigabe.

Erst nach separater Betriebsfreigabe Container starten:

```bash
docker compose -f compose.yaml -f compose.console.yaml --profile console up -d --build
```

Ein externer LAN-Ollama-Host erfordert zusätzlich das geprüfte `compose.lan.yaml` und Host-Firewall-Regeln. Zugangsdaten nicht an Klartext-HTTP-Adressen außerhalb Loopback senden.

## Tests und CI

```bash
python3 -m unittest discover -s tests -v
node --check console/static/app.js
node --check console/static/login.js
node tests/test_chat_history.cjs
node tests/test_p23_browser.cjs
for script in scripts/*.sh; do bash -n "$script"; done
```

Der P2.3-Branch wurde auf dem Raspberry Pi mit **83 Python-Tests** und **23 DOM-Harness-Assertions** geprüft. Zusätzlich sind isolierte HTTP-, PDF- und lokale Ollama-/RAG-Smokes dokumentiert. Das DOM-Harness ist kein echter Browser; der Docker-HTTP-Test verwendet einen Modell-Simulator und beweist keinen Upstream-Inferenzabbruch.

Die GitHub-Actions-Workflowdatei `.github/workflows/ci.yml` prüft Python, JavaScript, Compose-Konfiguration und Shell auf x86_64 und ARM64. CI ersetzt weder die reale Pi-/Ollama-Hardwareabnahme noch Netz-/Restore-/Security-Tests.

## Noch offene Freigabekriterien

1. Egress-Allowlist am Host sowie unerwünschte DNS-/WAN-Verbindungen nachweislich blockieren.
2. Backup und Restore ausschließlich auf separaten Wegwerf-Volumes reproduzierbar prüfen.
3. Tatsächliche Beendigung der Upstream-Inferenz nach Client-Abbruch und Prompt-Injection-Härtung nachweisen.
4. Supply-Chain-Digests, Ressourcen- und Browser-E2E-Abnahme sowie Hermes-/Codex-MCP-Integration abschließen.

Weitere Details: [Roadmap](docs/ROADMAP.md), [Sicherheitskonzept](docs/SECURITY.md), [P1/P2-Dokumentation](docs/V05_P1_P2.md), [P2.3-Abnahme](docs/V05_P23_RAG_CHAT.md), [GitHub-Issues](docs/GITHUB_TRACKING.md) und [Entwicklungsregeln](AGENTS.md).
