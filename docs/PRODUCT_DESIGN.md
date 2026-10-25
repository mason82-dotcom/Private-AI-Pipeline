# Product Design — Funktions- und UX-Spezifikation

**Design-Brief:** Eine lokal betriebene, datenschutzorientierte Entwickler-KI soll auch bei fehlendem Modell, Offline-Modus und begrenztem Raspberry-Pi-Arbeitsspeicher verständlich und sicher bedienbar sein. Das Ziel ist kein Open-WebUI-Redesign, sondern eine schlanke Verwaltungsoberfläche für den bestehenden Kern.

## Informationsarchitektur

```text
Open WebUI Chat (bestehender Standard)
└── Private AI Verwaltung (künftiger modularer Einstieg)
    ├── Übersicht       Modellstatus, Offline/LAN-Modus, Dienste, Ressourcen
    ├── Wissen          Dateien, Indizierung, Zitierquellen, Suchvorschau
    ├── Gedächtnis      Projekt-Namespace, Einträge, Freigaben, Löschung
    ├── Agenten         verbundene Clients, erlaubte Tools, Freigabeanfragen
    └── Administration  Netzwerkmodus, Datensicherung, Updates, Audit
```

## Kern-Journeys

| Journey | Einstieg | Erfolgszustand | Fehlerzustand/Recovery |
|---|---|---|---|
| J1 Ersteinrichtung | Admin öffnet lokale URL | Login, lokales Modell erkannt, Chat verfügbar | Ollama offline → Diagnose + expliziter lokaler Zielhost, **kein Cloud-Fallback** |
| J2 Wissensimport | Projekt wählen und Dateien hinzufügen | Dateianzahl, Quellpfade, erfolgreich indexiert | zu groß/falsches Format → Datei einzeln abgelehnt, Grund genannt |
| J3 Frage mit Quellen | Frage zu Projektdateien | Antwort mit überprüfbarem Zitat/Quellpfad | keine Treffer → 'Keine geeignete Quelle' statt erfundene Belege |
| J4 Erinnerung freigeben | Agent bittet um Schreibzugriff | Nutzer bestätigt Inhalt, Namespace und Haltbarkeit | abgelehnt/Timeout → keine Änderung |
| J5 Wiederherstellung | Operator öffnet Systemstatus | Backup-/Restore-Testrun dokumentiert | Sicherung unvollständig → rot markierter Blocker, keine Erfolgsmeldung |

## Konzept der Bildschirmzustände

- **Overview:** Statusindikatoren 'WebUI', 'Gateway', 'Modell', 'Memory'; letzte erfolgreiche Prüfung; Modus sichtbar. Ausgabewerte niemals als 'Live' deklarieren, wenn sie aus Cache stammen.
- **Knowledge:** Quellenliste mit Titel, Pfad, Namespace, Zeitstempel, Typ, Import-/Indexstatus; Mehrfachimport dedupliziert; Löschvorschau.
- **Memory:** Trennung persönlicher und projektbezogener Erinnerungen, read-only als Default, Filter nach Quelle, Export und bestätigtes Löschen.
- **Agents:** Tool-Typ (read/write/network/exec), Berechtigung, Zielpfad, Gültigkeit und Begründung. Kein Ein-Klick 'Alles erlauben'.
- **System:** Sicherungsdatum, Prüfsumme, Plan-/Ist-RAM, Netzmodus, Warnungen und Link zu lokalem Testreport.

## UX-Richtlinien

- Desktop ab 1280 px als Operator-Arbeitsfläche, mobile ab 360 px als Diagnose-/Chat-Ansicht.
- WCAG 2.2 AA als Ziel für Kontrast, Fokus, Fehlermeldungen und Tastaturinteraktion.
- Status nie ausschließlich durch Farbe kodieren. Datensicherungs- und Löschvorgänge mit klarer Folgenbeschreibung.
- Keine nutzlosen Dashboard-Kacheln; wichtiger als Animation sind erreichbare Modelle, belegbare Quellen und nachvollziehbare Freigaben.
- Kein automatisches Speichern von Prompts im **eigenen** Memory-Modul. Der bestehende WebUI-Chatverlauf wird von Open WebUI separat gespeichert; dies muss im UI transparent sein.

## Spezifikation für Prototyp- und UI-Abnahme (kein Mockup gebaut)

1. Navigierbarer UX-Fluss für J1–J5, Desktop + Mobile.
2. Jeder Screen mit Empty/Loading/Error/Success.
3. Nutzertest: Modell offline, falsches Netz, veraltete Daten, nicht erlaubte Speicher-Schreiboperation.
4. Erst danach UI-Implementierungs-PR. Bis dahin bestehendes Open WebUI verwenden.

## Offene Entscheidungen (Owner PO)

- Wird die Verwaltung als eigener kleiner Webdienst oder als Open-WebUI-Integration bereitgestellt?
- Ist ein einzelnes Benutzerkonto die dauerhafte Zielgruppe oder gibt es später mehrere Vertrauensdomänen?
- Wird der Zugriff nur via Tailscale-HTTPS oder auch physischem LAN zugelassen?
