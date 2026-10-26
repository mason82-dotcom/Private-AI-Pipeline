# Rechercheprotokoll – Stand 25.10.2026

Ausgangspunkt: https://www.reddit.com/r/SATNA_PROJECT/comments/1xddu0a/how_to_build_a_100_free_local_ai_coding_setup_on/

## Auswertung der fünf Referenzen

| Projekt | geprüfte Quelle | Entscheidung |
| --- | --- | --- |
| Open WebUI | https://docs.openwebui.com/getting-started/quick-start/ | Pi-ARM64 unterstützt, als lokale Chat-UI geeignet; Docker-Image/Account-Setup vorher prüfen. |
| OpenDesign | https://github.com/nexu-io/open-design | Kein Bestandteil des Server-Stacks, eher Desktop-/Agententool. Local-first ≠ garantiert offline; README beschreibt bestimmte Telemetrie. |
| claude-mem | https://github.com/thedotmack/claude-mem | Projektreferenz für später; nicht ungeprüft als 'automatisch 100 % offline' deklarieren. Lokaler, expliziter MCP-Speicher im MVP vermeidet die anfängliche Integrationskomplexität. |
| OmniRoute | https://github.com/cheaper-inference/OmniRoute | Reddit-Link `omniroute/omniroute` ungültig. Reales Projekt existiert, bietet auch viele Cloudanbieter. Für strict-local-V1 vermeiden wir unbeabsichtigte Fallbacks. |
| RAGFlow | https://github.com/infiniflow/ragflow/blob/main/docs/quickstart.mdx | Empfohlene Startressourcen 4 CPU, 16 GB RAM, 50 GB Disk; aktueller nativer Docker-Build nur x86-64. Nicht auf 8-GB-Pi. |

Weitere Referenzen:
- Open WebUI Config: https://docs.openwebui.com/reference/env-configuration/
- Open WebUI Offline: https://docs.openwebui.com/tutorials/maintenance/offline-mode/
- Ollama Inferenz-Runtime: https://github.com/ollama/ollama
- Modellgrößen: https://ollama.com/library/qwen3

## Hardwarebezogene Entscheidung

Pi 5 / 8 GB: UI + kleines Python-Gateway + SQLite-Suche; Docker-Volumes möglichst auf SSD. Offline-Modell auf dem Pi nur nach Auslastungsmessung. Ein vorhandener PC mit Nvidia GTX 1050 Ti 4 GB eignet sich eher für kleinere quantisierte Modelle; hochwertige große Coding-Modelle sind dafür nicht realistisch ohne CPU-/RAM-Offloading und Latenznachteile.

Auf Ollama sind Qwen3 1.7B (ungefähr 1,4 GB Download) und Qwen3 4B (ungefähr 2,5 GB Download) verfügbar. Downloadgröße =/= maximaler RAM/VRAM-Verbrauch. `qwen3:1.7b` dient als leichter Funktionstest und nicht als gleichwertiger Ersatz für leistungsfähige Cloud-Coding-Modelle.

## Präzise Datenschutzannahmen

- Free/open source: keine obligatorischen API-Abos. Hardware, Strom, Speicher, Updates bleiben eigene Kosten.
- Datenpfad: Chat im WebUI-Volume; Kopie der Anfrage bei lokalem Ollama; explizit gespeicherte Notizen im SQLite-Volume; keine sonstigen automatischen Erfassungen im eigenen Gateway.
- Offlineschalter: `OFFLINE_MODE=true` beeinflusst Open WebUI-Anwendungsfunktionen. Er ist **keine Netzwerk-Firewall**.
- Lokal im LAN ist nicht gleich auf demselben Gerät. Wer vollständige physische Isolation will, lädt Images/Modelle vor und trennt die Inferenzmaschine extern vom Internet.
- MCP-Tools ermöglichen absichtliche Gedächtnisänderungen durch lokale Agenten. Daher nur für vertrauenswürdige Agenten freigeben.
- FTS5 liefert termbasierte Treffer und kann semantisch verwandte Begriffe übersehen. Dafür sind keine Embedding-Downloads und keine zusätzliche Vector-DB notwendig.

## Noch zu validierende Kompatibilität

- Echte Open-WebUI-Verbindung über OpenAI-kompatiblen Gateway gegen aktuelle gepinnte Version
- Echte Ollama-Antworten inkl. Fehlern, Modelllisten, SSE/Timeouts, embeddings
- Saubere Ressourcenlimits und Firewall-Blockade auf Raspberry Pi 5
- MCP stdio-Kompatibilität mit ausgewählter realer Codex-/Hermes-Version
- Open WebUI Offline-Start ohne lokale SentenceTransformer-Caches, besonders bei PDF-Upload

## Lizenzhinweis

Die MIT-Lizenz im ZIP gilt **nur für den eigens erstellten Pipeline-Quellcode**.
Open WebUI, Ollama, Modellgewichte und optionale Komponenten verbleiben unter ihren **jeweils eigenen Lizenzen**. Die Container-Images und Modellgewichte sind nicht Bestandteil des Archivs.
