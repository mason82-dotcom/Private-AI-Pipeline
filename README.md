# Private AI Pipeline — v0.5 (P1 + erste P2-Implementierung)

**Neu:** getrennte Gateway-/Ollama-Diagnose mit Prüfzeitpunkt und Latenz; eigenständig authentifizierte, projektgebundene Wissens-API mit read-only Memory, optionale Textimporte und SHA-256-Deduplizierung. **50+ lokal simulierte HTTP-/Unit-Tests; echte Pi-/Docker-Abnahme weiterhin offen.**

**Migration und Release-Gates:** [docs/V05_P1_P2.md](docs/V05_P1_P2.md). Für bestehende `.env`: `bash scripts/upgrade_env_p2.sh` vor dem Neustart ausführen. Für neue Installationen erzeugt `scripts/init.sh` zusätzlich den separaten Knowledge-Schlüssel. Der Import ist **standardmäßig aus** und muss bewusst aktiviert werden.

---

# Private AI Pipeline v0.4-P0 — lokale KI und Light Console

**Status 2026-10-25, UX-Ausbau P0/P1:** Konsolidierte Entwicklungsversion mit Open WebUI, lokalem Gateway, SQLite-FTS5-Gedächtnis, read-only MCP und einer **neu angebundenen Light Console**. Gateway- und Console-End-to-End-Tests wurden gegen einen **simulierten** Ollama-Server ausgeführt. **Keine** echte Pi-/Docker-/Windows-GPU-Abnahme. **Nicht** für öffentlich erreichbaren Betrieb oder unbeaufsichtigte Agenten freigegeben.

Die Light Console enthält weiterhin vier echte read-mostly Funktionen: Login, Status, Modellliste und Modell-Streaming-Chat. Wissensbasis, Gedächtnis und Agenten zeigen ihren geplanten Status, haben **keine** HTTP-Schreib-APIs. Open WebUI ist weiterhin die separate Haupt-Chatoberfläche; es hat eine **eigene** Benutzerverwaltung und speichert den eigenen Chatverlauf unabhängig von der Console. Der Console-Chat ist ausschließlich flüchtig im aktuellen Browser-Tab (auch das Upstream-Gateway protokolliert nicht den Prompt). `MEMORY_INJECTION=false`, `MCP_READONLY=true` sind weiterhin Standard.

## UX-Weiterentwicklung v0.4-P0 (neu)

Das neue UI übernimmt das P0–P4-Konzept aus Canva: **fünf Hauptmodule** (Übersicht, Chat, Wissen & Gedächtnis, Agenten, System). Modelle, Netzwerk, Sicherungen und Einstellungen liegen als Tabs innerhalb von System; Dokumente und Erinnerungen als getrennte Tabs unter Wissen & Gedächtnis. Die globale Schnellnavigation (`Strg+K` bzw. `Cmd+K`) wechselt nur zwischen **Ansichten**, nicht zwischen vertraulichen Dokumenten. Desktop-Navigation, mobiler Drawer, Esc-Verhalten und Fokuszustände wurden erweitert. Status-Abfragen enthalten jetzt serverseitige UTC-Prüfzeitpunkte und Quellenkürzel.

**Wichtig:** Die Topbar zeigt ausdrücklich „Einzelinstanz · kein Projektfilter“ statt eines nicht implementierten Projektwechsels. Es existiert noch keine projektbasierte Backend-RBAC. Wissen, Gedächtnis und Agenten zeigen deshalb ausschließlich das geplante Zielbild, ohne echte private Datensätze oder Schreibrechte. Nicht durch den Browser verifizierbar sind WAN-Isolation, Firewall, Backup-Restore und Pi-Ressourcen.

Die 40 Python-Tests (davon 8 neue P0-Vertrags-/Integrationstests) laufen ohne echte Inferenzhardware; zusätzlich wurden die neue UI-Navigation und Mobilansicht in Chromium mit simulierten API-Antworten geprüft. Browser-E2E über lokale Ports konnte wegen Testumgebungsbeschränkung nicht durchgeführt werden. Details in `docs/V04_P0_UX.md`.

## Architektur

```text
Browser -- 127.0.0.1:38881 --> Light Console (scrypt Login, Session, CSRF)
                                      |
                   ausschließlich internes Docker-Netz
                                      v
Browser -- 127.0.0.1:38880 --> Open WebUI ---+--> Gateway (Bearer Token)
                                                   |        |
                                                   |        +--> SQLite FTS5 / MCP stdio
                                                   +--> Ollama (internes Docker-Netz
                                                        oder ausdrücklich freigegebener LAN-PC)
```

Der Browser erhält **nie** den `PIPELINE_TOKEN`. Das Backend akzeptiert nur `GET /api/status`, `GET /api/models` und `POST /api/chat` sowie Session-Verwaltung. Es gibt keine API zum Löschen, Erstellen oder Ändern von Projektdateien. Die Gateway-Schnittstelle bleibt ausschließlich intern. Standard-Compose betreibt ein Docker-`internal`-Netz; `compose.lan.yaml` fügt auf ausdrücklichen Wunsch ein Egress-Netz hinzu, das **zusätzliche Host-Firewall-Regeln benötigt**. Dies allein ist **keine Air-Gap-Garantie**.

## Installation der neuen Console (opt-in)

Von v0.2 können Projektdateien zunächst **ohne Löschen der alten Docker-Volumes** durch v0.3 ersetzt werden. `.env` und persistente Docker-Volumes vor Änderungen sichern und die vorhandenen Ports/Dienste prüfen. Niemals `docker compose down -v` verwenden. Auf einem Pi mit bereits laufendem SkyHub-Next, Forgejo, Mosquitto und Tailscale nur nach geprüftem Vorflug-Audit starten.

```bash
# Im entpackten Projektverzeichnis:
./scripts/init.sh                     # vorhandene .env bleibt unverändert
python3 console/set_password.py      # interaktive Eingabe; speichert nur scrypt-Prüfwert
./scripts/preflight.sh

# Bestehende v0.2-Dienste starten bzw. aktualisieren:
docker compose up -d --build

# Neue Console ausdrücklich zuschalten:
docker compose -f compose.yaml -f compose.console.yaml \
  --profile console up -d --build

# Öffnen auf dem HOST: http://127.0.0.1:38881
# Original Open WebUI:  http://127.0.0.1:38880
```

**Das Beispiel funktioniert erst, wenn ein lokales Ollama bereits erreichbar ist und mindestens ein Modell geladen hat.** `OLLAMA_URL` ist standardmäßig `http://ollama:11434`, der containerinterne Ollama-Dienst wird aber nur über das optionale Compose-`inference`-Profil gestartet. Für einen externen Windows-/LAN-Rechner statt des obigen Starts eine passende `compose.lan.yaml`-Kombination verwenden und die Firewall auf Pi **und** Inferenzrechner auf explizite Adressen begrenzen. Die Windows-GPU GTX 1050 Ti wird hier nicht automatisch konfiguriert.

### LAN-Modus (nur wenn freigegeben)

```bash
# Vorab OLLAMA_URL=<private IP> in .env, Host-Allowlist setzen und überprüfen!
docker compose -f compose.yaml -f compose.lan.yaml \
  -f compose.console.yaml --profile console up -d --build
```

**Sicherheit:** Die Console ist ausschließlich an `127.0.0.1:38881` gebunden; kein öffentlicher Zugriff. Ein späterer Tailscale-HTTPS-Proxy erfordert `CONSOLE_SECURE_COOKIE=true`, passende Trusted-Proxy-Konfiguration/Host-Freigaben und einen gesonderten Sicherheitstest. **Passwort nicht an eine HTTP-LAN-Adresse senden.** Anmeldung nutzt scrypt (gesalzener Prüfwert in `.env`), zeitlich begrenzte, rein speicherbasierte Session-Cookies (HttpOnly, SameSite=Strict), Token-/CSRF-Prüfung für schreibende Requests und Login-Rate-Limits. **Bestehende Open-WebUI-Konten authentifizieren NICHT automatisch die Console.**

Die Console authentifiziert nur einen Operator. **Keine Benutzer-/Projekt-RBAC-Implementierung** und keine Datenzugriffsrechte für andere Benutzer; bis zur Rechteprüfung nicht für Multi-User-Betrieb geeignet.

## Tests

```bash
python3 -m unittest discover -s tests -v
node --check console/static/app.js
node --check console/static/login.js
bash -n scripts/*.sh
# Auf Docker-Host nach Konfiguration:
docker compose -f compose.yaml -f compose.console.yaml \
  --profile console config
```

In den automatisierten Tests werden Start/Stop von drei temporären HTTP-Servern (Fake Ollama, echtes lokales Gateway und echte Console) eingesetzt. Überprüft werden Modellliste, echter SSE-Durchlauf (gegen Fake-Inferenz), Login, Cookie-Flags, CSRF, Cross-Origin-Verweigerung, Rate-Limit, Logout und kein Cloud-Fallback. **Das beweist nicht, dass ein realer Ollama-Server, Container-Image, ARM64-Host, Docker Compose oder Pi-Firewall korrekt funktionieren.**

## Betrieb und Sicherungen

`./scripts/backup.sh` und `./scripts/restore.sh` decken die Open-WebUI- und Gateway-Daten ab, **nicht** separat das Console-Sitzungsinventar (das absichtlich nur im RAM existiert). Die Konfiguration `.env` einschließlich `CONSOLE_PASSWORD_HASH` wird durch das bestehende Backup mitgesichert. Test-Restore grundsätzlich auf getrennten Wegwerf-Volumes durchführen. Archive sind **unverschlüsselt und vertraulich**; nicht ungeschützt in Cloud, Git oder gemeinsame Ordner legen. Docker-Image-Digests sind noch nicht gepinnt.

## Modulstand

| Modul | Umsetzungsstand | Beleg |
| --- | --- | --- |
| Light Console Login/Session/CSRF | Implementiert | HTTP-Integrationstest |
| Live-Status und Modellliste | Implementiert | Gateway/Ollama-Simulation |
| Browser-Chat mit SSE | Implementiert | HTTP-SSE-End-to-End mit Fake Ollama |
| Open WebUI | Compose vorbereitet | **Keine** reale Docker-Abnahme |
| SQLite-Memory / Namensräume | Implementiert | Unit-/Migrations-Tests |
| MCP stdio | Read-only implementiert | Unit-/Protokolltest, kein Hermes/Codex-E2E |
| Dokumente/RAGFlow/OCR/Vektorsuche | Nicht implementiert | Roadmap |
| Echte Pi-/GPU-/Netzwerk-/Restore-Abnahme | Offen | `docs/V03_ACCEPTANCE.md` |

Siehe außerdem `docs/ROADMAP.md`, `docs/SECURITY.md`, `docs/V03_ACCEPTANCE.md`, `docs/PRODUCT_DESIGN.md`, `AGENTS.md` und den bewusst separaten visuellen UI-Prototyp `design/prototype/`.


## Upgrade-Hinweis v0.3 → v0.4-P0

Dies ist ein **UI-/Status-API-Upgrade** ohne Veränderung an SQLite-Schema oder persistierten Volumes. Vor einem Wechsel auf dem Pi: Backups anlegen, Portbelegung prüfen, `docker compose ... config` validieren, Console-Dienst aktualisieren, `/api/status` und `/api/models` mit Auth prüfen. Container-Instanzen nicht ohne Host-Abnahme starten. Das bisherige Chatverhalten und der separate Open-WebUI-Verlauf bleiben erhalten.
