# Aufgabenverteilung und Arbeitsvertrag für Entwicklungsagenten

Diese Datei definiert **Rollen und Übergaben**, nicht tatsächlich gestartete parallele Agenten.

## Planungsregel
- Kleine, prüfbare Arbeitspakete; keine Refaktorisierung fremder Pi-Dienste.
- Externe Netz- und Hoständerungen brauchen den expliziten Freigabeschritt des Betreibers.
- Standardbranch `main` bleibt stabil; Feature-Branches heißen `feat/PAI-###-kurz`, Hotfixes `fix/PAI-###-kurz`.
- Commits enthalten keine `.env`, SQLite-Dateien, Tokens, Chatverläufe oder personenbezogene Beispieldaten.
- Keine unbeaufsichtigten Agenten, kein autonomes Pushen von Geheimnissen, kein Docker-Socket in KI-Containern.

## Rollenschnittstellen

**Platform Engineer:** Compose, Backup, Restore, Ressourcenprüfung. Liefert getestete Shell-Skripte und Beispiel-Konfiguration.

**API Engineer:** OpenAI-kompatible Routen, SSE, Timeouts, Fehler- und Payload-Limits. Liefert simulierte Integrations-Tests.

**Memory/MCP Engineer:** SQLite-Migration, isolierte Namespaces, MCP-stdio und Client-Test. Liefert Invarianten und Daten-Schemas.

**Security Reviewer:** Egress/Firewall, Threat Model, Redaction, Image-Pins. Kann Releases blockieren.

**Product Designer:** Journeys, IA, Accessibility, Spezifikation; kein UI-Build ohne abgestimmtes visuelles Ziel.

**QA Engineer:** vollständige Tests, Pi-Abnahme, Benchmark, Restore-Drill und Release-Beweis.

## Übergabeformat pro Aufgabe
1. Ticket-ID, Owner-Rolle, Scope, Nicht-Ziele.
2. Änderungen in Pfaden, Migrationseffekt, Sicherheitsfolgen.
3. Testkommandos und Ergebnisse (simuliert versus echte Hardware).
4. Rollback-Anleitung.
5. Entscheidung 'ready for review' / 'blocked' mit Grund.

## Nächste parallele, konfliktarme Pakete

- Plattform: PAI-001 (nur Skript) und PAI-004 (nur Recovery-Testumgebung).
- Backend: PAI-003 (Gateway-SSE-Simulation).
- Security: PAI-002 (Dokumentation/Host-Regelskript, keine Firewalländerung).
- Product Design: PAI-009 (UX-Flüsse und Informationsarchitektur).
- QA: PAI-005 zunächst Testplan; echte Abnahme erst auf freigegebenem Pi.

**Integration:** Backend-/Security-Gates vor Agentenberechtigungen; Hardware-Abnahme vor UX-Statusanzeigen, die Betriebsdaten versprechen.
