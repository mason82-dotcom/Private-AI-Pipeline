# Light Console P0 / P1 — UX-Handoff und Abnahme

**Stand:** 2026-10-25. **Code:** Implementiert im Paket v0.4-P0; **Pi-Hardware:** nicht abgenommen. Das zugehörige 14-seitige Canva-Konzept bleibt Referenz, nicht Beleg einer Implementierung.

## Informationsarchitektur

- **Übersicht:** Handlungsorientierter Zustand, Gateway- und Modellprüfungen mit Herkunft und Zeitstempel, Diagnoseaktionen.
- **Chat:** Browserflüchtige SSE-Unterhaltung; Modellwahl; kein Cloud-Fallback. Open WebUI verwaltet seinen Chatverlauf weiterhin unabhängig.
- **Wissen & Gedächtnis:** Tabs `Dokumente` und `Erinnerungen`. Keine Live-Daten, bis Identitäts-/Namespace-API sicher implementiert ist.
- **Agenten:** Sicherheits- und Berechtigungs-Zielzustände. Weder Agent-Aktionen noch schreibende APIs verfügbar.
- **System:** Tabs `Dienste`, `Modelle`, `Netzwerk`, `Sicherungen`, `Einstellungen`. Nur Dienste und Modelle zeigen wirklich abgefragte Werte; die anderen Tabs sind Planungs-/Sicherheitszustände.

## P0-Komponenten

| Bauteil | Zustand | Test |
|---|---|---|
| Sidebar (5 Module) | Implementiert | 40 Python-Tests; DOM-Browserprüfung |
| Mobile Drawer / Scrim | Implementiert | 375 px Browserprüfung inkl. Interaktion |
| Tastatur-Suche (`Ctrl/Cmd+K`, Enter, Esc) | Implementiert | Browserprüfung gegen simulierte API |
| Untertabs für Wissen und System | Implementiert | Browserprüfung |
| Statuszeitpunkt `observed_at` (UTC) | Implementiert | Authentifizierter HTTP-Integrationstest |
| Gateway Health / Modellliste | Implementiert wie v0.3 | Fake Ollama HTTP End-to-End |
| Projektfilter und Multi-User-RBAC | Nicht implementiert | Keine private Daten-API freischalten |
| Netz-Egress-Messung / Restore-/Backup-Status | Nicht implementiert | Vor Produktivbetrieb messen |

## Read-only-Datenvertrag (aus Auth-Pflicht)

`GET /api/status` → `console`, `gateway`, `inference`, `source` (= `gateway_health`), `observed_at` (UTC ISO 8601). `inference: not_checked` ist bewusst: ein Gateway-Gesundheitscheck ist kein Modelltest.

`GET /api/models` → `models:[{id}]`, `source` (= `gateway_model_list`), `observed_at` (UTC ISO 8601). Bei Nichterreichbarkeit HTTP 503 statt Erfolg. `0 Modelle` kann auch eine leere Modellliste bedeuten: Statusdarstellung trennt diese Fälle.

Beide Endpunkte verlangen eine gültige Session. Jeder ausgegebene Prüfzeitpunkt ist der Zeitpunkt der Console-Abfrage, **nicht** zwingend Zeitpunkt der Zustandsänderung auf dem Zielsystem.

## UX-Zustandsmatrix

| Komponente | Leerlauf | Laden | Erfolg | Fehler |
|---|---|---|---|---|
| Übersicht | Ungeprüft | Prüfung | Zeitstempel + Quellangabe | Gateway unreachable / Diagnose |
| Modelle | Ungeprüft | Modellabfrage | echte IDs oder 'Keine Modelle' | Abfrage fehlgeschlagen, kein Cloud-Fallback |
| Chat | Eingabefeld | Stream/Stop | lokale Antwort | fehlendes Modell; Fehler, keine Ausweich-API |
| Wissen | bewusst gesperrt | – | erst nach RBAC | Platzhalter mit Grund |
| Agenten | bewusst gesperrt | – | erst nach Policy-Enforcement | WRITE/EXEC/NETWORK verweigert |
| Backup/Offline | nicht geprüft | – | erst nach Restore-/Egress-Nachweis | keine grüne Sicherheitsbehauptung |

## P1–P4-Abhängigkeiten

1. **P1**: Status-API als getrennte Dienstabfragen, exakte Fehlertypen und sichtbare Ablaufzeiten; echter Ollama-Test auf Pi/Windows (keine simulierten Werte).
2. **P2**: sichere Identitäts-/Projektbindung für Memory und Dokumente; nur nach serverseitigen ACL- und Cross-Scope-Tests.
3. **P3**: MCP-Client-Identitäten, scoped Policy-Enforcement, Approval-Flow mit TTL und Replay-Schutz; read-only bleibt Standard.
4. **P4**: Backup/Restore-Status aus überprüften Sicherungen, ARM64-Pi-Ressourcen, Host-Egress-Messung und WCAG-2.2-AA-Review.

## Sicherheit, Grenzen und Betriebsfreigabe

- UI-Tabs sind keine Zugriffskontrolle. Die Backend-Autorisierung muss separat erfolgen.
- Die Console bindet laut Compose nur an `127.0.0.1`, aber keine produktive Host-Portprüfung wurde durchgeführt.
- Der private LAN-Modus benötigt eine wirksame Host-Firewall und dokumentierten Egress-Test. Nur eine GUI-Aussage genügt nicht.
- Browser-Screenshots wurden mit ausdrücklich **simulierten** API-Antworten erzeugt. Kein tatsächlicher Modellhost ist damit abgenommen.
- Testbefehle: `python -m unittest discover -s tests -v`; `node --check console/static/app.js`; `bash -n scripts/*.sh`.

## Definition of Done P0

- [x] Fünf Hauptmodule sichtbar
- [x] Funktionsgruppierung in Wissen/System durch Tabs
- [x] Schnellnavigation und mobile Tastatur-/Touch-Interaktion im simulierten Browser
- [x] API-Abfragen belegen Quelle und Prüfzeitpunkt
- [x] Keine erfundenen Project-RBAC-/Backup-/WAN-Nachweise
- [x] Lokale Regressionstests und Chromium-UI-Prüfung
- [ ] Echte Docker- und Pi-Abnahme
- [ ] Vollständige Accessibility-Prüfung mit Screenreader
- [ ] Docker-Image-Pins, Netzaudit, Restore-Drill

**Release-Einstufung:** getesteter Entwicklungsstand, nicht produktionstauglich bestätigt.
