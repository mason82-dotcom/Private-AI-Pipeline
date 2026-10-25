# Private AI Pipeline

Lokale, datenschutzorientierte KI-Plattform auf Raspberry Pi 5 (ARM64) und optionalem LAN-Inferenzrechner.

**Status 2026-10-25:** Implementierungsstand v0.2 liegt als getestetes Projektpaket in der Entwicklungsumgebung vor, ist aber noch **nicht in dieses Repository eingecheckt**. Für den lokalen Stand wurden 17 Python-Unit-/HTTP-Vertragstests bestanden. Weder Docker noch realer Pi-/Ollama-Betrieb wurden abgenommen.

## Produktziel
Open WebUI → lokales OpenAI-kompatibles Gateway → Ollama; SQLite-FTS5-Gedächtnis, MCP-stdio, Namensräume, read-only als Standard. **Keine Cloud-Fallbacks**.

## Roadmap
- **v0.2:** Betriebskern härten, Host-/Portprüfung, Backup-/Restore-Abnahme, kontrollierter LAN-Egress.
- **v0.3:** Hermes-/Codex-MCP-End-to-End, echter Ollama-Streaming-Test und Diagnose.
- **v0.4:** lokale Dokumenten-Pipeline, PDF-Import und belegte Quellen; optionale lokale Embeddings.
- **v0.5:** Product-Design-Journeys und administrative Bedienoberfläche, sichere Agentenfreigaben.
- **v1.0:** reproduzierbarer ARM64-Release, Integrationstests, vollständiger Datenschutz- und Recovery-Nachweis.

Aufgaben sind in GitHub Issues unter Kennungen `PAI-001` ff. nach Priorität, Rollen, Abhängigkeiten und Abnahmebedingungen dokumentiert. Die Zuweisung erfolgt **an Fachrollen**, nicht automatisch an Personen oder unbeaufsichtigte KI-Agenten.

## Sicherheitsgrenze
Der Offline-Standard benötigt keine externe Schnittstelle; die WebUI bindet nur auf 127.0.0.1. Für einen externen lokalen Modellhost muss ein opt-in LAN-Profil bewusst aktiviert und über Host-Firewall-Regeln beschränkt werden. Open WebUI `OFFLINE_MODE` alleine ist **keine Egress-Firewall**.

## Quellen
- [Open WebUI Härtung](https://docs.openwebui.com/getting-started/advanced-topics/hardening/)
- [Docker Compose Networking](https://docs.docker.com/compose/how-tos/networking/)
- [Model Context Protocol](https://modelcontextprotocol.io/specification)

**Hinweis:** Den v0.2-Quellcode erst nach Review als Initial-Commit hinzufügen und dann die CI aktivieren.