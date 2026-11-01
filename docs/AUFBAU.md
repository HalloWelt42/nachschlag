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

## Suche

Der Index des Buchs antwortet immer. Ist die Bedeutungssuche angebunden, läuft sie gleichzeitig mit einer Wartezeit;
die Ergebnisse werden nach Rang gemischt (RRF). Antwortet sie nicht rechtzeitig, steht `nur_index` in der Antwort, und
die Oberfläche sagt es.

## Anbindungen

| Anbindung | wofür | ohne sie |
|---|---|---|
| Fundus | Bedeutungssuche | nur Index |
| Kellerwolke | Konten, Ablage | ein Nutzer, eigene Datenbank (Betriebsart ohne Anmeldung, Bau 8) |
| Leitstelle | Übersetzen, Vorschläge | ausgeblendet |
| Vorlesedienst | Vorlesen | ausgeblendet |

Hausinternes (Adressen, Schlüssel, Ausrollen) gehört nicht in dieses Repo.
