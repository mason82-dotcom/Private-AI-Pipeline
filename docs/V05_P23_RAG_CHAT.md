# P2.3 – Optionale lokale Chat-Antworten mit Dokumentquellen

**Status: Draft / Entwicklung.** P2.3-Regression auf dem Raspberry Pi bestanden: 79 Python-Tests, JavaScript-Syntax und 11 Chat-/RAG-SSE-Fälle mit Exit-Code 0. Isolierte Live-API-Smokes für FTS5-RAG (28,35 s) und semantischen RAG mit `nomic-embed-text` + `qwen3:0.6b` (3,73 s Index, 35,25 s API/Chat) bestanden. Der isolierte PDF-RAG-End-to-End-Test ist ebenfalls bestanden (26,93 s, korrekte Seite 2). Docker-/Browser-End-to-End-Abnahme und GitHub-CI stehen aus. Keine Änderungen am produktiven Raspberry-Pi-Stack.

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
- [x] Echtes generiertes dreiseitiges Text-PDF über authentifizierten Import, PDF-Worker, Volltextsuche und RAG-Chat mit Quellenbeleg Seite 2 geprüft (Pi, Exit-Code 0)
- [x] Simulierte und reale semantische RAG-Suche auf dem Pi bestanden
- [x] Semantische RAG-Suche mit echten lokalen Modellen; 2/2 Vektoren, korrektes Ranking, [Q1] zitiert; gemessene Index-/Gesamtdauer
- [ ] Speicherlast und Ausfall-/Abbruchverhalten bei semantischen RAG-Anfragen separat prüfen
- [x] Isolierter Live-API-Smoke: Authentifizierung, serverfestes Scope, SSE-Quellen und lokale Ollama-Antwort mit `[Q1]` geprüft
- [x] Isolierter Docker-HTTP-Test: Login, CSP, CSRF, Origin, Testimport, Namespace, SSE `[Q1]`, Non-RAG-Chat und Erreichbarkeit nach Client-Disconnect; Exit-Code 0 (26.10.2026)
- [x] DOM-basierte JavaScript-Regression mit tatsächlicher `app.js`: 23 Assertions (26.10.2026)
- [x] Aktualisierte Python-Gesamtsuite: 83/83 bestanden, 60,865 Sekunden (26.10.2026)
- [ ] Echter Browser-Test einschließlich Layout/CSP und tatsächlicher Upstream-Abbruchmechanik
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

## Semantischer Live-RAG-Smoke (auf Pi bestätigt)

Dieser Modus erweitert den **bereits erfolgreich getesteten** FTS-Live-Smoke. Er indiziert **genau zwei temporäre Testchunks** (Hydraulik und Apfelkuchen) mit dem lokalen `nomic-embed-text:latest` und verwendet die vorhandene Console-/Gateway-/Ollama-Kette im semantischen Modus. Die semantische Abfrage muss die passende Hydraulikquelle vor dem themenfremden Apfelkuchen ranken. Der Index liegt ausschließlich in der temporären SQLite-Datei. Es werden keine produktiven Dokumente importiert, kein Docker-Service verändert, keine Cloud-Abfragen gestellt und **keine Modelle heruntergeladen**.

Prüfe zunächst Ressourcen und installierte Modelle:

```bash
free -h
ollama ps
ollama list | grep -E '^(nomic-embed-text|qwen3:0.6b)'
```

Führe danach den aktualisierten Branch und zunächst die gezielten Simulationen aus:

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations
.venv/bin/python -m unittest discover -s tests -p 'test_p23_rag.py' -v
.venv/bin/python -m py_compile scripts/pi-p23-rag-live-smoke.py
```

Echter lokaler Embedding- und RAG-Test (vorhandenes `qwen3:0.6b` und `nomic-embed-text:latest` vorausgesetzt):

```bash
.venv/bin/python scripts/pi-p23-rag-live-smoke.py \
  --mode semantic \
  --model qwen3:0.6b \
  --embed-model nomic-embed-text:latest \
  > /tmp/p23-semantic-rag-live.log 2>&1
rc=$?
echo "Exit-Code: $rc"
tail -45 /tmp/p23-semantic-rag-live.log
```

Erwartete Prüfmarker bei Erfolg:

- `Semantic index: PASS (2/2 test chunks)`
- `Semantic ranking: Hydraulik [Q1] before Apfelkuchen [Q2]: PASS`
- `Authenticated Console → Gateway → local Ollama: PASS`
- `Isolated namespace, source [Q1] ranked first: PASS`
- `SSE completed: PASS`
- `Model used [Q1] in answer: YES`
- `P2.3 SEMANTIC RAG API SMOKE: PASS`

Die Ausgabe enthält **Indizierungsdauer** und **Gesamtdauer von Wissensabfrage bis gestreamter Chat-Antwort**. RAM/Swap werden dabei nicht dauerhaft mitgeschnitten; beobachte sie bei Bedarf separat. Das Embedding-Modell kann nach der Indizierung noch im Ollama-Speicher verbleiben; die Operationen laufen **sequenziell**, sind aber nicht zwingend speicherexklusiv. Die Qualität der generierten Erklärung muss anhand des tatsächlichen Texts überprüft werden.

Exit-Code `3` bedeutet, dass die Quellenmarkierung in der Modellantwort fehlt (fachliches Qualitätsgate), `2` ein fehlendes lokal installiertes Modell und `1` einen anderen Testfehler. Der isolierte FTS-Test bleibt rückwärtskompatibel: ohne `--mode` wird weiterhin `fts` verwendet.

> Diese Änderungen wurden auf GitHub veröffentlicht, sind aber weder auf echter Pi-Hardware noch im produktiven Docker-Stack freigegeben. Zuerst Testprotokoll bewerten, anschließend separates Docker-/Browser-/PDF-Gate.

## Semantische Live-Abnahme vom 26.10.2026

Durchgeführt auf dem Raspberry Pi 5 mit `scripts/pi-p23-rag-live-smoke.py --mode semantic --model qwen3:0.6b --embed-model nomic-embed-text:latest`:

- Exit-Code **0**, `P2.3 SEMANTIC RAG API SMOKE: PASS`.
- Temporärer semantischer Index **2/2 Chunks**, **3,73 Sekunden**.
- Ranking **Hydraulik [Q1] vor Apfelkuchen [Q2]**, PASS.
- Authentifizierte Console → Gateway → Ollama, serverfestes Namespace-Scope, SSE-Abschluss, Modell-Zitierung `[Q1]`: PASS.
- Vollständige semantische Abfrage + Chatantwort **35,25 Sekunden**; nicht direkt mit FTS5-Latenz gleichzusetzen (Kalt-/Warmzustand und Last nicht kontrolliert).
- Antwort: `Die Hydraulikpumpe des Baggers erstellt Öldruck, welches mit den Hydraulikzylinder zum Bewegen des Auslegeres eingesetzt wird. [Q1]`.
- Fachlich im Kern richtig, sprachlich unpräzise. Zitationsmarker bestätigt **keine faktische Verifikation** der einzelnen Formulierungen.
- Zum Zeitpunkt des semantischen Testlaufs noch nicht nachgewiesen: PDF-Textextraktion mit Seitenzahl im Live-Chat (inzwischen separat bestanden), Produktions-Docker-/Browserpfad, CI, Belastung und Prompt-Injection-Härtung.

## Realer dreiseitiger PDF-RAG-Test (auf Pi bestanden)

Mit `scripts/pi-p23-pdf-live-smoke.py` wurde ein gesonderter, isolierter Test für die letzte offene PDF-Lücke ergänzt. Der Test erzeugt ein echtes, dreiseitiges PDF mit suchbaren Helvetica-Textobjekten **nur im Arbeitsspeicher**, ohne Benutzerdateien zu verarbeiten. Der PDF-Import verläuft über den authentifizierten Console-Endpunkt `POST /api/documents/import` und den vorhandenen Gateway-PDF-Worker (`pypdf`), nicht über eine simulierte Importfunktion.

Prüfungen: fehlender CSRF-Header führt zu HTTP 403; Import erzeugt drei Seiten-Chunks; Volltextsuche findet `Hydraulikpumpe` **ausschließlich auf Seite 2**; RAG-Chat verwendet nur den serverfesten Test-Namensraum; das Quellenereignis transportiert `[Q1]`, den Dateinamen und `page: 2`; SSE endet vollständig; lokales `qwen3:0.6b` liefert Antworttokens und soll `[Q1]` nennen. Alle Testdaten und Schlüssel existieren nur temporär.

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations
.venv/bin/python -m py_compile scripts/pi-p23-pdf-live-smoke.py

.venv/bin/python scripts/pi-p23-pdf-live-smoke.py \
  --model qwen3:0.6b \
  > /tmp/p23-pdf-rag-live.log 2>&1
rc=$?
echo "Exit-Code: $rc"
tail -40 /tmp/p23-pdf-rag-live.log
```

Die virtuelle Python-Umgebung muss bereits `pypdf==5.9.0` enthalten, wie für die vorhandene PDF-Regressionssuite. Der Test verwendet weder bestehende SQLite-Volumes noch Compose, startet keine Cloud-Dienste und lädt keine Modelle herunter. Exit-Code 0: PDF-Import + Seitenprovenienz + lokales Modellzitat bestätigt; 3: Modellzitat fehlt, technischer Transport ggf. trotzdem erfolgreich; 2: Chatmodell nicht installiert; 1: technischer Abbruch oder Prüfungsfehler. Die tatsächliche Antwortqualität ist gesondert zu beurteilen.

**PDF-Live-Gate bestanden am 26.10.2026.** Ein generiertes dreiseitiges Text-PDF prüft den Original-Textlayer-Pfad, nicht Scans/OCR oder beliebige komplexe Layouts. Docker-/Browser- und CI-Gates bleiben offen.

## Mehrseitige PDF-Live-Abnahme vom 26.10.2026

**Durchgeführt:** `scripts/pi-p23-pdf-live-smoke.py --model qwen3:0.6b` auf Raspberry Pi 5.

- Exit-Code **0**, `P2.3 PDF LIVE RAG SMOKE: PASS`.
- Echtes generiertes Text-PDF: **3 Seiten, 1408 Bytes**, nur temporäre SQLite-Datenbank und Loopback.
- Authentifizierter PDF-Import und CSRF-Gate: **PASS**.
- FTS5-Seitenprovenienz: Schlüsselwort `Hydraulikpumpe` korrekt auf **Seite 2**, **PASS**.
- SSE-Quellennachweis `[Q1]` mit `hydraulik-dreiseitig.pdf` und `page: 2`: **PASS**.
- SSE abgeschlossen, serverfester Namensraum: **PASS**; lokales `qwen3:0.6b` lieferte Antwort mit `[Q1]`.
- Gemessene vollständige Chat-/RAG-Antwortdauer: **26,93 Sekunden**.
- Antwortqualität: `Die Hydraulikpumpe erzeugt Oeldruck und bewegt den Baggerausleger durch den Oeldruck aus den Hydraulikzyanl. [Q1]`. Der letzte Fachbegriff ist verstümmelt, und Pumpe/Zylinder sind nicht sauber differenziert. Quellenmarker ist **kein Faktencheck**.
- **Abnahmegrenze:** echtes Textlayer-PDF, aber künstlich erzeugte Testdatei; Scans, komplexe PDFs, echte Browser-/Docker-Bereitstellung und Security-Review nicht nachgewiesen. Kein Produktionsdeploy.

## P2.3 GUI-/Docker-Gate ohne Produktiveingriff (neu; noch nicht auf Pi ausgeführt)

Es gibt zwei neue, bewusst getrennte Teststufen:

1. `tests/test_p23_browser.cjs` lädt **die tatsächliche** `console/static/app.js` in eine kontrollierte Node-VM mit simuliertem DOM/Fetch. Verifiziert RAG-Opt-in/Deaktivierung, HTML-Escaping von Dateinamen und Quellentexten, PDF-Seite, SSE-Fragmentierung, vollständiges Streamende, Browser-Abbruch und Ausschluss abgebrochener Turns aus dem nächsten Chat-Kontext. **Dies ist kein echter Browser-/Screenshot-Test**.
2. `scripts/pi-p23-console-image-check.sh` validiert ausschließlich die synthetische Compose-Konfiguration aus einem temporären Env-File: Console RAG-Opt-in, an `127.0.0.1` gebundener Port, internes Bridge-Netz, Read-only-Rootfs, gesperrte Linux-Capabilities. `docker compose config` startet, stoppt, baut und aktualisiert **keine** bestehenden Services. Optional `--build` prüft einen **separaten lokalen** QA-Image-Build und führt Python-Importe in einem isolierten Container aus (`--network none`, `--read-only`, User 10001); der Base-Image-Cache für `python:3.13-slim` ist dafür zwingend erforderlich. Wenn nicht vorhanden, wird ohne Download abgebrochen.

```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations

node --check console/static/app.js
node tests/test_chat_history.cjs
node tests/test_p23_browser.cjs

bash scripts/pi-p23-console-image-check.sh

# Nur optional, nur wenn bereits python:3.13-slim im Docker-Cache:
# bash scripts/pi-p23-console-image-check.sh --build

.venv/bin/python -m unittest discover -s tests -q
```

Vor optionalem Build `docker image inspect python:3.13-slim` zur Sichtprüfung. Bitte **kein** `docker compose up`, `down`, `restart`, `pull` oder Test-Deployment gegen das produktive Compose-Projekt ausführen. Der Test schreibt lediglich lokale Logdateien/temporäre Testdaten und beim optionalen Build ein separates QA-Image. Die unversionierten Dateien `.agents/` und `skills-lock.json` bleiben unberührt.

**Offen trotz dieser Tests:** echter Browser mit DOM/CSP unter HTTP, realer mobiler UI-Test, produktionsferner Containerverbund mit eigener Netzwerk-/Volume-Isolation, nachweisbarer Stream-Abbruch im echten Proxy-Pfad und Security-Review. Dieses Gate ist also zunächst eine **Vorauswahl**, nicht die endgültige UI-/Docker-Freigabe.

## Isolierter Docker-HTTP-Test mit vorhandenen QA-Images (auf Pi bestanden)

Der gemeldete Gateway-QA-Image-Abgleich ergab sechs von sechs identische Dateien. Das aktualisierte Console-Image private-ai-p23-console:qa-current bestand den isolierten Laufzeittest und sein server.py-Hash stimmt mit dem Checkout überein. Das ältere Console-Image :qa wurde bei server.py als veraltet erkannt.

Der neue Test scripts/pi-p23-docker-http-smoke.sh verwendet ausschließlich vorhandene lokale Images, ein neu erzeugtes internes Bridge-Netz und drei kurzlebige Container (Offline-Ollama-Simulator, Gateway und Console). Das Gateway speichert Testdaten ausschließlich auf /data-tmpfs. Es werden **keine produktiven Docker-Container, Volumes, .env-Dateien, Netzwerke, Host-Portfreigaben, Builds, Pulls oder Downloads** verwendet. Ein Exit-Trap entfernt die eigenen QA-Container und das eigene Testnetzwerk.

Er überprüft HTTP-Login, Session und RAG-Konfiguration; CSP und Security-Header; authentifizierten Import mit CSRF- und Origin-Prüfung; serverfestes Namespace-Scoping; containerübergreifendes RAG-SSE einschließlich Quelle [Q1] und Stream-Ende; normalen Chat ohne RAG; sowie Client-Verbindungsabbruch während eines Streams und anschließende Erreichbarkeit des Console-Servers.

**Abbruch-Grenze:** Der Test bestätigt den Client-Disconnect und die weitere HTTP-Erreichbarkeit, aber nicht die tatsächliche Beendigung aller Upstream-Inferenzarbeiten. Ein echter Browser-/CSP-UI-Test und die reale lokale Ollama-Inferenz in Docker bleiben getrennte Gates.

### Pi-Ausführung

~~~bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git pull --ff-only origin feature/p2-rag-chat-citations
bash -n scripts/pi-p23-docker-http-smoke.sh
.venv/bin/python -m py_compile scripts/pi-p23-docker-ollama-mock.py scripts/pi-p23-docker-http-client.py
bash scripts/pi-p23-docker-http-smoke.sh > /tmp/p23-docker-http-smoke.log 2>&1
rc=$?
echo "Exit-Code: $rc"
tail -35 /tmp/p23-docker-http-smoke.log
~~~

Erwartete Marker bei Exit-Code 0: Console HTTP login/CSP/RAG config PASS; Authenticated import/CSRF/Origin/fixed namespace PASS; Container-to-container RAG SSE [Q1] PASS; Non-RAG chat PASS; Client disconnect during SSE and Console remains responsive PASS; P2.3 ISOLATED DOCKER HTTP SMOKE: PASS; QA cleanup finished.

**Stand:** Am 26.10.2026 auf dem Raspberry Pi 5 mit Exit-Code **0** bestanden. Der HTTP-Test startete das eigene interne Netzwerk ohne Host-Portveröffentlichung, alle drei QA-Container wurden bereit, sämtliche HTTP-Prüfungen bestanden und die abschließende Cleanup-Ausgabe bestätigte die Entfernung der temporären Ressourcen. PR bleibt Draft; kein Produktivdeploy oder Merge.

## Isolierte Docker-HTTP-Abnahme vom 26.10.2026

**Nutzerprotokoll:** `bash scripts/pi-p23-docker-http-smoke.sh`, Exit-Code **0**.

- Neues internes Docker-Netzwerk ohne Host-Ports erzeugt; drei temporäre QA-Dienste bereit.
- `Console HTTP login, CSP, session, static UI and RAG config: PASS`
- `Authenticated import, CSRF, Origin and fixed namespace: PASS`
- `Container-to-container RAG, SSE [Q1] and completion: PASS`
- `Non-RAG chat unchanged: PASS`
- `HTTP client disconnect during SSE; Console remains responsive: PASS`
- `P2.3 ISOLATED DOCKER HTTP SMOKE: PASS`
- `P2.3 QA cleanup finished (disposable resources only)`

**Grenzen:** Simulierter Ollama-Upstream; kein tatsächlicher Browser, kein realer CSS-/CSP-Browser-Renderpfad und kein Nachweis, dass Client-Abbruch die Upstream-Berechnung beendet. Die erfolgreiche Cleanup-Meldung stammt vom Testskript; ein unabhängiger Nachlauf der Docker-Ressourcen ist damit nicht belegt. Produktive Volumes und Container wurden durch die Testanweisungen nicht angesprochen.
