# Lokaler Dokumenteneingang

Nur Dateien ablegen, die ausdrücklich für die Suche freigegeben sind.
Anschließend: `docker compose exec gateway python memcli.py ingest /documents`

Unterstützt UTF-8-Textdateien, Markdown und ausgewählte Code-/Konfigurationsdateien.
Keine PDF-/Office-Parser im MVP. Dateigröße max. 1 MiB je Datei.
Vertrauliche Zugangsdaten, Tokens oder .env-Dateien gehören NICHT hierher.
