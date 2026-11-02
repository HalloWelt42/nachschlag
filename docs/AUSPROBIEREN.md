# Ausprobieren: Beispielcode ausführen und debuggen (WIKI-48)

Entwurf: `mockups/ausprobieren.html` (abgenommen 02.11.2026: "entwurf passt soweit").

## Entscheidungen (Gespräch 02.11.2026)

- Nur am Rechner; am Telefon gibt es den Knopf nicht.
- Gearbeitet wird an einer Kopie des Beispiels; das Original im Artikel bleibt unverändert ("Zurücksetzen" holt es
  wieder, "Behalten" legt die Kopie als eigenes Beispiel ab).
- Der Editor ist gleichwertig zu dem der Codeschmiede (CodeMirror 6, gleiche Funktionen), übernommen statt nachgebaut.
- Gerechnet wird in der Sandbox der Codeschmiede als gemeinsamem Dienst; Läufer und Debugger-Aufzeichnung gibt es einmal.
- Sprachen zuerst: PHP, Python, JavaScript.

## Aufbau

```
Nachschlag (Oberfläche: Ebene Ausprobieren, Editor, Ausgabe, Debugger)
   -> Nachschlag-Backend  POST /api/v1/ausprobieren  (Code, Sprache)
      -> Codeschmiede-Backend über den Verbund, mit dem App-Schlüssel von Nachschlag
         POST /api/v1/sandbox/aufzeichnen | /ausfuehren  (nur Apps auf der Erlaubnisliste "Sandbox für Apps")
         -> Sandbox-Dienst der Codeschmiede (Docker, ohne Netz, nur lesend, Grenzen)
```

- Der Sandbox-Dienst bleibt im Netz der Codeschmiede; offen ist nur die Schnittstelle der Codeschmiede, mit Anmeldung.
- Erlaubnisliste in den Einstellungen der Codeschmiede (Vorgabe: nachschlag); je App höchstens ein Lauf zugleich,
  Code höchstens 20.000 Zeichen, Grenzen der Sandbox wie im Kurs.
- Aufzeichnung (Python, JavaScript): die Funktion `aufzeichnen` der Codeschmiede liefert Schritte mit Zeile, Aufrufstapel,
  Variablen und Ausgabe bis zum Schritt; die Oberfläche spult vor und zurück, springt zu Haltepunkten.
- PHP: neues Sandbox-Abbild (PHP 8.x, Fassung aus "Meine Fassung"); zuerst nur Ausführen mit Ausgabe, die Aufzeichnung
  folgt.
- Editor und Debugger der Oberfläche: die Bausteine der Codeschmiede (`EditorBereich`, `DebuggerBereich`) wandern als
  gemeinsame Bausteine in `appkern-oberflaeche`, statt sie zu kopieren; Codeschmiede und Nachschlag nutzen dieselben.

## Reihenfolge des Baus

1. Codeschmiede: Schnittstelle für Apps (Anmeldung mit App-Schlüssel über den Appkern, Erlaubnisliste, Grenzen), Tests,
   Ausrollen.
2. Nachschlag: Weg zum Ausprobieren über den Verbund (Adresse der Codeschmiede aus dem Verzeichnis), Tests.
3. Appkern-Oberfläche: Editor und Debugger als gemeinsame Bausteine aus der Codeschmiede; die Codeschmiede stellt um.
4. Nachschlag: Ebene Ausprobieren nach dem Entwurf (Knopf am Beispiel, nur am Rechner), Behalten als eigenes Beispiel.
5. PHP-Abbild in der Sandbox, danach die Aufzeichnung für PHP.
