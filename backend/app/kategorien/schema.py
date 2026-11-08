"""Kategorien eines Buchs (WIKI-75): eine SQLite-Datei je Buch und Fassung, gebaut auf dem Mac aus den Datenabzügen von
Wikimedia (die ZIM-Dateien der Wikipedia bringen keine Kategorien mit). Sie enthält nur, was das Buch betrifft:

- `seite`: jede Seite des Buchs, die in einer Kategorie steht, mit Pfad und Titel. Die Nummer folgt der Ordnung der Titel
  (`ordnung`), so lesen sich die Seiten einer Kategorie in der Reihenfolge des Alphabets und seitenweise ab einer Nummer.
- `kategorie`: jede sichtbare Kategorie, in der eine Seite des Buchs steht, und jede darüber (bis zur obersten); die
  Nummer folgt ebenso der Ordnung. `seiten` zählt die Seiten des Buchs direkt darin. Versteckte Kategorien (Wartung)
  fehlen ganz.
- `seite_kategorie` und `unterkategorie`: wer worin steht.

Angaben: `wiki` (etwa dewiki), `stand` (Tag des Datenabzugs), `namensraum` (wie die Kategorien im Wiki heißen, etwa
"Kategorie"), `wurzel` (Titel der obersten Kategorie, wenn das Wiki eine kennt), `fertig` und `fassung`."""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

FASSUNG = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS angaben (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS seite (nr INTEGER PRIMARY KEY, pfad TEXT NOT NULL, titel TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kategorie (nr INTEGER PRIMARY KEY, titel TEXT NOT NULL UNIQUE, seiten INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS seite_kategorie (kategorie INTEGER NOT NULL, seite INTEGER NOT NULL,
                                            PRIMARY KEY (kategorie, seite)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS unterkategorie (ober INTEGER NOT NULL, unter INTEGER NOT NULL,
                                           PRIMARY KEY (ober, unter)) WITHOUT ROWID;
"""
#: erst nach dem Füllen angelegt (schneller als beim Einfügen mitzuführen)
INDIZES = """
CREATE UNIQUE INDEX IF NOT EXISTS seite_pfad ON seite (pfad);
CREATE INDEX IF NOT EXISTS seite_kategorie_seite ON seite_kategorie (seite, kategorie);
CREATE INDEX IF NOT EXISTS unterkategorie_unter ON unterkategorie (unter, ober);
"""

_FALTEN = str.maketrans({"ß": "ss", "_": " "})


def ordnung(titel: str) -> str:
    """Schlüssel für die Reihenfolge der Titel wie in einem Register: ohne Groß und Klein, Umlaute wie ihr Grundlaut
    (Äpfel bei A), Unterstrich wie Leerzeichen."""
    zerlegt = unicodedata.normalize("NFKD", titel.translate(_FALTEN).casefold())
    return "".join(z for z in zerlegt if not unicodedata.combining(z))


def anzeigen(titel: str) -> str:
    """Titel, wie das Wiki ihn zeigt (Leerzeichen statt Unterstrich)."""
    return titel.replace("_", " ")


def dateiname(kennung: str) -> str:
    return f"{kennung}.sqlite"


def oeffnen(pfad: Path) -> sqlite3.Connection:
    """Zum Bauen: eine leere Datei mit allen Tabellen."""
    pfad.unlink(missing_ok=True)
    v = sqlite3.connect(pfad)
    v.executescript("PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF;" + SCHEMA)
    return v


def lesen(pfad: Path) -> sqlite3.Connection:
    """Zum Abfragen: nur lesend."""
    v = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, check_same_thread=False)
    v.row_factory = sqlite3.Row
    return v


def angabe(v: sqlite3.Connection, schluessel: str, vorgabe: str = "") -> str:
    z = v.execute("SELECT wert FROM angaben WHERE schluessel=?", (schluessel,)).fetchone()
    return z[0] if z else vorgabe


def angabe_setzen(v: sqlite3.Connection, schluessel: str, wert: str) -> None:
    v.execute("INSERT INTO angaben (schluessel, wert) VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
              (schluessel, wert))


def gueltig(pfad: Path) -> bool:
    """Fertig gebaut und in der Fassung dieses Schemas."""
    try:
        v = lesen(pfad)
        try:
            return angabe(v, "fertig") == "1" and angabe(v, "fassung") == str(FASSUNG)
        finally:
            v.close()
    except sqlite3.DatabaseError:
        return False
