# Ausprobieren: Beispielcode ausführen und debuggen (WIKI-48)

Entwurf: `mockups/ausprobieren.html` (abgenommen 02.11.2026).

## Entscheidungen (02.11.2026)

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

## Schnitt der gemeinsamen Bausteine (Schritt 3)

- Eigener Eingang `appkern-oberflaeche/code` (Ordner `oberflaeche/code/` im Appkern): `EditorBereich`,
  `DebuggerBereich`, `Speicherbild`, `DebugSitzung`, die Steuerung des Debuggers und die Typen der Aufzeichnung. Apps
  ohne Code laden kein CodeMirror, weil der Haupteingang davon nichts weiß.
- Farben nur aus den Marken: das Schema des Editors steht als Abschnitt "Editor" (`--ed-*`) in `marken.css`, dazu die
  Farben des Speicherbilds; alles Übrige nutzt die bekannten Marken (`--akzent`, `--text-2`, `--rand`,
  `--schrift-code`, ...). Die Bausteine bringen ihren Stil selbst mit und hängen an keiner Klasse einer App.
- `DebugSitzung` kennt keine Schnittstelle: wer sie startet, gibt die Funktion mit, die einen Lauf aufzeichnet
  (Codeschmiede: Aufgabe mit Eingabe, Nachschlag: `POST /api/v1/ausprobieren`).
- Sprachen des Editors: Python, JavaScript, PHP, HTML, CSS, SQL, Markdown.
- Codeschmiede stellt um: Thema am `<html>` als `hell`/`dunkel` wie der Appkern, lädt `marken.css` und ordnet an einer
  Stelle die Marken ihren eigenen Farben und Schriften zu; ihre Kopien von Editor, Debugger und Speicherbild entfallen.

## Ebene Ausprobieren in Nachschlag (Schritt 4)

- Knopf "Ausprobieren" vor "Kopieren" an jedem Codeblock in einer Sprache, die die Sandbox gerade kann (Stand aus
  `GET /api/v1/ausprobieren`); nur am Rechner. Die Sprache nennt gefärbter Code selbst (`data-sprache` vom Backend,
  sonst die Färbung im Browser). Code ohne Kopf bekommt die Knöpfe oben rechts über dem Code.
- Die Ebene arbeitet an einer Kopie: Ausführen (Strg Enter) zeigt die Ausgabe, Debuggen den aufgezeichneten Lauf;
  beides ist derselbe Probelauf als Aufzeichner der `DebugSitzung`. Zurücksetzen holt das Original, Escape schließt.
- Behalten legt die Kopie mit einem Namen als eigenes Beispiel ab (`/api/v1/meins/beispiele`, je Konto, Buch über
  seinen Namen ohne Datum). Es steht im Artikel direkt unter dem Codeblock, aus dem es stammt (Nummer des Blocks wie
  bei den Kommentaren; fehlt er in einer neuen Fassung, am Ende des Texts), mit Ausprobieren, Kopieren und Löschen in
  zwei Klicks. Aus einem eigenen Beispiel geöffnet, speichert Behalten dieses.
- Die Ebene wird erst beim Öffnen geladen; Editor und Debugger (CodeMirror) braucht nur, wer etwas ausprobiert.

## PHP mit Fassungen (Schritt 5, WIKI-52)

Entscheidungen (02.11.2026): PHP-Fassungen 5.6, 7.4 und 8.0 bis 8.5, je eine als eigenes Abbild der Sandbox;
der Editor kennt die Funktionen jeder Fassung aus der Sandbox selbst. Die Fassung lässt sich passend zum Code in der
Ansicht zum Ausführen wechseln, und der Editor zeigt, welche Befehle es in einer älteren Fassung nicht gibt.

- Codeschmiede: die Fassungen stehen nur in `sandbox/laufzeiten.py` (Laufzeit `php-8.3`, Abbild
  `codeschmiede-sandbox:php-8.3` aus `sandbox-bilder/php.Dockerfile`). Für Apps: `GET /api/v1/sandbox/sprachen`
  (Sprachen, Fassungen, ob aufgezeichnet wird), `POST /api/v1/sandbox/ausfuehren` (Ausgabe, Hinweise, Fehler mit
  Zeile) und `GET /api/v1/sandbox/funktionen/php` (je Fassung die eingebauten Funktionen).
- Nachschlag nimmt das Angebot von der Codeschmiede (keine eigene Liste). PHP läuft ohne Aufzeichnung: kein Debugger,
  keine Haltepunkte; Hinweise (Warnungen) stehen unter der Ausgabe, die Zeile eines Fehlers ist im Editor markiert.
- Die Ebene beginnt mit Meine Fassung des Buchs (genau sie, sonst die neueste ihrer Reihe, "8" ergibt 8.5) und lässt
  die Fassung im Kopf wählen. Ein Wechsel lässt einen gezeigten Lauf in der neuen Fassung gleich noch einmal laufen.
- Der Editor (Appkern, `Funktionsbestand`) unterstreicht Aufrufe, die es in der gewählten Fassung nicht gibt, mit dem
  Hinweis, ab oder bis wann es sie gibt; die Vervollständigung bietet die Funktionen der Fassung an. Was keine Fassung
  kennt (Erweiterungen ohne Abbild), bleibt unmarkiert.
- Eigene Beispiele merken sich die Fassung, in der sie liefen.

## Reihenfolge des Baus

1. Codeschmiede: Schnittstelle für Apps (Anmeldung mit App-Schlüssel über den Appkern, Erlaubnisliste, Grenzen), Tests,
   Ausrollen.
2. Nachschlag: Weg zum Ausprobieren über den Verbund (Adresse der Codeschmiede aus dem Verzeichnis), Tests.
3. Appkern-Oberfläche: Editor und Debugger als gemeinsame Bausteine aus der Codeschmiede; die Codeschmiede stellt um.
4. Nachschlag: Ebene Ausprobieren nach dem Entwurf (Knopf am Beispiel, nur am Rechner), Behalten als eigenes Beispiel.
5. PHP-Abbilder je Fassung in der Sandbox, Wahl der Fassung und Funktionsbestand im Editor (WIKI-52); danach die
   Aufzeichnung für PHP.
