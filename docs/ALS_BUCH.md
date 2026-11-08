# Als Buch (WIKI-45)

Ein Thema wird ein Buch als EPUB und PDF. Eine Vorlage bestimmt Aufbau, Ton und Gestaltung; die KI formt die Artikel
über die Leitstelle um, nur aus dem, was in den Artikeln steht, mit Beleg je Absatz. Danach prüft Nachschlag Zahlen und
Belege gegen das Original und markiert, was dort so nicht steht. Entwürfe: `mockups/export.html`, `export-probe.html`,
`export-vorlage.html`, `export-buecher.html`, `telefon-export.html`.

## Seiten

| Seite | Weg | Inhalt |
|---|---|---|
| Als Buch | `themen/<thema>/buch` (Knopf "Als Buch" am Thema) | Inhalt (Bereiche als Kapitel, an und aus, Reihenfolge ziehen; Notizen, gemerkte Stellen, Bilder, Steckbriefe; Übersetzungen), Vorlage, Umformung (für wen, Länge, Fragen, feste Regeln), Format und Ablage (EPUB, PDF in A5, A4 oder zwei Seiten je A4, Titelbild); rechts Vorschau, Dauer mit Schritten, jetzt oder heute Nacht, Probekapitel, Bauen |
| Probekapitel | `themen/<thema>/buch/probe` | Anfang eines Artikels nach der Vorlage: Original und Ergebnis nebeneinander oder als Buchseite, Belege je Absatz (Zeiger oder Tipp zeigt die Stelle im Original), Prüfung oben, markierte Sätze neu schreiben lassen, anderen Artikel probieren |
| Vorlagen | `themen/<thema>/buch/vorlagen?vorlage=<kennung>` | Mitgelieferte (fest) und eigene; Aufbau aus Teilen (ziehen, entfernen, hinzufügen, eigener Kasten, Text umgeformt oder wie im Buch, Kapitel nach Bereichen oder von A bis Z), Anweisung (Ton, Vorgaben, Zusatz, feste Regeln), Gestaltung (Schrift, Farbe, Bilder); speichert nach jeder Änderung; Weitergeben lädt die Datei herunter |
| Eigene Bücher | `buecher` | Was entsteht (Stufen je Kapitel, Umgeformt, Tempo, fertig gegen, Hinweise; anhalten, fortsetzen, verwerfen) und das Regal (lesen, herunterladen, Hinweise der Prüfung, nachbauen, löschen) |
| Lesen | `buecher/<buch>` | Das Buch in der App, aus demselben Inhalt wie EPUB und PDF |

Am Telefon: Als Buch zeigt Vorlage, Formate und Dauer mit Probekapitel und Bauen unten; Eigene Bücher zeigt die Bücher
als Liste, ein fertiges öffnet als EPUB im Leser des Telefons. Vorlagen bearbeitet man am Rechner.

## Schichten (`backend/app/alsbuch/`)

| Modul | Aufgabe |
|---|---|
| `modell/alsbuch.py` | Modelle an den Grenzen: Vorlage, Bestellung, Schätzung, Buchinhalt, Probe, Regal |
| `teile.py` | Katalog der Teile (Titel, Herkunft, Platz) und Prüfung des Aufbaus |
| `vorlagen.py` | Vorlagen als TOML: mitgelieferte im Paket (`vorlagen/*.toml`), eigene in der Kellerwolke unter `Apps/Nachschlag/Vorlagen/<kennung>.toml` |
| `quelle.py` | Artikel als nummerierte Absätze mit Bildern und bereinigtem XHTML; Stücke fürs Modell (höchstens 10.000 Zeichen, an Überschriften geteilt) |
| `umformung.py` | Anweisungen, Antwortformen, nachsichtiges Lesen der Antworten |
| `pruefung.py` | Zahlen (beide Schreibweisen), Belege, Sätze ohne Beleg (Wortstämme gegen die belegten Absätze) |
| `darstellung.py` | Buchinhalt als XHTML für EPUB, PDF und Leseansicht; Stil aus der Gestaltung |
| `epub.py` | EPUB 3 packen (mimetype, Container, Paket, nav und toc.ncx, Bilder) ohne Abhängigkeit |
| `pdf.py` | Satz mit WeasyPrint, zwei Seiten je A4 mit pypdf |
| `dauer.py` | Schätzung aus dem Tempo des Modells |
| `bilder.py` | Bilder der Bibliothek (groß vom Bildholer, wenn da); WebP wird JPEG |
| `ablage.py` | Bücher in der Kellerwolke unter `Apps/Nachschlag/Bücher/<Thema>/` |
| `speicher.py` | Datenbank: fertige Bücher, Zwischenspeicher der Umformungen, Tempo je Modell, Probe und letzte Bestellung je Thema, Stand laufender Bauten |
| `dienst.py` | Plan, Aufträge (Probekapitel, Buch bauen), Zusammenbau, Regal |
| `api.py` | `/api/v1/meins/buecher`, `/api/v1/buchvorlagen`, Herunterladen unter `/api/v1/inhalt/buecher` und `/api/v1/inhalt/buchvorlagen` |

## Umformung

Nur in Aufträgen über die Leitstelle, mit dem Modell aus der Einstellung "Modell für Bücher" (Gruppe Als Buch). Je
Artikel: Umformen je Stück, eine Anfrage für Auf einen Blick und eigene Kästen; je Kapitel eine für Einleitung, Fragen
und Glossar. Der Bau läuft mit Priorität "hintergrund", das Probekapitel ohne (wer wartet, geht nicht hinten an).

Gleiche Anfrage, gleiches Ergebnis: jedes Ergebnis liegt mit dem Schlüssel aus Modell, Anweisung und Eingabe im
Zwischenspeicher. Ein angehaltener Bau setzt beim Fortsetzen dort fort, wo er war; ein Nachbau nach Änderungen am Thema
formt nur neue und geänderte Artikel um. Was im Probekapitel neu geschrieben wird, gilt auch für den Bau.

Feste Regeln (jede Vorlage): nur was in den Artikeln steht, Beleg je Absatz, Zahlen genau wie im Original. Die Prüfung
markiert, schreibt aber nicht von selbst neu (wie im Entwurf); neu schreiben lässt man im Probekapitel.

## Dauer

Grundlage ist die Hausmessung über die Leitstelle (Qwen3 80B, rund 75 Zeichen je Sekunde). Nach jedem Bau mit
mindestens 20 Sekunden Rechenzeit misst Nachschlag das Tempo des Modells neu und rechnet danach. Was das Modell schreibt,
folgt aus der Länge des Originals und der gewählten Länge; Kästen, Einleitungen, Fragen und Glossar mit ihrer üblichen
Länge. Heute Nacht heißt: im Fenster aus den Einstellungen (Über Nacht); reicht eine Nacht nicht, läuft der Rest in
der nächsten weiter.

## PDF

Gewählt ist WeasyPrint: es setzt dasselbe XHTML wie das EPUB mit Druckstil (Seitengröße, Seitenzahlen, Kopfzeile mit
dem Kapitel, Inhaltsverzeichnis mit Seitenzahlen, Silbentrennung). Eine Quelle für beide Formate statt eines zweiten
Satzes. Das Paket ist reines Python; es braucht Pango und HarfBuzz aus dem System. Im Abbild kommen sie über apt
(`libpango-1.0-0`, `libpangoft2-1.0-0`, `libharfbuzz-subset0`, dazu die Schriften `fonts-liberation2` und
`fonts-dejavu-core`), auf dem Raspberry Pi (arm64) wie auf amd64 aus Debian; geprüft in `python:3.12-slim` für arm64.
Ein ganzer Browser zum Drucken wäre ein Vielfaches größer; reine PDF-Bibliotheken bräuchten einen zweiten Satz neben
dem EPUB.

Am Mac kommen Pango und HarfBuzz aus Homebrew; WeasyPrint findet sie mit `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
(für Backend und Tests). Ohne sie sagt die Seite Als Buch, dass PDF hier nicht geht; EPUB geht immer, und der Test des
Satzes wird übersprungen.

## Ablage

| Was | Wo |
|---|---|
| Eigene Vorlagen | Kellerwolke `Apps/Nachschlag/Vorlagen/<kennung>.toml` (was dort abgelegt wird, erscheint in der Liste) |
| Bücher | Kellerwolke `Apps/Nachschlag/Bücher/<Thema>/<Thema> - <Vorlage>.epub` und `.pdf` |
| Inhalt, Stand, Zwischenspeicher | Datenbank der App (`nachschlag_alsbuch`) |

## Bewusst nicht gebaut

- Vorlesen eines Buchs (Knopf im Entwurf bei Vorlesebuch): Vertonen geht über Über Nacht am Thema.
- Als Buch aus dem Merkzettel (Auswahl): der Einstieg ist das Thema.
- Urheber und Lizenz für Bücher außerhalb der Wikis von Wikimedia: die ZIM-Dateien nennen sie nicht; dort steht "wie in
  der Quelle angegeben". Bilder tragen Urheber und Lizenz, sobald der Bildholer das große Bild hat.
