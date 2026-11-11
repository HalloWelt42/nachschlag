# Bücherlader

Der Bücherlader sieht das Verzeichnis der Bücher durch, meldet Neues und lädt abonnierte Bücher (WIKI-57, Entwurf
WIKI-2). Er ist eine eigene Schicht in `backend/app/buecherlader/` und der einzige Teil von Nachschlag, der in den Ordner
der Bücher schreibt. Alles, was länger läuft, ist ein Auftrag des Appkerns (Seite Aufträge, Fußleiste).

## Entscheidungen (07.11.2026)

- Quelle ist das Verzeichnis der Dateien (eine Seite je Bereich, wie ein Webserver Ordner zeigt). Titel, Beschreibung
  und Zahl der Artikel kommen wahlweise aus dem Katalog der Bücher.
- Nur die gewählten Sprachen (Vorgabe Deutsch und Englisch, Mehrsprachige auf Wunsch).
- Einmal je Woche das ganze Verzeichnis (einstellbar: täglich, wöchentlich, monatlich). Der erste Durchgang ist eine
  Erstaufnahme: nichts gilt als neu.
- Abonnierte Bücher laden von selbst. Eine neue Fassung eines Buchs, das schon da ist, wird geladen und geprüft und
  wartet dann, bis jemand umschaltet. Die vorige bleibt als Rückfall (Vorgabe 14 Tage) und wird danach gelöscht, nie,
  wenn sie von Hand wieder aktiv gesetzt ist (Archiv der Quellen).
- Platz: frei bleibt immer die Reserve aus den Einstellungen (Vorgabe 200 GB), geprüft vor jedem Laden und laufend
  währenddessen; dazu wahlweise eine Grenze für alle Bücher.
- Bücher ohne eigenen Baustein öffnen in der Originalansicht und tragen sichtbar "Eigene Ansicht fehlt" mit dem
  Erzeuger; die Bibliothek fasst oben zusammen, für welche Erzeuger eine Ansicht fehlt.
- Nur geänderte Artikel neu indexieren und einbetten (WIKI-58):
  - Eigener Index: jede Seite trägt einen Abdruck ihres Rohinhalts. Der Index einer neuen Fassung übernimmt alles mit
    gleichem Pfad und Abdruck aus dem Index der vorigen (auch Metadaten und übergangene Seiten); aufbereitet wird nur
    Neues und Geändertes. Nachschlag nennt dem Index-Dienst die Vorlage; der nimmt seine Kopie oder holt sie bei Nachschlag.
  - Bedeutungssuche: der Fundus führt eine neue Fassung als dieselben Dokumente zu und bettet nur geänderte Abschnitte
    ein. Er meldet unter `/api/v1/quellenstand/dateien`, welche ZIM-Dateien er noch liest; der Bücherlader löscht eine
    vorige Fassung erst, wenn sie dort fehlt (antwortet der Fundus nicht, bleibt sie).
  - Die Einstellung "Quelle der Bedeutungssuche" nennt eine Datei mit Stand und gilt nach dem Umschalten für die neue.

## Teile

| Datei | Aufgabe |
|---|---|
| `verzeichnis.py` | Verzeichnisseiten aller Spiegel lesen (Apache, lighttpd, nginx): Bereiche, Dateien, Stamm, Sprache, Stand |
| `katalog.py` | Katalog lesen (Bücher mit Angaben und Ladedatei) und Ladedateien (meta4: Prüfsumme, Spiegel) |
| `quellen.py` | Schnittstelle Quelle (Verzeichnis, Katalog, eigener Ordner) und die Vereinigungsmenge aller Quellen mit Bezugsquellen |
| `bestand.py` | Datenbank: Bücher und Fassungen mit dem Durchgang, in dem sie zuerst auftauchten, Durchgänge, Abos, Wechsel |
| `ablage.py` | Dateien im Ordner der Bücher: Bibliothek, `.laden/` (angefangen), `.neu/` (wartet aufs Umschalten) |
| `bibliotheksliste.py` | `library.xml` für einen Bücherserver neben Nachschlag nachziehen (wahlweise) |
| `dienst.py` | Zeitplan, Durchsicht, Abos, Laden, Umschalten, Rückfall, Aufräumen, Stand und Verzeichnis |
| `api.py` | `/api/v1/buecherlader` |

Ein Stamm ist der Dateiname ohne Stand (`wikipedia_de_all_maxi`): ein Buch in einer Ausgabe. Abos gelten je Stamm.

## Quellen (WIKI-62)

Quellen stehen als Liste im Bücherlader (Bibliothek, Fassungen und Laden): an oder aus, Reihenfolge, hinzufügen,
entfernen, Vorschläge aus der Spiegelliste der offiziellen Ladedatei. Erste Quellen: der Katalog der Bücher und die
Spiegel der Uni Erlangen, von dotsrc.org (Uni Aalborg), des Academic Computer Club Umeå und von NLUUG. Jede Durchsicht
liest alle eingeschalteten; eine, die nicht antwortet, fehlt mit Hinweis. Bittet ein Spiegel um Geduld (429, 503),
wartet der Lader und fragt erneut.

Vereinigung: je Buch und Stand ein Eintrag mit den Bezugsquellen aller Quellen, die die Datei haben, und den
zusammengeführten Angaben (Katalog vor Verzeichnis; Titel, Beschreibung, Artikel, Medien, Autor, Herausgeber,
Kategorie, Schlagworte, Bilder, Videos, Volltextindex, Datum; keine fremden Vorschaubilder).

### Eigene Bücher (WIKI-87)

Quellenart "Eigener Ordner": ein Ordner auf dem Rechner der App, darin ein Unterordner je Bereich mit den ZIM-Dateien
(Name `<stamm>_<JJJJ-MM>.zim` wie bei den Spiegeln) und je Datei die Prüfsumme daneben (`<datei>.sha256`, erstes Wort).
Ein anderes Programm legt neue Fassungen hinein, etwa das Buch der Dateiformate (`python -m dateiformate ausliefern`
im privaten Repo dateiformate, nach `/mnt/data/nachschlag/daten/eigene-buecher/other/`, in der App
`/app/daten/eigene-buecher`). Der Bücherlader führt diese Bücher wie jedes andere: Abo, Fassungen, Umschalten,
Rückfall. Geladen wird durch Kopieren (fortsetzbar), geprüft gegen die Prüfsumme daneben; ohne sie lädt nichts.

## Ablauf beim Laden

1. Prüfsumme (SHA-256) und weitere Spiegel aus der Ladedatei holen, sonst aus der Quelle der Prüfsummen; ohne Prüfsumme
   lädt nichts.
2. Reserve und Grenze prüfen; passt die Datei nicht, wird sie gemeldet statt geladen. Der Zeitplan (alle 15 Minuten)
   holt das nach, sobald Platz ist.
3. Laden in `.laden/`, fortsetzbar über Bereichsanfragen, von der ersten Bezugsquelle in der Reihenfolge der Quellen;
   liefert sie nicht, setzt die nächste an derselben Stelle fort. Alle 256 MB wird der freie Platz gegen die Reserve
   geprüft.
4. Prüfsumme rechnen; stimmt sie nicht, wird die Datei gelöscht.
5. Datei öffnen und zählen.
6. Ablegen: ein neues Buch direkt in die Bibliothek (und in die Liste), eine neue Fassung nach `.neu/`.

## Oberfläche

Seite Bibliothek mit den Reitern Meine Bücher, Katalog sowie Fassungen und Laden. Neues seit der letzten Durchsicht
zeigt die Zahl am Menüpunkt und ein Band auf der Startseite; wer den Katalog öffnet, hat es gesehen. Die Regeln stehen
unter Einstellungen, Bücherlader.
