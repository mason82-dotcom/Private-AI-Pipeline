# P2.3 – Opt-in Dokumenten-Chat (lokales RAG mit Quellen)

**Status:** Implementierter Entwicklungsbranch, **nicht produktiv freigegeben**. Automatisierte Pi-Regression (Python/JavaScript) erfolgreich; echte ARM64-/Docker-/Ollama-End-to-End-Abnahme ausstehend. Baut auf P2.1 PDF und P2.2 Semantik auf.

## Funktion

Die Light Console bietet im normalen Chat ein ausdrücklich aktivierbares Kästchen **Mit Dokumenten antworten** und eine Suchmodi-Auswahl:
- **Volltext (FTS5)**: ohne laufendes Embedding-Modell, nur vorhandene lokale Dokumentabschnitte
- **Semantisch**: erfordert separat eingeschaltetes `SEMANTIC_SEARCH_ENABLED=true` und bereits durch Operator-CLI indizierte Dokumente, `nomic-embed-text` läuft lokal

Ablauf: Browser (bereits authentifiziert, Session + CSRF) → Console BFF → serverseitige Knowledge API mit `KNOWLEDGE_TOKEN` und festem `KNOWLEDGE_NAMESPACE` → max. 3 Quellen mit 360 Zeichen pro Auszug → serverseitig erstellte Systemnachricht mit ausdrücklich unvertrauenswürdigem Kontext → Streaming-Chat über bestehendes Gateway und lokales Ollama. Die Quellen erscheinen als **separate, nicht automatisch verifizierte Fundstellen** im Browser. Quellen-IDs `[Q1]`–`[Q3]` sind Hinweise für die Modellantwort, **keine Garantie**, dass die KI korrekt zitiert.

Ist RAG eingeschaltet und keine Fundstelle vorhanden, liefert die Console HTTP 409; bei gesperrter/fehlender Suche HTTP 403/503. **Kein stiller Rückfall zu unbelegtem Standardchat.** Der Nutzer kann RAG bewusst ausschalten.

## Konfiguration – sichere Voreinstellung

```dotenv
RAG_ENABLED=false
SEMANTIC_SEARCH_ENABLED=false
KNOWLEDGE_IMPORT_ENABLED=false
```

`RAG_ENABLED` wird ausschließlich in `compose.console.yaml` an die Console übergeben, keine automatisch beschreibbare Memory-Schnittstelle. Der Browser kann RAG nur über einen gültigen CSRF-geschützten Chat-Aufruf aktivieren. Er kann weder Namensraum noch Gateway-URL, Quellenkennung oder Systemnachricht selbst festlegen.

Bei `RAG_ENABLED=false` bleibt der bisherige Chat unverändert. RAG kann über FTS5 genutzt werden, auch wenn der semantische Suchmodus deaktiviert ist.

## Quellenanzeige und Grenzen

- Vorhandene UTF-8- und PDF-Textabschnitte werden aus SQLite FTS5 gelesen; Memory-Einträge werden nicht in den Retrieval-Pfad übernommen.
- PDF-Quellen enthalten den Textauszug sowie Dateiname und Seitennummer, sofern aus der P2.1-Extraktion vorhanden; die Original-PDF wird nicht dauerhaft vorgehalten.
- Browser zeigt **abgerufene** Quellen; er validiert nicht die Tatsachenbehauptungen der Modellantwort.
- Dokumenttext kann Prompt-Injections enthalten: Die Console kennzeichnet ihn gegenüber dem Modell als unvertrauenswürdig und führt daraus keine Befehle aus. Solche Anweisungen sind eine verbleibende LLM-Risikoquelle, keine formale Isolation.
- Kein externer Cloud-Fallback, kein automatisches Indexieren und keine neuen Host-Ports.
- Kleines `qwen3:0.6b` kann trotz Kontextaufbau Quellen übersehen oder falsch referenzieren. Gerade bei sehr geringem RAM/CTX müssen Antwortgenauigkeit, Latenz und Kontextüberschreitung auf echter Hardware geprüft werden.

## Tests (isolierter Entwicklungscheckout)

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git fetch origin
git switch --track origin/feature/p2-rag-chat-citations
.venv/bin/python -m unittest discover -s tests -p 'test_p2_rag.py' -v
.venv/bin/python -m unittest discover -s tests -v
node --check console/static/app.js
node tests/test_chat_history.cjs
git status -sb
```

Die Python-HTTP-Tests verwenden einen simulierten lokalen Ollama-Server mit echten Console- und Gateway-HTTP-Handlern. Zielabdeckung: Zugriff ohne Login / fehlendes CSRF / RAG-Flag OFF, abgesicherte Quellen nur aus festem Namespace, Custom-SSE-Quellen vor Modell-Tokens, unveränderter Standardchat, keine Quellen → fail-closed, nicht aktivierte semantische Suche → fail-closed.

**Keine Änderungen an produktiver Pi-Installation** für diese automatisierten Tests. Vor einer späteren Testinstallation: SQLite-Backup validieren, vorbereitende P2.1/2.2 PRs abnehmen und die laufenden Pi-Dienste/RAM/Swap prüfen. Kein `docker compose down -v`; keine Container-Neuerstellung ohne gesonderten Betriebsentscheid.

## Release-Gates

- [ ] Alle Tests auf Pi und GitHub-CI nachgewiesen erfolgreich
- [ ] ARM64-Build der veränderten Console-/Gateway-Images erfolgreich
- [ ] RAG mit echtem lokalem Ollama end-to-end inkl. SSE und sichtbaren Quellen
- [ ] Injektions- und Zitierqualitäts-Stichproben auf verschiedenen Dokumenten
- [ ] Modell-RAM/Swap-/Timeout-Messung beim sequentiellen Embedding- und Chat-Betrieb
- [ ] Herkunft/Status der Quellen und Auswirkung von Dokument-Updates geprüft
- [ ] Review und Merge-Kette: P2.1 PDF → P2.2 Semantik → P2.3 RAG


## Nachgewiesene Pi-Regression, 25.10.2026

- Separate P2.3-Tests: **5/5 bestanden** (3,727 s): RAG-Prompt-Begrenzung, fehlerhafte Quellen, Anmeldung/CSRF/Featureflag, SSE-Quellennachweis und normaler Chat, Fail-Closed-Verhalten.
- Gesamtsuite: **70/70 Python-Tests bestanden** (46,654 s), keine Fehler und keine übersprungenen Tests.
- JavaScript: Syntaxprüfung ohne Fehlermeldung, **11 Chat-Historie-/RAG-SSE-Regressionsfälle bestanden**.
- Git-Status am Pi: Branch `feature/p2-rag-chat-citations` auf `origin/...`, unversionierte `.agents/` und `skills-lock.json` vorhanden; Herkunft nicht bestätigt, nicht automatisch committen oder löschen.
- Diese Tests nutzen für RAG ein simuliertes Ollama; **kein** Nachweis für produktive Docker-Container, echten Qwen-RAG-Inferenzlauf oder PDF-Anzeige im Live-Browser.
