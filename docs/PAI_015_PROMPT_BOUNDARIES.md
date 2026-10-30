# PAI-015 – RAG-Promptgrenzen gegen Dokument-Injection

**Status:** inkrementelle Härtung, keine vollständige Prompt-Injection-Garantie.

## Änderung

Abgerufene Dokumentausschnitte werden nicht mehr zwischen frei formulierbaren
Klartextmarkern in den System-Prompt eingesetzt. Die Console serialisiert die
höchstens drei Quellen stattdessen als kompaktes JSON in genau einem
`untrusted_sources_json`-Block. JSON maskiert Steuerzeichen; zusätzlich werden
`<`, `>` und `&` als Unicode-Escapes übertragen. Ein Dokument kann dadurch
weder den Block mit einem eigenen End-Tag schließen noch eine zusätzliche
Prompt-Rolle erzeugen.

Die Quellen bleiben ausdrücklich unvertrauenswürdige Daten. Der System-Prompt
untersagt Rollenwechsel, Befehle, URLs, Tool-Aufrufe und die Herausgabe von
Geheimnissen aus dem Dokumenttext. Die bestehende Begrenzung auf drei Quellen
mit je 360 Zeichen und der serverfeste Knowledge-Namensraum bleiben erhalten.

## Nachweis und Grenzen

`tests/test_p15_prompt_boundaries.py` verwendet synthetische Angriffstexte mit
alten und neuen Endmarkern, angeblichen Systemrollen, Tool-/Netzwerkaufrufen,
JSON-Codeblöcken und Steuerzeichen. Der Test prüft:

- genau eine Systemrolle und die unveränderte Benutzerfrage,
- genau einen Quellenblock ohne wörtlich einschleusbares End-Tag,
- verlustfreie JSON-Dekodierung der maskierten Daten,
- unveränderte Quellen-ID, PDF-Seite und Source-Cap.

Dies ist eine strukturelle Promptgrenze, keine mathematische Trennung innerhalb
eines LLM. Ein Modell kann unvertrauenswürdigen Inhalt trotz Anweisung falsch
interpretieren. Deshalb bleiben Agenten-Schreibrechte, Netzwerktools und
automatische Tool-Ausführung außerhalb dieses RAG-Pfads. Vor einer späteren
Toolfreigabe sind modellbasierte Angriffstests und eine separate
Autorisierungsschicht weiterhin Pflicht.

## Rollback

Der Commit kann ohne Datenmigration zurückgenommen werden. Datenbank,
Knowledge-API, SSE-Quellenformat und Feature-Flags ändern sich nicht.
