# Private AI Pipeline — Produkt- und Entwicklungsroadmap

**Version:** 0.2 / Planstand 2026-10-25
**Produktziel:** Eine lokal betriebene KI-Entwicklungsumgebung mit vertrauenswürdigem Chat, nachvollziehbarer Wissenssuche, kontrolliertem Agenten-Gedächtnis und optionaler Modellinferenz auf einem zweiten Heimnetz-Rechner.

## 1. Nicht verhandelbare Produktprinzipien

1. **Local first**: Keine Cloud-Provider, kein automatischer Fallback, kein standardmäßiger Remote-Zugriff.
2. **Fail closed**: Ohne Modellserver wird ein klarer Fehler angezeigt; kein stiller Wechsel.
3. **Least privilege**: Agenten lesen standardmäßig nur; Persistieren, Löschen, Dateischreiben und Terminalzugriff verlangen separate Freigaben.
4. **Isolierte Erinnerungen**: Namensräume pro Projekt/Vertrauensdomäne. Kein allgemeiner Chat-Mitschnitt.
5. **Reproduzierbar**: Image-Pins, testbare Migrationspfade, Backups und Restore-Drills.
6. **Pi-schonend**: Pi 5 (8 GB) hostet Steuerung/UI/Speicher; leistungsintensive Inferenz möglichst extern.
7. **Explizit getrennte Betriebsarten**: (A) abgeschottet im eigenen Docker-Netz, (B) freigegebener lokaler Inferenzhost unter Host-Firewall-Regeln. 'Offline' heißt nicht, dass LAN-Egress automatisch sicher ist.

## 2. Scope und Zielgruppen

- **Einzelnutzer-MVP**: Eigentümer betreibt Open WebUI lokal, verbindet ein Modell und fragt projektspezifische Notizen ab.
- **Coding-Workflow**: Hermes/Codex suchen gezielt in *freigegebenem* Projektspeicher; Schreibzugriffe bleiben zunächst gesperrt.
- **Operator-Workflow**: Fehlersuche ohne vertrauliche Prompt-Logs; Backup und Restore mit überprüfbarer Datenintegrität.
- **Nicht v1.0**: Öffentliche SaaS-Nutzung, beliebige Plugins aus dem Internet, unüberwachte Code-Agenten, RAGFlow auf dem Pi, Multi-Tenant-SaaS, garantierte Echtzeit-Inferenz auf GTX 1050 Ti.

## 3. Rollenbasierte Aufgabenverteilung (Verantwortung, nicht behauptete Ausführung)

| Rolle | Eigentümerschaft | Entscheidungsrecht |
|---|---|---|
| Produktverantwortlicher (PO) | Prioritäten, Akzeptanz, Freigaben für reale Pi-/LAN-Änderungen | Scope und Release-Freigabe |
| Plattform/DevOps | Docker Compose, Ressourcen, Installationssicherheit, Backups | Infrastruktur-Pull-Requests |
| Backend/API | Gateway, Protokolle, Fehlerbehandlung, Streaming | API-Vertrag und Implementierung |
| Security/Privacy | Netzsegmente, Geheimnisse, Egress, Threat Model | Blockierendes Security-Review |
| AI/RAG & MCP | Gedächtnis, Quellenqualität, MCP-Protokoll, lokale Embeddings | Daten- und Retrieval-Verträge |
| Product Design | Informationsarchitektur, Jobs-to-be-done, Onboarding, Accessibility | UX-Abnahme |
| QA/Release | Integrationstest, Hardware-Messung, Recovery, CI | Testfreigabe; Stop-the-line bei P0-Fehlern |

Eine Person oder ein KI-Agent darf mehrere Rollen übernehmen, aber jeder Pull Request braucht mindestens eine vom Implementierer unabhängige Abnahme. Kein Hintergrund-Agent arbeitet ohne explizit ausgelöste Sitzung.

## 4. Release-Phasen und Gates

| Release | Zielzeitraum (Planungsannahme) | Inhalt | Harte Freigabekriterien |
|---|---|---|---|
| **v0.2 – gehärteter Kern** | Woche 1–2 | Versionierte Compose-Profile, Namensräume, read-only MCP, Wiederherstellungsstrategie, Sicherheitschecks | 13+ Unit-/HTTP-Tests grün; kein public Bind; vollständiger Restore-Drill **auf Testvolumes**; Pi-Port-/Ressourcenaudit |
| **v0.3 – verlässliche Nutzung** | Woche 3–4 | MCP-Handshake/stdio-Kompatibilität, echter Ollama-SSE-Test, Sichtbarkeit des Modellzustands, Admin-Erststart und LAN-Policy | Hermes oder Codex führt Memory-Search aus; 30 Chat-Streams ohne Protokollfehler; Policy blockiert unzulässige Ziele |
| **v0.4 – lokales RAG** | Woche 5–7 | Dokumentquellen, deduplizierter Import, lokale Embeddings optional auf zweitem Rechner, Zitierstellen, PDF-Extraktion vor OCR | 20 Testdokumente, Nachweis der korrekten Quellen/Scopes; keine Netzdownloads nach Provisionierung |
| **v0.5 – Product UX + Agenten** | Woche 7–9 | Management-Ansichten, Import-/Löschbestätigung, Toolfreigaben, Hermes-Agent, Sandbox | Erfolgreicher First-Run ohne Shell bei vorhandenem Modell; alle destruktiven Agentenaktionen standardmäßig blockiert |
| **v1.0 – betreibbare Veröffentlichung** | Woche 10–12 | Supply-Chain-Pins, CI auf amd64/arm64, Backup-Restore-Drills, Betriebsdoku, Sicherheitsaudit, Rollback | Messprotokoll echter Pi; kein unbeabsichtigter Egress in abgeschotteter Betriebsart; Restore und Rollback reproduzierbar |

Zeitangaben sind **Planungsfenster**, keine zugesagten Liefertermine. Abhängigkeiten und Hardwareverfügbarkeit gehen vor Kalenderdatum.

## 5. Ausführbarer Backlog (reihenfolgeabhängig)

| ID | Prio | Rolle | Aufwand* | Paket | Abhängigkeit | Abnahme |
|---|---|---|---|---|---|---|
| PAI-001 | P0 | Plattform | S | Vorflugprüfung: Ports, freier RAM/SSD, Docker Compose | – | Read-only-Report; SkyHub, Forgejo, Mosquitto unverändert |
| PAI-002 | P0 | Security | M | Egress-Policy für separates LAN-Profil | PAI-001 | DNS/WAN geblockt, erlaubter Inferenzhost erreichbar |
| PAI-003 | P0 | Backend | M | Gateway-Protokolltests inkl. defektem SSE und Fehlercodes | – | keine doppelten HTTP-Antworten; 30 Streams fehlerfrei |
| PAI-004 | P0 | Plattform | M | Backup und Restore auf Testvolumes | PAI-001 | SHA-Prüfung, DB integrity_check, Verifizierung nach Restore |
| PAI-005 | P0 | QA | M | Pi-/GPU-PC-Abnahme | PAI-002,003 | echter Chat, Modellliste, Lastprofil, keine Portkollisionen |
| PAI-006 | P0 | Security | S | Erststart und Sign-up-Sperre | PAI-001 | Admin einmalig; nach Setup kein fremdes Signup |
| PAI-007 | P1 | AI/MCP | M | MCP stdio Lifecycle + Protokolltests | PAI-003 | Connect/List/Search/Errors mit echtem Client |
| PAI-008 | P1 | AI/MCP | M | Speicher-Berechtigungen & projektbezogene Namespaces | PAI-007 | Cross-namespace Tests; write off by default |
| PAI-009 | P1 | Product Design | M | Bedienkonzept, Screen-Flows und Accessibility | PAI-005 | 5 Kernprozesse mit Leer-/Fehler-/Ladezuständen spezifiziert |
| PAI-010 | P1 | Backend | S | Fehlerdiagnostik ohne Prompt-/Token-Logs | PAI-003 | Correlation-ID, strukturierte datensparsame Logs |
| PAI-011 | P1 | AI/RAG | M | Ingestion-Pipeline mit Metadaten und Deduplizierung | PAI-008 | Wiederholter Import ohne Duplikate; Rückverfolgbarkeit |
| PAI-012 | P1 | QA | M | v0.3 Regression CI (amd64 + arm64) | PAI-005,007 | Merge nur bei allen verpflichtenden Checks |
| PAI-013 | P2 | AI/RAG | L | Lokale semantische Suche als optionaler Dienst | PAI-011 | ausschließlich lokale Embeddings, Offline-/Recall-Test |
| PAI-014 | P2 | AI/RAG | M | PDF-/Tabellenextraktion mit Quellstellen | PAI-011 | Fundstelle dokumentiert und überprüfbar |
| PAI-015 | P2 | Security | M | Prompt-Injection-/Dokumentengrenzen | PAI-014 | untrusted Text kann keine Tools ausführen |
| PAI-016 | P2 | Product Design | M | Management-UI: Status, Wissen, Speicher, Freigaben | PAI-009 | Desktop/Mobil-Entwurf getestet, danach Implementierungsfreigabe |
| PAI-017 | P2 | Agenten | L | Hermes-/Codex-Adapter und Berechtigungsdialoge | PAI-007,008,015 | read-only läuft; write nur nach expliziter Freigabe |
| PAI-018 | P2 | Plattform | M | Lokales Ressourcen-Monitoring | PAI-005 | Host/container CPU RAM Speicher & Upstream-Status |
| PAI-019 | P2 | Security | S | Versionspins, SBOM, CVE-Prozess | PAI-012 | reproduzierbarer Build und dokumentierte Aktualisierung |
| PAI-020 | P2 | QA | M | Disaster-Recovery-/Rollback-Drill | PAI-004,019 | Upgrade–Fail–Restore–Rollback ohne Datenverlust |
| PAI-021 | P3 | AI/RAG | L | Zusätzliche Modell-/Embeddingprofile | PAI-013 | Ressourcenlimits und Profiltests |
| PAI-022 | P3 | Product Design | S | Bedienbarkeitstest mit realen Nutzeraufgaben | PAI-016 | Task-Erfolg ≥ 90 %, keine kritischen Accessibility-Fehler |
| PAI-023 | P3 | Plattform | M | Verschlüsseltes externes Backup | PAI-020 | Restore aus verschlüsseltem Off-Host-Archiv |
| PAI-024 | P3 | Security/QA | M | Release-Sicherheitsfreigabe v1.0 | PAI-002,015,019,023 | P0=0; dokumentiertes Restrisiko und Freigabe |

*Aufwand: S = bis 1 Arbeitstag, M = 2–3 Arbeitstage, L = 4–7 Arbeitstage (nur erste Schätzung).

## 6. Kritischer Pfad

```text
PAI-001 Host Preflight
  ├─ PAI-002 LAN-/Egress-Policy → PAI-005 Hardware-Abnahme
  ├─ PAI-004 Sicherung → PAI-020 Disaster-Restore
  └─ PAI-006 Admin-Erststart

PAI-003 Gateway-Tests → PAI-007 MCP → PAI-008 Namensräume
                                     ├─ PAI-011 Ingestion → PAI-013 RAG
                                     └─ PAI-017 Agenten
PAI-005 Hardware-Abnahme → PAI-009 UX → PAI-016 Management-UI
```

**Blocker:** Ohne erfolgreichen Host-/Offline-Test ist v0.2 nicht produktionsreif. Ohne echten MCP-Clienttest ist keine Agentenfreigabe erlaubt. Ohne nachgewiesene Retrieval-Quellen ist semantisches RAG nicht akzeptiert.

## 7. UX-Zielbild

- **Chat:** Modellstatus sichtbar, Fehler ohne Cloud-Umschaltung, Antwortstream kann abgebrochen werden.
- **Wissensquellen:** Import als bewusste Aktion; Quelle, Zeitpunkt, Namespace, Indizierungszustand.
- **Gedächtnis:** Lesen, begründetes Speichern, kontrolliertes Vergessen, niemals stilles Cross-Projekt-Mischen.
- **Agenten:** Tool-Aufruf zeigt Berechtigung, Zielpfad und Risikograd; Schreibfreigabe immer ausdrücklich.
- **System:** Offline/LAN-Modus, Modell erreichbar?, Ressourcen, Sicherheitswarnungen, Backupdatum.

Open WebUI bleibt Frontend. Zusätzliche Management-Screens werden erst nach UX-Abnahme umgesetzt, um nicht die gesamte Open-WebUI-Oberfläche zu ersetzen.

## 8. Qualitätsmetriken

- **Sicherheit:** 0 öffentliche Ports ohne bewusste Freigabe; 0 Cloud-Fallbacks; Gateway kein Prompt-Logging; unerlaubte Egress-Verbindungen = 0 im abgeschotteten Test.
- **Zuverlässigkeit:** Wiederherstellung einer Testinstallation einschließlich Konfiguration erfolgreich; `PRAGMA integrity_check=ok`; keine verlorenen zugelassenen Dokumente beim Reimport.
- **API:** HTTP/JSON + SSE gegen simulierten und realen Ollama-Server; eindeutige Fehler bei Ausfall.
- **Leistung:** Pi-Idle-/Last-RAM und SSD-I/O vor/nach Installation messen. Ein absolutes Performanceversprechen ohne Hardware-Messung wäre unseriös.
- **UX:** 5 Kern-User-Journeys; jedes hat Lade-, Leer-, Fehler- und Erfolgsmeldung sowie Tastaturbedienung.

## 9. Definition of Ready / Done

**Ready:** Akzeptanzkriterien messbar, Schnittstellen/Owner definiert, Abhängigkeiten geklärt, private Datenbeispiele synthetisch.

**Done:** Quellcode + Unit-/Integrations-Tests + Datenschutz-Risiken + Dokumentation + reproduzierbarer Testreport; unabhängige Review-Freigabe; keine Veränderung anderer Pi-Dienste.

## 10. Quelle für technische Leitplanken

- https://docs.docker.com/compose/how-tos/networking/
- https://docs.openwebui.com/reference/env-configuration/
- https://docs.openwebui.com/getting-started/advanced-topics/hardening/
- https://docs.openwebui.com/tutorials/maintenance/offline-mode/
- https://modelcontextprotocol.io/specification

**Wichtig:** `OFFLINE_MODE=true` in Open WebUI verbietet nicht alle selbst konfigurierten externen Verbindungen. Docker `internal:true` trennt nur Container, die **ausschließlich** im internen Netz hängen; das Opt-in-LAN-Profil braucht zusätzlich Hostregeln.
