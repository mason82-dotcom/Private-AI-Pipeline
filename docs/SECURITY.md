# Sicherheit und Betriebsfreigabe

## Bedrohungsmodell

**Schutzobjekte:** Chats, Projektdateien, geheime Tokens, gespeicherte Erinnerungen, Netzwerkzugang und andere Pi-Dienste.

**Angreifer/Fehlfunktionen:** ungewollte WAN-Verbindungen; fremder Browser im selben LAN; kompromittiertes Dokument mit Prompt-Injection; unberechtigter Agent; kompromittiertes Docker-Image; unverschlüsseltes Backup; fehlerhaftes Update.

| Risiko | Ist-Zustand v0.2 | Offener Schutz |
|---|---|---|
| Cloud-Fallback | Nur fest konfigurierte private Ollama-Zieladresse | Reale Egress-Prüfung auf Pi und Windows-PC |
| WAN-Verbindungen | Standardnetze `internal:true`; LAN-Overlay ausdrücklich opt-in | Firewall-Allowlist für Modellhost und DNS |
| Gateway-Fremdzugriff | Token; keine veröffentlichten Gateway-Ports | Tokenrotation und Rejection-Tests |
| Open WebUI Anmeldung | Anmeldung an, Ersteinrichtung mit Signup an | Signup nach Adminanlage konsequent sperren |
| Memory-Cross-Project | getrennte SQLite-Namespaces; nur explizite Auswahl | Identität pro Benutzer erst bei Multiuser |
| MCP-Aktionen | stdio; default read-only | Clientinteroperabilität und Zustimmung zu Schreibrechten |
| Backup-Vertraulichkeit | Daten und `.env` zusammen im Archive, **nicht verschlüsselt** | verschlüsselte Ablage, Berechtigungen und Restore-Drills |
| Lieferkette | Docker-Tags nicht auf Digest fixiert | SBOM, Reproduzierbarkeit, CVE-Review |
| RAG-Dokument-Injection | Quellen als maskiertes JSON in einem unvertrauenswürdigen Datenblock; keine Toolrechte im RAG-Pfad | Modellbasierter Angriffskorpus und Autorisierungsschicht vor jeder Toolfreigabe |

## Sichere Freigabeabfolge

1. **Kein** `docker compose up` vor Host-Audit: Ports, RAM, Volume-Verfügbarkeit, laufende Services.
2. Erstinstallation ausschließlich Loopback `127.0.0.1`. Anmeldung/Signup absichern.
3. Standardmodus ohne ausgehende Containerverbindung; lokales Inferenzprofil nur bei ausreichenden Ressourcen.
4. LAN-Overlay nur nach Host-Firewall-Regeln freigeben. Remote-Ollama **niemals** an 0.0.0.0 ohne strikte Zugriffskontrolle/Firewall.
5. Kein Agenten-Schreibrecht und kein Shell-/Docker-Socket-Mount in der Basisinstallation.
6. Echte Netzbeobachtung im Hardwaretest (`tcpdump`/Firewalld/DOCKER-USER auf dem Host); auf Windows Host/WSL2 separat prüfen.
7. Nach jedem Image-Update: Gateway-/MCP-/WebUI-Tests, Backup, Restore-Test, Rollback-Plan.

## Benötigte Tests vor Produktivbetrieb

- Auth: unbekannter / fehlender Token → 401; kein Token in Logs.
- Gateway: unzulässiger URL-Host und Redirects abgelehnt; kein ungewolltes Fallback.
- Streaming: Client-Abbruch, Timeout, ungültige SSE-Frames, große Frames und begrenztes Antwortvolumen.
- Daten: Import ohne Symlink-Traversal, Maximalgrößen, isolierte Namespaces, Legacy-Migration.
- RAG: Angriffsdokumente können die JSON-Promptgrenze nicht schließen oder zusätzliche Rollen erzeugen; modellbasierte Befolgungstests bleiben separates Gate.
- Offline: DNS, HTTP, HTTPS aus allen rein internen Containern unzulässig. Für LAN-Overlay nur explizite private IP/Port erlaubt.
- Recovery: SHA, SQLite `PRAGMA integrity_check`, Open WebUI-Neustart und Erhaltung vorhandener Benutzer/Chats, **nur in Wegwerf-Testvolumes**.
- Host: SkyHub-Next, Forgejo, Mosquitto und Tailscale laufen nach Tests unverändert weiter.
