# P2.3 – Optionale lokale Chat-Antworten mit Dokumentquellen

**Status: Draft / Entwicklung.** P2.3-Regression auf dem Raspberry Pi bestanden: 79 Python-Tests, JavaScript-Syntax und 11 Chat-/RAG-SSE-Fälle mit Exit-Code 0. Der isolierte Live-API-Smoke gegen echtes lokales `qwen3:0.6b` ist ebenfalls bestanden (28,35 s); Docker-/Browser-End-to-End-Abnahme und GitHub-CI stehen weiterhin aus. Keine Änderungen am produktiven Raspberry-Pi-Stack.

## Funktionen

- Standardmäßig **aus** (`RAG_ENABLED=false`), unabhängig von `SEMANTIC_SEARCH_ENABLED` und `KNOWLEDGE_IMPORT_ENABLED`.
- Nach Anmeldung und CSRF-Prüfung kann der Benutzer in der **Light Console → Chat** „Mit Dokumenten antworten“ einschalten.
- Abfrage über die bereits vorhandene Knowledge-API unter der **serverfesten** `KNOWLEDGE_NAMESPACE`, keine frei wählbare Namespace-/URL-Option im Client.
- Modus **Volltext** (FTS5) oder **Semantisch** (vorher explizit indizierte Embeddings vorausgesetzt).
- Höchstens drei kurze Textstellen à 360 Zeichen. Keine Erinnerungen, externen Suchmaschinen, Dateischreibzugriffe oder Cloud-Fallbacks.
- Zuerst wird die Wissenssuche abgewickelt, danach die Chat-Modellabfrage; keine gleichzeitige Suche und LLM-Inferenz auf Kosten des Pi-RAM.
- Quellen-IDs `[Q1]` bis `[Q3]`; vorhandene Dateinamen und PDF-Seitenzahlen werden mitgeführt.
- Die Console zeigt **abgerufene Fundstellen**, nicht kryptografisch überprüfte Modellzitate. Sie werden als „nicht automatisch verifiziert“ gekennzeichnet.
- Bei keiner Fundstelle (HTTP 409), ausgeschalteter Funktion (403), nicht bereitem semantischem Index (409) oder fehlender lokaler Wissens-API (503) wird **keine unbelegte RAG-Antwort** gestartet.
- Server entschärft den Prompt: Dokumente werden als unvertrauenswürdige Daten gekennzeichnet; System-/Rollenanweisungen aus Dokumenten sollen ignoriert werden. Dies ist kein absoluter Schutz vor Prompt Injection.
- Bestehender Chat ohne RAG bleibt unverändert; keine dauerhafte eigene Chat-Historie.

## Konfiguration

```dotenv
# Zu Testzwecken bewusst und separat freischalten, Standard false
RAG_ENABLED=false
# Für semantische Suche zusätzlich (sonst FTS5 verwenden)
SEMANTIC_SEARCH_ENABLED=false
SEMANTIC_MODEL=nomic-embed-text:latest
```

Das Flag wird nur an den Console-Container übergeben. `KNOWLEDGE_TOKEN` muss bereits serverseitig gesetzt sein. `KNOWLEDGE_IMPORT_ENABLED` ist zum *Lesen* bereits vorhandener Dokumente nicht erforderlich. Die Console-Dockerdatei enthält nun `rag.py`. Die UI greift auf die authentifizierte Route `GET /api/rag-config` zu.

Für RAG ausschließlich mit Dokumentquellen empfehlen wir `MEMORY_INJECTION=false` beizubehalten; die Gateway-weite Memory-Injection ist eine separate Option und könnte anderenfalls weiteren Kontext hinzufügen.

## Isolierte Pi-Tests ohne Containeränderungen

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git fetch origin
git switch -c feature/p2-rag-chat-citations --track origin/feature/p2-rag-chat-citations
.venv/bin/python -m unittest discover -s tests -p 'test_p23_rag.py' -v
.venv/bin/python -m unittest discover -s tests -v
node --check console/static/app.js
node --check console/static/login.js
node tests/test_chat_history.cjs
git status -sb
```

Bei bereits vorhandenem lokalen Branch statt `switch -c` `git switch feature/p2-rag-chat-citations && git pull --ff-only` verwenden.

Die `test_p23_rag.py`-Tests verwenden ausschließlich Loopback mit simuliertem Ollama. Sie prüfen Autorisierung, CSRF, deaktivierte Funktion, Herkunft der Quellen, Namensraumtrennung, unveränderten Standard-Chat, ungültige Optionen und leere Treffer. Ein echter Docker-/Browser-/RAG-Modelltest ist ein **separates Freigabe-Gate**. Es ist ausdrücklich nicht nötig, das Feature für die Tests in der Produktions-`.env` einzuschalten.

## Release-Gates

- [x] Pi-Python-Gesamtlauf inklusive P2.3: 79 Tests in 58,193 Sekunden, Exit-Code 0 (26.10.2026, Nutzerprotokoll)
- [x] Chat-Kontext- und RAG-SSE-JavaScript-Regression: 11/11 bestanden; JavaScript-Syntaxcheck Exit-Code 0 (26.10.2026, Nutzerprotokoll)
- [ ] CI-Lauf auf GitHub bestätigt
- [ ] Echtes mehrseitiges PDF mit Seitenangabe in Chat geprüft
- [ ] Semantische RAG-Suche mit echtem Modell (Latenz, Speicher, Ausfallverhalten)
- [x] Isolierter Live-API-Smoke: Authentifizierung, serverfestes Scope, SSE-Quellen und lokale Ollama-Antwort mit `[Q1]` geprüft
- [ ] Vollständige Docker-/Browser-End-to-End-Abnahme einschließlich CSP und Stream-Abbruch geprüft
- [ ] Manuelle Review: Prompt-Injection, Quellenidentität, Egress und Last
- [ ] Vorgelagerte P2.1 und P2.2 PRs gemergt

**Kein automatischer Deploy oder Merge.**

## Pi-Testnachweis vom 26.10.2026

- Vorläufiger Stand: `Ran 71 tests in 47.227s` / `OK`.
- Aktualisierter vollständiger Stand: `Ran 79 tests in 58.193s` / `OK`, Python Exit-Code 0.
- JavaScript: `Chat context and RAG SSE regression tests OK (11 cases)`.
- Beim früheren Stand war der Checkout fünf Commits hinter `origin`; danach erfolgte ein Fast-Forward. Der gemeldete erfolgreiche 79-Test-Lauf bezieht sich auf den aktualisierten P2.3-Stand **vor dem Hinzufügen des Live-Smoke-Skripts und dieser Dokumentationsänderung**.
- Unversionierte lokale Dateien `.agents/` und `skills-lock.json` wurden gemeldet. Diese nicht automatisch löschen, überschreiben oder committen.
- Keine realen RAG-Antworten des Ollama-Chatmodells, keine Container-/Browserabnahme und kein Produktiv-Deploy nachgewiesen.

## P2.3 isolierter Live-API-Smoke mit echtem lokalem Ollama (bestanden)

Der neue Test `scripts/pi-p23-rag-live-smoke.py` startet **nur zwei temporäre Python-HTTP-Server auf zufälligen 127.0.0.1-Ports** (Gateway und Light Console), verwendet eine SQLite-Datenbank in `tempfile.TemporaryDirectory`, erstellt nur Testdokumente und zufällige In-Memory-Schlüssel und verbindet sich mit dem **bereits laufenden lokalen** Ollama `127.0.0.1:11434`. Er nutzt ausschließlich die FTS5-Dokumentensuche, kein zusätzliches Embedding-Modell und keinen Docker-Container.

Vorbereitung: freien RAM und Swap sowie `ollama ps` und `ollama list` prüfen, keine großen Modelle zeitgleich laufen lassen. Kein Modell-Download; der Test lehnt nicht installierte Modellnamen vor der Inferenz ab.

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git fetch origin
git pull --ff-only origin feature/p2-rag-chat-citations
.venv/bin/python -m py_compile scripts/pi-p23-rag-live-smoke.py
.venv/bin/python scripts/pi-p23-rag-live-smoke.py --model qwen3:0.6b \
  > /tmp/p23-rag-live-smoke.log 2>&1
rc=$?
tail -30 /tmp/p23-rag-live-smoke.log
echo "Live-Smoke Exit-Code: $rc"
```

Exit-Code **0**: Transport, geschützter Login/CSRF, scoping, SSE-Quelle und Modellzitat `[Q1]` nachgewiesen. **3**: Modell hat Text geliefert, aber `[Q1]` nicht in der Antwort verwendet; dies ist ein begrenzter Modell-Qualitätsbefund, kein Beweis für einen defekten API-Transport. **2**: gewähltes Chatmodell ist nicht lokal installiert. **1**: anderer Fehler; Protokoll prüfen.

Der Test ist ein echter lokaler **API-Smoketest**, keine produktive Bereitstellung, keine Docker-Abnahme und kein vollständiger Browser-UI-Test. Eine positive Quelle in SSE belegt außerdem noch nicht die Richtigkeit aller generierten Aussagen.

## Live-Abnahmenachweis vom 26.10.2026

**Lauf:** `scripts/pi-p23-rag-live-smoke.py --model qwen3:0.6b` auf dem Raspberry Pi 5.

- Exit-Code: **0**, `P2.3 LIVE RAG API SMOKE: PASS`.
- Modell vor Start bereits installiert: `qwen3:0.6b`.
- Verwendet: temporäre SQLite-Datenbank, serverfester Namensraum und zwei isolierte Loopback-HTTP-Server; keine Docker-Neustarts oder produktiven Datensätze.
- Login/CSRF → Console → Gateway → lokales Ollama: **PASS**.
- Scope-Prüfung, genau eine abgerufene Quelle `[Q1]`, SSE-Abschluss: **PASS**.
- Gemessene Laufzeit: **28,35 Sekunden**, einschließlich Modellantwort (kein isolierter P50/P95-Latenzwert).
- Modellantwort enthielt `[Q1]`: **YES**.
- Qualitätshinweis: Die Modellantwort nannte fälschlich/ungenau eine direkte Bewegung der Zylinder durch die Hydraulikpumpe und vermischte die Erklärung mit irrelevanten Testtextbestandteilen. Die Quelle beschreibt technisch präziser: Die Pumpe **erzeugt Öldruck**; dieser bewegt über die Hydraulikzylinder den Ausleger. Daher **Transport-/Zitationsabnahme bestanden, fachliche Antwortqualität nur eingeschränkt bestätigt**. Eine vorhandene Zitiermarkierung validiert den Antwortinhalt nicht.

Weiter offen: semantischer RAG-Pfad mit echtem Embedding-Modell, mehrseitiges echtes Text-PDF mit Seitenprovenienz, Docker/Browser UI, Stream-Abbruch und CI. Kein Merge und keine Produktionsfreigabe.
