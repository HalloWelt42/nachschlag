# Aufbau von Nachschlag

Nachschlag liest jedes Buch im ZIM-Format aus einem Ordner und macht es durchsuchbar und angenehm lesbar. Der Kern läuft
allein (nur der Ordner mit den Büchern, ohne Anmeldung); weitere Dienste sind Anbindungen, die man zuschaltet. Die freigegebenen
Entwürfe unter `mockups/` sind der Leitfaden für die Oberfläche.

## Schichten

| Schicht | Ort | Aufgabe |
|---|---|---|
| Modelle | `backend/app/modell/` | Daten an den Grenzen (Pydantic): Buch, Artikel, Abschnitt, Treffer, Suchergebnis |
| Bibliothek | `backend/app/bibliothek/` | Ordner lesen, Bücher öffnen (libzim), Fähigkeiten aus den Angaben der Datei, Einträge, Weiterleitungen, Medien |
| Bausteine | `backend/app/bausteine/` | je Grundstruktur eines Buchs ein Baustein mit eigenen Methoden: erkennen, Inhalt lösen, säubern, gliedern |
| Suche | `backend/app/suche/` | Index des Buchs (Volltext und Titel), Bedeutungssuche als Anbindung, Mischen, Rückfall |
| Als Buch | `backend/app/alsbuch/` | ein Thema als Buch (EPUB und PDF) nach einer Vorlage, umgeformt über die Leitstelle, geprüft gegen das Original (docs/ALS_BUCH.md) |
| Bücherlader | `backend/app/buecherlader/` | Verzeichnis der Bücher durchsehen, Neues melden, Abos laden, Fassungen umschalten; schreibt als Einziger in den Ordner der Bücher (docs/BUECHERLADER.md) |
| Meins und Themen | `backend/app/meins/`, `backend/app/themen/` | Merkzettel, Notizen, Verlauf und Themen je Konto (ohne Anmeldung: der feste Nutzer) |
| Ablage | `backend/app/markdownablage.py` und die Dienste | Dateien über die Ablage des Appkerns (`geruest.ablage`): Kellerwolke, wenn eingetragen, sonst `ablage/` im Datenordner |
| Schnittstelle | `backend/app/api.py` und je Bereich `api.py` | REST unter `/api/v1`; die Oberfläche nutzt nur diese Wege |
| Oberfläche | `frontend/src/` | Svelte in der Schale des Appkerns |

## Bausteine

Ein Baustein erfüllt die Schnittstelle in `bausteine/basis.py`. Er wird an den Angaben der Datei erkannt (Erzeuger,
Schlagworte), nie am Dateinamen. Suche, Merkzettel, Notizen und Themen kennen nur die Schnittstelle.

| Baustein | Erzeuger | Stand |
|---|---|---|
| Enzyklopädie | mwoffliner | Bau 1 |
| Originalansicht | alle übrigen | Bau 1, Rückfall für jedes Buch |
| Dokumentation | devdocs2zim | Bau 6 |
| Frage und Antwort | sotoki | Bau 6 |
| Anleitung, Gerät, Anleitungen finden | ohne Erzeuger, Kategorie iFixit | WIKI-64 |
| Übung, Übungen (Kurse) | fcc2zim (freeCodeCamp) | WIKI-66 |
| Kategorie (Kategorieseite), Kategorien am Artikel | mwoffliner ab 2.x, wenn das Buch Kategorien hat (Klexikon) | WIKI-75 |
| Dateiformat (Formatseite mit Steckbrief, Startseite als Übersicht der Kategorien) | dateiformate (eigenes Buch, gebaut im privaten Repo dateiformate) | WIKI-87 |

Sprungseiten: eine kleine HTML-Seite mit `meta refresh` auf `Seite#Abschnitt` ist eine Weiterleitung (mwoffliner) und
wird aufgelöst. Ein Sprung auf einen Anker mit Schrägstrich (`index.html#kurs/block/aufgabe`, fcc2zim) ist dagegen eine
Route einer Skript-Anwendung: die Seite bleibt sie selbst, ihr Baustein liest den Inhalt aus den Dateien des Buchs
(`bibliothek.ordner.sprungziel`, eine Regel für Lesen und Index).

Übungen (fcc2zim) leben vom Selbertesten: man schreibt den Code selbst, und jeder Prüfpunkt läuft als Test gegen ihn.
Dafür nutzt die Oberfläche den Testläufer, den das Buch mitbringt (`test-runner/javascript-test-evaluator.js`, ein Web
Worker der Quelle), über den Medienweg des Buchs mit dem Lesezugang; das Protokoll ist das der Original-Anwendung
(`frontend/src/lib/pruefen.ts`: einrichten mit Code davor, eigenem Code und Code danach, dann je Prüfpunkt sein Test,
höchstens 5 Sekunden). Der eigene Code und gelöste Aufgaben bleiben im Browser (`lib/uebungsstand.ts`).

## Originalansicht (WIKI-85)

Manche Bücher sind ganze Webseiten mit eigener Bedienung (etwa The Last Codex: Atlas, Zeitleiste, Graph, Modelle, Suche).
Ihre Seiten laufen unverändert mit ihren Skripten über den Port der App, aber nie mit ihrer Herkunft
(`backend/app/originalansicht/`):

- **ohne eigene Herkunft:** Sandbox ohne `allow-same-origin`, im Rahmen der App und als Inhaltsregel der Seite selbst
  (auch allein geöffnet). Speicher und Anmeldung der App erreicht ein Buch so nicht, seine Anfragen tragen keine Cookies
  der App. Speicher hat die Seite damit keinen (das Codex-Buch fängt das ab und merkt sich nur seine Designwahl nicht).
  Zuerst lief die Ansicht auf einem eigenen Port; den erreichten manche Geräte nicht (ein iPhone im Heimnetz).
- **Schein statt Cookie:** `/api/v1/original/<schein>/<buch>/<pfad>`; der Schein ist signiert (Geheimnis im Datenordner,
  `originalansicht.geheim`), gilt für ein Buch und sieben Tage und ist einen Tag lang gleich (der Zwischenspeicher des
  Browsers hält). Relative Verweise der Seite behalten ihn. Ohne eigene Herkunft holen Skripte Module und Daten nur mit
  Freigabe: die Originalseiten geben sie (`Access-Control-Allow-Origin: *`), der Schein ist der Zugang.
- **Inhaltsregeln:** laden und verbinden nur mit den Wegen der Originalseiten (nicht mit der Schnittstelle der App,
  nichts nach außen); einbetten nur die App.
- **Brücke** (`bruecke.js`, als erstes Skript jeder Seite, ändert nichts am Aussehen): meldet der App den Ort (Buch, Pfad,
  Abfrage, Anker), reicht Verweise im Buch an die App weiter (sie öffnet sie im Lesen, mit eigenem Lesedesign, wenn es
  eines gibt), öffnet Verweise nach außen in einem neuen Tab und nimmt die Lesegröße an. Die App setzt den Rahmen an
  ihren Ort ohne neuen Eintrag im Verlauf; geht die Seite selbst weiter, folgt die App (`frontend/src/lib/originalrahmen.ts`).

Der Rahmen füllt die Fläche und rollt selbst, auch am Telefon. Bücher, die nur im Original laufen, haben einen schmalen
Kopf: der Pfad in einer Zeile, Titel und Werkzeuge hinter einem Knopf.

## Schnittstelle und MCP

Alle Wege liegen unter `/api/v1`; die Oberfläche nutzt nur diese. Der Bereich Schnittstelle (Baustein des Appkerns)
zeigt sie angemeldeten Menschen aus dem eigenen OpenAPI-Schema (`/api/v1/schnittstelle`), mit Ausprobieren für GET.
Für KI gibt es MCP über HTTP: `POST /api/v1/mcp` (JSON-RPC, zustandslos, Anmeldung wie jeder Weg) mit den Werkzeugen
`nachschlag_buecher`, `nachschlag_suchen` und `nachschlag_lesen` (`backend/app/mcp/`, je Werkzeug Eingabemodell und
eine dünne Schicht über den Diensten).

## Suche

Der Index des Buchs antwortet immer. Ist die Bedeutungssuche angebunden, läuft sie gleichzeitig mit einer Wartezeit;
die Ergebnisse werden nach Rang gemischt (RRF). Antwortet sie nicht rechtzeitig, steht `nur_index` in der Antwort, und
die Oberfläche sagt es.

## Anbindungen

| Anbindung | wofür | ohne sie |
|---|---|---|
| Fundus | Bedeutungssuche | nur Index |
| Kellerwolke | Konten (Anmeldung), Ablage der Dateien | ohne Anmeldung ein fester Nutzer für alle Geräte, Ablage im Datenordner (WIKI-11) |
| Verzeichnis der Bücher | Bücherlader: Neues melden, Abos laden | Bibliothek ohne Katalog und Laden |
| Leitstelle | Übersetzen (Suche und Artikel, als Auftrag), Korrektur, Spracheingabe (Hördienst), Vorlesen (Sprechdienst), Bücher umformen (als Auftrag) | ausgeblendet; Bücher nur mit Vorlagen ohne KI |
| Bildholer | große Bilder der Wikis (docs/BILDHOLER.md) | Bilder aus den Büchern |
| Index-Dienst | eigene Indizes und Kategorien (docs/SUCHE.md) | Index der Datei |
| Codeschmiede | Beispiele ausprobieren (docs/AUSPROBIEREN.md) | ohne Ausprobieren |
| Vertonung | eigene Stimmen fürs Vorlesen | Stimmen des Sprechdienstes |

Jede Anbindung ist wahlweise: nicht eingerichtet zeigt die Oberfläche sie weder als fehlend noch als Fehler. Ob man sich
anmeldet, ist eine eigene Wahl (Einstellungen, Zugang): ab Werk ohne Anmeldung, mit Kellerwolke wahlweise je Konto.

Hausinternes (Adressen, Konten, Ausrollen ins eigene Netz) liegt im privaten Teil `privat/` (eigenes Repo, von Git
ausgeschlossen), nicht in diesem Repo.
