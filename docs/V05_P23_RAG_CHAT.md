# P2.3 – Optionale lokale Chat-Antworten mit Dokumentquellen

**Status: Draft / Entwicklung.** Der Code ist im separaten Branch implementiert; die neue P2.3-Regression und die echte Pi-/Docker-Abnahme sind noch nicht bestätigt. Keine Änderung am produktiven Raspberry-Pi-Stack.

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

- [ ] Neuer Pi-Python-Gesamtlauf inklusive P2.3 grün
- [ ] JS-Syntax und Chat-Historie unverändert grün
- [ ] CI-Lauf auf GitHub bestätigt
- [ ] Echtes mehrseitiges PDF mit Seitenangabe in Chat geprüft
- [ ] Semantische RAG-Suche mit echtem Modell (Latenz, Speicher, Ausfallverhalten)
- [ ] End-to-End-Authentifizierung, CSP, UI und Stream-Abbruch geprüft
- [ ] Manuelle Review: Prompt-Injection, Quellenidentität, Egress und Last
- [ ] Vorgelagerte P2.1 und P2.2 PRs gemergt

**Kein automatischer Deploy oder Merge.**
