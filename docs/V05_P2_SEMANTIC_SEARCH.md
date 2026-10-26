# P2.2 – Optionale lokale semantische Dokumentensuche

**Status:** Entwicklungsbranch; Pi-ARM64-Tests mit echtem lokalen Ollama-Embedding-Modell bestanden, aber Container-/Console-End-to-End-Abnahme und GitHub-CI weiterhin offen. Kein Chat-RAG in dieser Phase.

## Architektur

Dokumente aus SQLite FTS5 (`upload:*`, `doc:*`, `pdf:*`) werden nur nach einer **expliziten Operator-Aktion** in lokale Vektoren umgewandelt. Erinnerungen bleiben ausgeschlossen. Pro Dokumenttext wird ein SHA-256-Prüfwert gespeichert; veraltete Vektoren werden beim Suchen verworfen und müssen bei Bedarf neu indiziert werden.

Vektoren (normalisierte float32, 32–2048 Dimensionen) liegen in der bestehenden SQLite-Datenbank in `semantic_vectors`. Der Primärschlüssel enthält Namensraum, Quellen-ID und Modellbezeichnung. Keine neue Cloud-Abhängigkeit, kein automatischer Download, kein autonomer Hintergrundlauf, keine neue Netzwerkfreigabe.

Die semantische Suche erfolgt über die separate Knowledge-API des Gateways mit eigenem Berechtigungsschlüssel. Bei aktiviertem Modus erhält der angemeldete Operator in der Light Console eine Auswahl **Volltext** oder **Semantisch (lokal)**. Die Suche liefert maximal fünf Treffer mit Quellenkennung, ggf. PDF-Seite und Kosinus-Ähnlichkeit. **Ähnlichkeit ist kein Wahrheits- oder Relevanznachweis.**

## Konfiguration (standardmäßig OFF)

```dotenv
SEMANTIC_SEARCH_ENABLED=false
SEMANTIC_MODEL=nomic-embed-text:latest
```

Nur `nomic-embed-text:latest` und `bge-m3:latest` sind freigegeben. Der Modellhost ist der bereits explizit konfigurierte lokale `OLLAMA_URL`. Das Modell `nomic-embed-text` ist auf dem Raspberry Pi bereits installiert. Ein echter Hardware-Test gegen `127.0.0.1:11434` mit temporärer SQLite-Datenbank wurde am 25.10.2026 erfolgreich durchgeführt; der produktive Gateway-/Console-Pfad wurde dabei nicht verwendet.

Die Konfiguration wird über `compose.yaml` in den Gateway-Container übernommen. Import (`KNOWLEDGE_IMPORT_ENABLED`) und semantische Suche haben **unabhängige** Flags. Ein Dateiupload startet keine Modellindizierung.

## Testen ohne produktive Container zu verändern

Nur im separaten Checkout:
```bash
cd ~/Projekte/Private-AI-Pipeline-P2-Dev
git fetch origin
git switch --track origin/feature/p2-semantic-search
python3 -m unittest discover -s tests -p 'test_p2_semantic.py' -v
node --check console/static/app.js
node tests/test_chat_history.cjs
```

Diese Tests verwenden einen **Fake-Ollama-Embedding-Server**, nicht das echte Modell.

## Spätere gezielte Pi-Abnahme – erst nach Freigabe/Backup

Vor einem produktiven Test: bestehendes SQLite-Volume über SQLite-Backup-API sichern und Sicherung prüfen. **Nicht** `docker compose down -v` ausführen. Einen neuen Gateway-Container nur in einem geplanten Wartungsfenster bauen/neu erstellen; dann vorher laufende Chats beenden. Auf dem Pi kein großes Chatmodell parallel zum Embedding-Modell laden.

Nach bewusstem Aktivieren des Flags in der installierten `.env` und Neubau des Gateway-Images kann ein Operator in kleinen Batches indexieren:

```bash
cd ~/Projekte/Private-AI-Pipeline
docker compose exec -T gateway python semantic.py index --limit 8
```

Der Indexlauf erfasst höchstens acht neue/geänderte Chunks; erneuter Aufruf für weitere Batches. Die maximale Suche/Index-Scan-Grenze liegt bei 512 Einträgen. Für große Datenmengen ist eine spätere paginierte Batch-Indexierung nötig.

Im UI: **Wissen & Gedächtnis → Dokumente**, Suchmodus auf **Semantisch (lokal)** stellen und Suchbegriff eingeben. Wenn das Flag aus ist, bleibt die Volltextsuche vollständig funktional. Ohne Vektoren meldet das Gateway 409; bei nicht verfügbarem lokalem Embedding-Modell 503. Keine Cloud-Ausweichroute.

## Offen / Release-Gates

- [x] Raspberry-Pi-Python-Regressionssuite: 65 Tests, zunächst 64 bestanden + 1 wegen PyYAML übersprungen; anschließend alle 8 Tests in `test_v02.py` mit PyYAML bestanden, einschließlich des zuvor übersprungenen Tests. Zusätzlich 7 Chat-Historien-Tests bestanden.
- [ ] GitHub-CI-Gesamtlauf für den Feature-Branch bestätigt
- [x] Echte ARM64-Embedding-Inferenz mit `nomic-embed-text`: zwei Chunks in temporärer SQLite-DB, Indexierung 2/2, Suchranking Bagger-Hydraulik (0,9056) vor Apfelkuchen (0,6147)
- [ ] Echte ARM64-Docker-Build- und End-to-End-Tests; Modell-Ladezeit, RAM/Swap-Verlauf und Suchlatenz noch nicht separat gemessen
- [ ] Validierung auf mehrseitigen echten Text-PDFs und geänderten Quellen
- [ ] Begrenzung/Monitoring bei mehreren parallelen Suchanfragen, Zugriffsschutz und Egress-Audit
- [ ] Quellenbelegte RAG-Antworten im Chat (P2.3), noch nicht integriert
- [ ] Review und Merge der vorgelagerten P2.1-PDF-Änderungen

Dieser Stand ist **nicht** produktiv freigegeben. Container und bestehende Dienste auf dem Pi bleiben bis zur gesonderten Abnahme unverändert.

## Bestätigte Pi-Ergebnisse vom 25.10.2026

- RAM vor dem Test: 7,9 GiB gesamt, 3,3 GiB verfügbar; Swap 15 GiB gesamt, 3,8 GiB verwendet. Nachher-Werte nicht gemeldet.
- Ollama `ps`: keine geladenen Modelle vor dem Test.
- Installiertes Embedding-Modell: `nomic-embed-text:latest`, 274 MB laut `ollama list`.
- Import in isolierter SQLite-DB: `{'indexed': 2, 'examined': 2, 'model':'nomic-embed-text:latest','namespace':'hardwaretest','limit':8}`.
- Abfrage: „Wie funktioniert die Hydraulik eines Baggers?“ – Rang 1: Bagger/Hydraulikzylinder, Score 0,9056; Rang 2: Apfelkuchen, Score 0,6147.
- Ergebnis am Pi: `P2.2 REAL EMBEDDINGS: PASS`.
- Aussagegrenze: Der erfolgreiche Test bestätigt echten lokalen Ollama-Modellaufruf, Vektor-SQLite und Ranking; nicht die Docker-/UI-Berechtigungskette und keinen RAG-Chat.
