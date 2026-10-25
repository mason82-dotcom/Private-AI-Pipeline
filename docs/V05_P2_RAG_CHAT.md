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

## P2.3 echter Pi-FTS5-RAG-Smoke (neu; Ausführung steht aus)

Ein vollständig isolierter Hardwaretest ohne Deployment steht im Feature-Branch unter `scripts/p2_rag_live_smoke.py`.

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations
.venv/bin/python -m py_compile scripts/p2_rag_live_smoke.py
.venv/bin/python scripts/p2_rag_live_smoke.py
```

**Voraussetzung:** Ein bereits lokal installiertes `qwen3:0.6b` und ein laufendes Ollama unter `http://127.0.0.1:11434`. Das Skript verwendet die bestehende virtuelle Umgebung und installiert oder lädt nichts herunter.

**Abgrenzung:** Für den Smoke-Test werden Console/Gateway aus dem Entwicklungscheckout an **zufälligen lokalen Loopback-Ports** gestartet; SQLite wird ausschließlich im temporären Verzeichnis erzeugt. Es werden frische Test-Tokens und ein Testpasswort erstellt; `.env`, produktive Volumes und laufende Docker-Dienste werden nicht verändert. Die Test-PDF mit zwei Seiten wird im Arbeitsspeicher erzeugt und durch die echte P2.1-Extraktion indiziert. Echte Ollama-Inferenz erfolgt **einmal** mit `qwen3:0.6b`.

**Vorabbruch:** Der Test startet keine Inferenz, wenn weniger als etwa 1,43 GiB Arbeitsspeicher verfügbar sind, das Modell nicht installiert ist oder ein anderes Modell bei Ollama geladen ist. Keine fremden Modelle automatisch entladen.

**Anforderungen für PASS:** CSRF-Sperre, HTTP 409 bei leerer RAG-Fundstelle, echte PDF-Quellenkennung und **Seite 2**, getrennte Namespaces/Memory-Ausschluss im Quellennachweis, gültiger SSE-Abschluss `[DONE]` und nichtleere Modellantwort. Ausgegeben werden Antwortzeit, kurze Modellantwort sowie `Quellenzitat im Modelltext: True/False`. **Dieses Zitat ist ein separates Qualitätsmerkmal und keine zwingende Bedingung für den Transport-PASS.**

**Wichtige Grenze:** Auch ein erfolgreicher Test ist kein Docker-Image-Build und keine Live-Browser-/Produktivfreigabe. Dieser E2E-Smoke belegt die realen HTTP-Server- und Modellpfade ohne neue Ports von außen.

## Echte Pi-Abnahme: 25.10.2026 – Transport bestanden, RAG-Qualität offen

**Echter Ollama-Test mit `qwen3:0.6b`:**

- Temporäre Datenbank, zwei Seiten PDF, FTS5-Gateway und authentifizierte Light Console über Loopback erfolgreich.
- Richtige Fundstelle: `rag-hardwaretest.pdf`, **Seite 2**, Kennung `[Q1]`.
- SSE vollständig, **52 Zeichen** Modellantwort in **27,7 s**; gesamte Testdauer **28,2 s**.
- RAM verfügbar: **3,42 → 2,76 GiB**; Swap belegt: **3,71 → 3,79 GiB**. Dies sind Momentaufnahmen, keine Spitzenlastmessung.
- **Qualitätsmangel:** Die Antwort lautete *„Die gefundenen Dokumente belegen dazu keine Antwort.“* und enthielt kein `[Q1]`, obwohl die relevante PDF-Seite den Zusammenhang zwischen Hydraulikpumpe, Drucköl und Baggerzylindern beschreibt.
- Daher **Transport-PASS**, aber **Antwortqualitäts-Gate NICHT bestanden**. Weder produktiver Einsatz noch PR-Merge sind dadurch freigegeben.

**Korrekturen im Branch:** Die kurze RAG-Systemnachricht fordert jetzt eine konkrete Antwort aus der Quelle, ohne die frühere Ablehnungsformulierung als wörtliche Vorlage anzubieten. Das echte Pi-Smoke-Skript bewertet nun das konkrete Testbeispiel separat: Antwort enthält `Druck`, `Zylinder`, die richtige Quellen-ID `[Q1]` und keine ungegründete Ablehnung. Dies ist **nur eine Fixture-Prüfung, keine allgemeine Halluzinationsdetektion**. Der Test gibt RAM- und Swap-Werte auch dann aus, wenn die Qualitätsprüfung fehlschlägt. Neue Tests und der echte Modelllauf nach der Änderung stehen aus.

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations
.venv/bin/python -m unittest discover -s tests -p test_p2_rag.py -v
.venv/bin/python -m unittest discover -s tests -v
node --check console/static/app.js
node tests/test_chat_history.cjs
.venv/bin/python scripts/p2_rag_live_smoke.py
```

**Abnahme nur dann:** Transport und Fixture-Qualität beide PASS, außerdem weiterhin keine Namensraum-/Memory-Leaks und keine unzulässige Modell- oder Containeränderung.

## Wiederholungstest nach RAG-Prompt-Korrektur – PASS (25.10.2026)

**Die zuvor dokumentierte inhaltliche Nicht-Antwort ist im Wiederholungstest behoben.** Dieser Abschnitt ergänzt den historischen Erstlauf, statt ihn zu überschreiben.

- Sechs gezielte P2.3-Regressionsfälle: **6/6 PASS**, Laufzeit 3,240 s. Der zusätzliche Test `test_fixture_requires_evidence_and_matching_citation` prüft das spezifische Bagger-Hydraulik-Beispiel.
- Reale lokale Ollama-Inferenz mit `qwen3:0.6b`, temporärer SQLite-Datenbank und zweitseitiger Test-PDF: `rag-hardwaretest.pdf`, Seite 2, Quellen-ID `Q1`.
- Tatsächlich generierte Antwort: *„Die Hydraulikpumpe erzeugt Druckoel für die Baggerzylinder. [Q1]“*
- **`P2.3 REAL LOCAL FTS5 RAG TRANSPORT: PASS`** und **`P2.3 FIXTURE ANSWER QUALITY: PASS`**.
- SSE-Text 64 Zeichen; gemessene Antwortzeit 24,1 s; gesamte Skriptlaufzeit 25,3 s.
- Vorher: RAM verfügbar 3,52 GiB, Swap belegt 3,74 GiB. Nachher: RAM verfügbar 2,78 GiB, Swap belegt 3,74 GiB. Keine Spitzenlastmessung.
- Die positive Qualitätsbewertung gilt für **diese konkrete Testfrage**, nicht als allgemeiner Nachweis korrekter KI-Zitate, Halluzinationsfreiheit oder gegen Prompt-Injection.

**Offen trotz PASS:** Python-Gesamtsuite nach der neuen Qualitätsprüfung erneut ausführen und GitHub-CI bestätigen; ARM64-Docker-Images bauen; isolierten Live-Browsertest durchführen; mehrere unterschiedliche Dokumente, gezielte adversarielle Beispiele und Wiedergabe nach Dokument-Updates prüfen. Produktive Pi-Container und das bestehende Memory-Volume bleiben unverändert. Ein Merge darf erst nach Review und den übrigen Release-Gates erfolgen.

## Pi-Regressionsabnahme nach der Qualitätskorrektur (25.10.2026)

- **71/71 Python-Tests PASS**, vollständiger `.venv/bin/python -m unittest discover -s tests -v`-Lauf in **47,240 Sekunden**, **keine Fehler und keine übersprungenen Tests**.
- `node --check console/static/app.js` ohne Fehler; `node tests/test_chat_history.cjs`: **11/11 Chat-Historie-/RAG-SSE-Fälle PASS**.
- Getesteter Checkout: `feature/p2-rag-chat-citations`, Stand `9e61c96`.
- **Testabdeckung:** einschließlich PDF-Import mit Seitenfundstelle, FTS5, semantischer Suche mit Fake-Embedding, abgesichertem RAG-SSE-Endpunkt, sicherem Fehlerfall und konkreter Qualitätstest-Fixture.
- **Abgrenzung:** Die gesamten Python-Tests nutzen größtenteils simulierte Server; der zuvor separat bestandene reale Ollama-Smoke bleibt ein einzelner Inhaltsfall. GitHub Actions liefert für den aktuellen Commit noch keine bestätigten Workflow-Runs/Statusprüfungen. ARM64-Docker-Build und Browserintegration weiterhin offen.

### Nächste isolierte Docker-Bauprüfung

Aus dem Entwicklungscheckout; **kein** `docker compose up`, `down`, `--force-recreate` oder `docker system prune`:

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
free -h
df -h .
docker system df

docker build --pull=false -f gateway/Dockerfile -t private-ai-p23-gateway:qa ./gateway
docker build --pull=false -f console/Dockerfile -t private-ai-p23-console:qa ./console

docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --entrypoint python private-ai-p23-gateway:qa \
  -c "import gateway, knowledge, semantic, pdf_ingest, pypdf; print('GATEWAY_IMAGE_IMPORT_OK')"

docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --entrypoint python private-ai-p23-console:qa \
  -c "import server, rag; print('CONSOLE_IMAGE_IMPORT_OK')"
```

`docker build` erzeugt nur zusätzlich markierte Images; es ersetzt keine laufenden Container. Neue Base-Layer und die gepinnte `pypdf`-Abhängigkeit können heruntergeladen werden, falls nicht gecacht. Vor dem Bau freien Platz/RAM prüfen; bei Knappheit den Bau überspringen. Die einmaligen `docker run`-Checks verwenden kein Netzwerk, keine Volumes und starten keine Server. Images nach dem Test nicht ohne weitere Prüfung produktiv einsetzen; Basisimage-Pinning, Security-Review und isolierte Browserabnahme sind offen.

## Release-Gates

- [x] Vollständige Pi-Python- und JavaScript-Regression nach der Qualitätskorrektur nachgewiesen (71 + 11 Fälle)
- [ ] GitHub-CI-Gesamtlauf nachgewiesen erfolgreich
- [ ] ARM64-Build der veränderten Console-/Gateway-Images erfolgreich
- [x] Isolierter lokaler FTS5-RAG-E2E-Smoketest mit echtem Ollama, SSE, PDF-Seite 2 und passendem Quellenzitat (ein Testfall); Live-Browser-Abnahme weiterhin offen
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
