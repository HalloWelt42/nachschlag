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

Sprungseiten: eine kleine HTML-Seite mit `meta refresh` auf `Seite#Abschnitt` ist eine Weiterleitung (mwoffliner) und
wird aufgelöst. Ein Sprung auf einen Anker mit Schrägstrich (`index.html#kurs/block/aufgabe`, fcc2zim) ist dagegen eine
Route einer Skript-Anwendung: die Seite bleibt sie selbst, ihr Baustein liest den Inhalt aus den Dateien des Buchs
(`bibliothek.ordner.sprungziel`, eine Regel für Lesen und Index).

Übungen (fcc2zim) leben vom Selbertesten: man schreibt den Code selbst, und jeder Prüfpunkt läuft als Test gegen ihn.
Dafür nutzt die Oberfläche den Testläufer, den das Buch mitbringt (`test-runner/javascript-test-evaluator.js`, ein Web
Worker der Quelle), über den Medienweg des Buchs mit dem Lesezugang; das Protokoll ist das der Original-Anwendung
(`frontend/src/lib/pruefen.ts`: einrichten mit Code davor, eigenem Code und Code danach, dann je Prüfpunkt sein Test,
höchstens 5 Sekunden). Der eigene Code und gelöste Aufgaben bleiben im Browser (`lib/uebungsstand.ts`).

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
