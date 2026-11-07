# Bücherlader

Der Bücherlader sieht das Verzeichnis der Bücher durch, meldet Neues und lädt abonnierte Bücher (WIKI-57, Entwurf
WIKI-2). Er ist eine eigene Schicht in `backend/app/buecherlader/` und der einzige Teil von Nachschlag, der in den Ordner
der Bücher schreibt. Alles, was länger läuft, ist ein Auftrag des Appkerns (Seite Aufträge, Fußleiste).

## Entscheidungen (Gespräch am 07.11.2026)

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
- Nur geänderte Artikel neu indexieren und einbetten: eigenes Ticket WIKI-58.

## Teile

| Datei | Aufgabe |
|---|---|
| `verzeichnis.py` | Verzeichnisseiten lesen: Bereiche, Dateien, Stamm, Sprache und Stand aus dem Namen (reine Funktionen) |
| `katalog.py` | Titel und Beschreibung aus dem Katalog, über den Dateinamen im Verweis zugeordnet |
| `bestand.py` | Datenbank: Bücher und Fassungen mit dem Durchgang, in dem sie zuerst auftauchten, Durchgänge, Abos, Wechsel |
| `ablage.py` | Dateien im Ordner der Bücher: Bibliothek, `.laden/` (angefangen), `.neu/` (wartet aufs Umschalten) |
| `bibliotheksliste.py` | `library.xml` für einen Bücherserver neben Nachschlag nachziehen (wahlweise) |
| `dienst.py` | Zeitplan, Durchsicht, Abos, Laden, Umschalten, Rückfall, Aufräumen, Stand und Verzeichnis |
| `api.py` | `/api/v1/buecherlader` |

Ein Stamm ist der Dateiname ohne Stand (`wikipedia_de_all_maxi`): ein Buch in einer Ausgabe. Abos gelten je Stamm.

## Ablauf beim Laden

1. Prüfsumme (SHA-256) holen; ohne Prüfsumme lädt nichts.
2. Reserve und Grenze prüfen; passt die Datei nicht, wird sie gemeldet statt geladen. Der Zeitplan (alle 15 Minuten)
   holt das nach, sobald Platz ist.
3. Laden in `.laden/`, fortsetzbar über Bereichsanfragen; alle 256 MB wird der freie Platz gegen die Reserve geprüft.
4. Prüfsumme rechnen; stimmt sie nicht, wird die Datei gelöscht.
5. Datei öffnen und zählen.
6. Ablegen: ein neues Buch direkt in die Bibliothek (und in die Liste), eine neue Fassung nach `.neu/`.

## Oberfläche

Seite Bibliothek mit den Reitern Meine Bücher, Katalog sowie Fassungen und Laden. Neues seit der letzten Durchsicht
zeigt die Zahl am Menüpunkt und ein Band auf der Startseite; wer den Katalog öffnet, hat es gesehen. Die Regeln stehen
unter Einstellungen, Bücherlader.
