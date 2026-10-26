# Private AI Pipeline – Light Console (Designprototyp)

**Stand:** 2026-10-25 · **UI-Konzept:** v0.1 · **Implementierung:** Statisches HTML/CSS/JavaScript ohne Paketmanager oder externe Ressourcen.

## Start

`index.html` im Browser öffnen oder lokal mit `python3 -m http.server 8098 --bind 127.0.0.1` aus diesem Verzeichnis bereitstellen, dann `http://127.0.0.1:8098` öffnen.

**ACHTUNG: Dies ist ausschließlich ein Frontend-Demoprototyp.** Er verbindet sich mit keiner API, führt kein Modell aus, prüft keine echten Systemzustände und speichert keine Nutzdaten dauerhaft. Chat-Eingaben werden nur zur Laufzeit in der Ansicht simuliert. Dateiauswahl liest nur den Dateinamen und die Größe (niemals Inhalte). Es gibt keine `fetch`, WebSocket-, Analytics-, Font- oder CDN-Requests. Alle dargestellten Daten sind illustrative Beispiele.

## Bedienbare Bereiche

- Übersicht: statische Beispielkennzahlen, Arbeitsbereichswahl, Schnellzugriff
- Chat: Modellwahl, Nachrichteneingabe mit klar als Simulation markierter Antwort
- Wissensbasis: Suche nach Dateinamen/Projekten, Dateiauswahl-Demo
- Gedächtnis: projektspezifische Filter, Demo-Einträge hinzufügen und entfernen
- Agenten: Leserechte und schreibende Toolfreigabe als **reine UI-Simulation**, keine Sicherheitswirkung
- Modelle: Wechsel des dargestellten Beispielmodells
- Systemstatus: klare Kennzeichnung „Nicht geprüft“, keine erfundenen Live-Metriken
- Einstellungen: kompakte bzw. normale UI-Dichte
- Schnellsuche über `Ctrl + K` / `⌘ + K`, mobile Off-Canvas-Navigation

## Visuelles System

| Token | Wert | Verwendung |
|---|---|---|
| `--paper` | `#f6f8fb` | Hintergrund |
| `--surface` | `#ffffff` | Karten und Sidebar |
| `--text` | `#17253a` | Primärtext |
| `--text2` | `#586a80` | Sekundärtext |
| `--blue` | `#3c6ddf` | Interaktion und aktive Elemente |
| `--teal` | `#169a82` | vertrauenswürdige Infozustände |
| `--amber` | `#be862a` | Unklar / nicht geprüft |
| `--line` | `#e6ebf1` | Trennlinien |
| `--radius` | `12px` | Container |
| `--nav-width` | `236px` | Navigation |

Keine heruntergeladenen Webfonts. UI-Systemschrift, die auf Windows, Linux und Android funktioniert. Abstände orientieren sich an 4/8px; Inhaltsbreite maximal 1620px; Mobile-Menü ab 760px.

## Architekturentscheidung

Die Designoberfläche ersetzt **nicht** Open WebUI oder dessen Login-/Chatmechanismen. Sie ist ein potenzielles ergänzendes *Admin-Control-Center* mit eigenem gesicherten Status-Backend, während die eigentliche Chatfunktion zunächst Open WebUI bleibt. Für die produktive Umsetzung sind Authentifizierung, CSRF-Schutz, Autorisierung pro Namespace, serverseitig geprüfte MCP-Policies, Status-Schemata, CORS/Origin-Restriktion, Request-Limits und Offline-Nachweise erforderlich.

## Weiterentwicklung

1. PAI-009: Flows mit Nutzertests validieren, Designfreigabe.
2. PAI-016: Light Console in separat testbares Frontend übertragen (keine Live-Daten ohne Backend-Vertrag).
3. Neue schreibgeschützte API: `/api/control/status`, `/api/control/models`, `/api/control/knowledge`, `/api/control/memory`, `/api/control/agents` nach Bedrohungsmodell.
4. Erst nach Auth/ACL/CSRF-Review: Schreib- und Löschaktionen. Secrets niemals als frei editierbares Feld im Frontend.
5. Playwright: responsive Layout und Tastatur-Bedienung auf Chromium/Firefox/WebKit prüfen; Accessibility-Audit ergänzen.
