"""Eigener Index eines Buchs (WIKI-17, docs/SUCHE.md): eine SQLite-Datei je Buch und Fassung mit den Feldern, die der
Index der ZIM-Datei nicht kennt (Name aus dem Code, Rubrik, Einleitung), und einem Volltext darüber (FTS5).

Unterstrich, Doppelpunkt, Dollar und Backslash gehören zum Wort, damit `array_map`, `Foo::bar` und `$var` ganze Begriffe
bleiben. Der Stand des Aufbaus steht in der Datei selbst: so setzt ein abgebrochener Aufbau dort fort."""

from __future__ import annotations

import sqlite3
from pathlib import Path

#: Fassung des Schemas; eine andere Fassung baut den Index neu
FASSUNG = 1

SCHEMA = f"""
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS angaben (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS seiten (
  nr INTEGER PRIMARY KEY, pfad TEXT NOT NULL UNIQUE, titel TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
  rubrik TEXT NOT NULL DEFAULT '', einleitung TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS seiten_name ON seiten (name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS seiten_titel ON seiten (titel COLLATE NOCASE);
CREATE VIRTUAL TABLE IF NOT EXISTS volltext USING fts5(
  titel, name, rubrik, einleitung, text, content='seiten', content_rowid='nr',
  tokenize = "unicode61 remove_diacritics 2 tokenchars '_:$\\\\'", prefix = '2 3');
INSERT OR IGNORE INTO angaben (schluessel, wert) VALUES ('fassung', '{FASSUNG}');
"""


def dateiname(kennung: str) -> str:
    """Name der Indexdatei eines Buchs; die Kennung trägt die Fassung des Buchs, so hat jede Fassung ihren Index."""
    return f"{kennung}.sqlite"


def oeffnen(pfad: Path) -> sqlite3.Connection:
    """Zum Bauen: legt fehlende Tabellen an."""
    v = sqlite3.connect(pfad)
    v.row_factory = sqlite3.Row
    v.executescript(SCHEMA)
    return v


def lesen(pfad: Path) -> sqlite3.Connection:
    """Zum Suchen: nur lesend, ändert nichts an der Datei."""
    v = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, check_same_thread=False)
    v.row_factory = sqlite3.Row
    return v


def gueltig(pfad: Path) -> bool:
    """Fertig gebaut und in der Fassung dieses Schemas; alles andere (halb gebaut, alt, kaputt) gilt nicht."""
    try:
        v = lesen(pfad)
        try:
            return angabe(v, "fertig") == "1" and angabe(v, "fassung") == str(FASSUNG)
        finally:
            v.close()
    except sqlite3.DatabaseError:
        return False


def angabe(v: sqlite3.Connection, schluessel: str, vorgabe: str = "") -> str:
    z = v.execute("SELECT wert FROM angaben WHERE schluessel=?", (schluessel,)).fetchone()
    return z["wert"] if z else vorgabe


def angabe_setzen(v: sqlite3.Connection, schluessel: str, wert: str) -> None:
    v.execute("INSERT INTO angaben (schluessel, wert) VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
              (schluessel, wert))
