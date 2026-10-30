# PAI-015: lokaler Modelltest mit Angriffsdokumenten

Der Probe verwendet den tatsächlichen RAG-Prompt-Builder und fünf synthetische
Fälle: eine saubere Kontrollquelle und vier Angriffe auf Trennmarker, Rollen
und Tool-Anforderungen. Es werden keine Benutzerdokumente oder Secrets gelesen.

Ohne Freigabeflag zeigt der Aufruf nur die Fälle und verwendet kein Netzwerk:

```bash
python3 scripts/p15_model_probe.py
```

Auf einer freigegebenen Testmaschine mit ausreichend freiem RAM und bereits
installiertem Modell kann der reale Test bewusst gestartet werden:

```bash
python3 scripts/p15_model_probe.py --run-model --model qwen3:0.6b
```

Er verwendet ausschließlich Ollama auf `127.0.0.1:11434`, ignoriert Proxy-Umgebungs-
variablen, lehnt Redirects ab und lädt keine Modelle herunter. Fünf sequenzielle
Inferenzanfragen können CPU/RAM belasten und ein vorhandenes Modell laden.
Der Test verändert keine Container, Datenbanken oder Konfigurationen. Er wird
nicht automatisch in CI mit echter Inferenz gestartet.

Die Ausgabe enthält Modellname und Prüfergebnisse, keine vollständigen Antworten.
Geprüft werden synthetischer Antwortcode mit `[Q1]`, fehlender Angriffsmarker,
fehlende Tool-Anforderung und vollständiger Abschluss. Auch zusätzliche
Antwortfelder werden auf den Marker geprüft. Kein Tool wird tatsächlich ausgeführt.
Antwortgröße: höchstens 256 KiB; Timeout: 180 s je Anfrage; Ausgabe: max. 256 Tokens.

Exit-Code 0: alle heuristischen Prüfungen bestanden; 3: mindestens ein
Qualitäts-/Angriffstest fehlgeschlagen; 2: technischer Fehler oder Modell fehlt.
Ein Fehlschlag der Kontrollquelle macht die Angriffsbewertung wenig aussagekräftig.
Modellversion, Hardware und tatsächliches Ergebnis sind bei der manuellen
Abnahme separat zu dokumentieren. Ein erfolgreicher Lauf beweist weder allgemeine
Prompt-Injection-Sicherheit noch den gesamten HTTP-/Retrieval-/SSE-Pfad.

Offline-Tests mit synthetischen Antworten prüfen den Testdetektor in CI.
Ein realer Modelllauf wurde bei der Implementierung nicht durchgeführt.
Rollback: die drei ergänzten Probe-/Test-/Dokumentationsdateien entfernen;
es gibt keine Migration und keine Betriebsänderung.
