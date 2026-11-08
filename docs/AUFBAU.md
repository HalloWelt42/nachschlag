# Aufbau von Nachschlag

Nachschlag liest jedes Buch im ZIM-Format aus einem Ordner und macht es durchsuchbar und angenehm lesbar. Der Kern läuft
allein (nur der Ordner mit den Büchern); weitere Dienste sind Anbindungen, die man zuschaltet. Die freigegebenen
Entwürfe unter `mockups/` sind der Leitfaden für die Oberfläche.

## Schichten

| Schicht | Ort | Aufgabe |
|---|---|---|
| Modelle | `backend/app/modell/` | Daten an den Grenzen (Pydantic): Buch, Artikel, Abschnitt, Treffer, Suchergebnis |
| Bibliothek | `backend/app/bibliothek/` | Ordner lesen, Bücher öffnen (libzim), Fähigkeiten aus den Angaben der Datei, Einträge, Weiterleitungen, Medien |
| Bausteine | `backend/app/bausteine/` | je Grundstruktur eines Buchs ein Baustein mit eigenen Methoden: erkennen, Inhalt lösen, säubern, gliedern |
| Suche | `backend/app/suche/` | Index des Buchs (Volltext und Titel), Bedeutungssuche als Anbindung, Mischen, Rückfall |
| Bücherlader | `backend/app/buecherlader/` | Verzeichnis der Bücher durchsehen, Neues melden, Abos laden, Fassungen umschalten; schreibt als Einziger in den Ordner der Bücher (docs/BUECHERLADER.md) |
| Schnittstelle | `backend/app/api/` | REST unter `/api/v1`; die Oberfläche nutzt nur diese Wege |
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
| Kellerwolke | Konten, Ablage | ein Nutzer, eigene Datenbank (Betriebsart ohne Anmeldung, Bau 8) |
| Verzeichnis der Bücher | Bücherlader: Neues melden, Abos laden | Bibliothek ohne Katalog und Laden |
| Leitstelle | Übersetzen (Suche und Artikel, als Auftrag), Korrektur, Spracheingabe (Hördienst), Vorlesen (Sprechdienst) | ausgeblendet |

Hausinternes (Adressen, Schlüssel, Ausrollen) gehört nicht in dieses Repo.
