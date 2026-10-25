# Sprint 01 — v0.2 stabilisieren (2 Wochen, Planungsfenster)

**Sprint-Ziel:** Technische Basis auf einem isolierten Testsystem nachvollziehbar abnehmen, ohne bestehende Pi-Dienste zu verändern.

## Parallele Arbeitsstränge

| Strang | Rolle | Arbeitstage 1–3 | Arbeitstage 4–7 | Arbeitstage 8–10 | Übergabe |
|---|---|---|---|---|---|
| A | Plattform | PAI-001 Read-only Host-Audit | PAI-004 Backup/Restore auf Testvolumes | Pi-Freigabe-Vorbereitung | QA |
| B | Backend | PAI-003 SSE/Fault-Tests | API-Vertrag stabilisieren | Gateway-Releasebericht | QA + Security |
| C | Security | PAI-002 Firewall/No-Egress-Design | Gegenprobe mit simuliertem Ollama | PAI-006 Signup und Netzgrenzen | QA |
| D | Product Design | J1/J2: Einrichtungs- und Importflow | J3–J5 Fehler-/Freigabeflow | Review der Daten- und Fehlerzustände | PO |
| E | QA | Testmatrix/Synthetikdaten | Simulierte Integrations- und Restore-Tests | PAI-005 echte Hardware-Abnahme | PO/Release |

Es handelt sich um **zugewiesene Verantwortungsbereiche**, nicht um aktive Hintergrundausführung. Der reale Betreiber muss Gerätezugriff und Firewalländerungen gesondert freigeben.

## Tagesabschlusskriterien

- Tag 3: Host-Inventar dokumentiert, keine Portkollision, Testmatrix und Mock-Ollama reproduzierbar.
- Tag 7: Gateway-/Restore-Tests bestanden; LAN-Policy demonstriert erlaubte und unerlaubte Ziele.
- Tag 10: Pi-/Windows-Live-Abnahme oder **klarer Blocker mit reproduzierbarem Beleg**, kein künstliches 'grün'.

## Go / No-Go

**Go** nur bei: keinerlei Änderungen an fremden Diensten; Login/SSE/Memory funktionieren; Offline- und LAN-Profile sind nachvollziehbar getrennt; Restore-Test erfolgreich.

**No-Go** bei: offener HTTP-Port auf 0.0.0.0, unerwünschtem WAN-Egress, nicht funktionierendem Restore, Namespace-Leak, verlorenen Anmeldedaten, ungetestetem unprivilegiertem Docker-Betrieb.

## Issue-Links

- [PAI-001 Host-Audit](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/1)
- [PAI-002 Egress-Policy](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/2)
- [PAI-003 Gateway/SSE](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/3)
- [PAI-004 Backup/Restore](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/4)
- [PAI-005 Hardware-Abnahme](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/5)
- [PAI-006 Signup](https://github.com/mason82-dotcom/Private-AI-Pipeline/issues/6)
