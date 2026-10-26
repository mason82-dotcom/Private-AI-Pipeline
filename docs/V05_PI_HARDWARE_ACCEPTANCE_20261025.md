# Raspberry Pi 5 — P1/P2 Hardware-Abnahme (2026-10-25)

## Prüfstand

- Host: Raspberry Pi 5, Debian 13, Docker Compose v5.6.1, Ollama 0.33.2
- Repo/Branch: `mason82-dotcom/Private-AI-Pipeline`, `release/v0.5-p1-p2`
- Betrieb: Gateway und Console in internem Docker-Bridge-Netz; existierendes Host-Ollama über lokale Bridge-Proxies; Light Console nur über Loopback/SSH-Tunnel
- Projektbezogene Mehrbenutzer-RBAC und nachgewiesene WAN-Egress-Sperre **nicht** Bestandteil dieser Abnahme

## Durch Nutzertests belegt

| Funktion | Befund | Nachweis |
| --- | --- | --- |
| Python-Regressionssuite | 53/53 Tests bestanden | Pi-Terminal, `unittest discover` |
| Gateway | Docker health = healthy | `docker compose ps` |
| Lokales Ollama | 6 bereits vorhandene Modelle über Gateway gelistet | GET `/v1/models` |
| Host-Ollama-Anbindung | Ollama 0.33.2 aus Gateway-Container erreichbar | Bridge-Proxy und GET `/api/version` |
| Console | Docker health = healthy, HTTP 200 | interner `/health`-Test |
| Windows-Zugriff | HTTP 200 durch Windows-SSH-Tunnel | Windows `curl.exe` auf Loopback |
| Console-Login | UI nach Authentifizierung nutzbar | Screenshot aus Browser |
| Chat-Verlauf | Zwei aufeinanderfolgende Streaming-Antworten ohne frühere `Nachrichtenlänge ungültig`-Fehlermeldung | Pi-Live-Screenshot; Hotfix im Branch |
| Direkte Chat-Inferenz | `qwen3:0.6b` antwortet vollständig (`done:true`) in ca. 3,26 s | Ollama `/api/chat` |
| Dokumentenliste | Testdatei `p2-hardwaretest.txt` angezeigt, indiziert | Light Console Screenshot |
| Dokumentensuche (FTS5) | `p2probeokt2026` findet importierten Text mit Fundstelle | Light Console Screenshot |
| Knowledge API | `documents` und `memory` unter Namespace `personal` abgefragt | Gateway-API-Ausgabe, je 0 Einträge vor Import |
| Import deaktiviert | `KNOWLEDGE_IMPORT_ENABLED=false`, UI zeigt „Import gesperrt“ | `.env`-Auswahl und Browser-Screenshot |

**Einschränkung:** Das Screenshot belegt weder den zweiten identischen Upload als Dublette noch eine aktive Anzeige von gespeicherten Memory-Einträgen. Vor dem finalen P2-Abschluss diese Fälle separat protokollieren.

## Bereits behobene Integrationsprobleme

1. ZIP-Quellbaum mit zu restriktiven Unix-Dateirechten: Container-Dockerfile normalisiert Leserechte.
2. Console-Port bei `internal: true` nicht auf Host veröffentlicht: separater Loopback-socat-Proxy; Host-Publish-Bindung allein genügte nicht.
3. SSH-Tunnel versehentlich auf dem Pi statt Windows gestartet: Tunnel nun auf Windows-Port 38882.
4. Große `dolphin3-pi`-Inferenz mit ca. 5,3 GB Laufzeitverbrauch, 7+ GiB Swap, 180-s-Timeout: kleineres `qwen3:0.6b` für Abnahme.
5. Leere/fehlgeschlagene Assistant-Turns wurden im Chatkontext gesendet: Browser-Historie bereinigt und Regressionstests ergänzt.

## Offene Release-Gates

- [ ] Dubletten-Import eindeutig mittels zweier identischer Imports und `duplicate:true` nachweisen
- [ ] Memory-Tab bei mindestens einem bewusst gespeicherten Datensatz testen
- [ ] Persistenz nach Container-Neuerstellung und Restore mit isolierten Wegwerf-Volumes testen
- [ ] Firewall/Egress-Isolation der gesamten Pipeline und Zugriffsbeschränkung der Proxies auditiert prüfen
- [ ] PDF-Import mit Seitennummern, maximalen Dateigrößen und Parser-Isolation implementieren
- [ ] Quellenbelegte Chat-RAG-Suche und Retrieval-Qualität prüfen
- [ ] UI-Anzeige für Modellstart/Timeout/Token-Streaming und Ressourcenwarnung ergänzen
- [ ] GitHub-CI prüfen und Draft-PR vor Merge reviewen

## Betriebsregeln

Keine produktiven `.env`-Schlüssel oder Datenbanken in Git einchecken. `docker compose down -v` ist für diese Installation verboten. Für Importtests nur isolierte Testdokumente ohne private Inhalte verwenden, vorab SQLite-Backup über die SQLite-Backup-API prüfen. Open WebUI wurde in diesem Abnahmelauf **nicht** produktiv abgenommen.
