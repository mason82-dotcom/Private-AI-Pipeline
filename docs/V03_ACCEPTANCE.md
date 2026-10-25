# v0.3 — Betrieb, Testabnahme und offene Risiken

## Liefergegenstand (prüfbar im Repository)

- `console/server.py`: neues serverseitiges Gateway-Frontend mit ohne Drittbibliotheken implementierter scrypt-Anmeldung, `HttpOnly`/`SameSite=Strict`-Cookie, Anti-CSRF, zeitlicher Session-Grenze, begrenzter Login-Rate und strikt lokaler Gateway-Zielprüfung.
- `console/static/`: responsive Light Console mit echten API-Routen, SSE-Stream (lokal), kein Drittanbieter-JavaScript, CSP und reiner DOM-Textdarstellung für Modellinhalte.
- `compose.console.yaml`: opt-in-Service, localhost-Port 38881, Bridge `internal:true`, RAM-/PID-Limit, rootless, read-only und ohne zusätzliche Host-Mounts.
- `tests/test_v03_console.py`: vollständiger temporärer HTTP-Stack Fake Ollama → Gateway → Console als End-to-End-Simulation.

## Vor der echten Pi-Abnahme

1. Auf Pi 5 (Debian 13/aarch64) **nur lesen**: `docker compose ls`, `docker ps`, `ss -lntup`, `free -h`, `df -h`, `docker system df`, Tailscale-Serve-Regeln; Ergebnisse ohne Secrets sichern.
2. Prüfen, dass Ports 38880/38881 frei sind, keine Portweiterleitung offen ist und CPU/RAM/SSD genügend Reserve aufweisen.
3. Exakten Image-Digest für Open WebUI, Ollama (optional), Python/Console/Gateway-Build notieren; ARM64-Manifeste nachweisen. Keine impliziten Updates.
4. Bestehende SkyHub-Next-, Forgejo-, Mosquitto- und Hermes-Dienste vorher/nachher vergleichen. Andere Compose-Projekte weder stoppen noch modifizieren.
5. Getrennten Backup-Test nach dokumentierter Wiederherstellungsprozedur ausführen, inklusive SQLite-Integrität, Open-WebUI-Chats und Konfiguration.

## Live Acceptance Gates

| Gate | Aktion | Erwartetes Ergebnis |
| --- | --- | --- |
| Auth | Console ohne Login öffnen | Login sichtbar; `/api/models` 401 |
| Login | Falsche Passwörter wiederholen | 401, dann 429; Session nur mit richtigem Passwort |
| CSRF/CORS | Forged POST ohne Token/mit Fremd-Origin | 403 |
| Modell | Mit ausdrücklich freigegebenem LAN-Ollama verbinden | Reale Modell-ID erscheint, keine Demo-Modelle |
| Chat | 30 echte Streaming-Chats/Abbruchtests | Korrektes SSE, kein Fehler nach Header-Start, kein Prompt-Logging |
| Recovery | Gateway ausschalten und Modelle neu laden | 503/Unbekannt, kein Cloud-Fallback |
| Datenschutz | Netzverkehr beim Chat kontrollieren | Kein unerwarteter WAN-Egress; LAN nur freigegebener PC |
| Reverse Proxy | Optional Tailscale HTTPS | Geschützte Session, `Secure`-Cookie, Auth-Cookie nur via HTTPS |
| Resource | Pi unter Last messen | Keine OOM-Kills, Auswirkung auf Bestandsdienste dokumentiert |
| Backup | Wegwerf-Restore und Hash/Integritätskontrolle | Wiederherstellbarer Zustand, keine produktiven Volume-Änderungen |

## Bekannte Grenzen und Folgeschritte

- Console-Zugang ist ein **separater Single-Operator** und kein SSO mit Open WebUI. Keine Rechteweitergabe zwischen den Systemen.
- Keine tragfähige projektbezogene HTTP-Memory-API; kein dokumentenbezogenes RAG, keine MCP-Schreibfreigaben; nicht als fertig bewerben.
- Das GUI blendet bei Modellhost-Ausfall dessen echte Modelle aus, aber CPU, RAM, Docker und WAN-Zustand werden noch nicht ermittelt.
- Passwortprüfwert in `.env`, Gateway-Token im Container-Environment: Docker-Administratoren können die Hashes/Token sehen; produktiv auf Docker-Secrets umstellen.
- Sicheres LAN-Egress verlangt Host-Firewall und Messung, bevor `compose.lan.yaml` verwendet wird.
- Vor einem Merge ins öffentliche GitHub: Quelltext auf Zugangsdaten, private Dokumente und gitignore-Probleme prüfen.
