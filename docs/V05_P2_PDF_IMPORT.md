# P2.1 — PDF-Import mit Seiten-Fundstellen (experimentell)

## Umfang

- Zusätzlicher optionaler POST-Payload: `{"filename":"beispiel.pdf","pdf_base64":"..."}` auf der bestehenden, authentifizierten Import-Route.
- Browser → Console (Session + CSRF) → Gateway (separater Knowledge-Token).
- PDF ≤ 1 MiB, 1–16 Seiten, maximal 96 KiB extrahierter UTF-8-Text, Parser-Timeout 18 s sowie CPU-/Adressraumbegrenzung.
- Optionaler textbasierter PDF-Parser `pypdf==5.9.0` wird ins Gateway-Image eingebaut (Image-Bau benötigt ggf. Netz; Laufzeit offline).
- Extrahierter Text wird seitenweise in SQLite-FTS5 gespeichert; Quellen: `pdf:<dokument-id>:p<seite>#<chunk>`.
- Suchtreffer erhalten `filename`, `page`, `document_id`. Die Original-PDF wird **nicht** dauerhaft gespeichert.
- Alte Textimporte `.txt`, `.md`, `.rst` bleiben unverändert.

## Sicherheit und Grenzen

- Standardmäßig gesperrt: `KNOWLEDGE_IMPORT_ENABLED=false` in beiden Containern.
- Keine OCR für Scans, keine verschlüsselten PDFs, keine Annahme von Dateipfaden, keine Ausführung von Links oder Anhängen.
- Parser arbeitet in einem kurzlebigen subprocess mit Zeit-, CPU- und Adressraumlimit sowie minimalem Environment. **Keine vollständige Sandbox**; für nicht vertrauenswürdige PDFs zusätzlichen Security-Review durchführen.
- Keine cloudbasierten Parser, keine neue öffentliche Portfreigabe und keine ungeprüfte Speicher-Injektion in Chat-Nachrichten.
- Wegen möglicher PDF-Parser-Schwachstellen Sicherheitsupdates und Dependency-Pinning vor einem produktiven Einsatz erneut überprüfen.

## Tests und Rollout

```bash
python3 -m unittest discover -s tests -v
node --check console/static/app.js
node tests/test_chat_history.cjs
```

PDF-Tests: Mehrseitigkeit, Seite-2-Suche, SHA-Deduplizierung, Namespace-Trennung, CSRF, gesperrter Import, leere Textebene, verschlüsseltes/zu großes PDF, >16 Seiten.

Das lokale Testsystem hat die spezifischen PDF-Tests bestanden; die vollständige Regression muss auf dem aktuellen Feature-Branch durch CI bestätigt werden. Raspberry-Pi-Docker-/ARM64-Abnahme steht aus. Zuerst SQLite-Backup prüfen, dann nur nach expliziter Testfreigabe das Import-Flag temporär aktivieren und danach wieder deaktivieren.

Nächste P2-Stufe: semantische Suche und Chat-RAG mit begrenzter Anzahl lokaler Quellen. Diese sind **noch nicht implementiert**.
