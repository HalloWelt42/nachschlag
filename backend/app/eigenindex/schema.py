"""Eigener Index eines Buchs (WIKI-17, docs/SUCHE.md): eine SQLite-Datei je Buch und Fassung mit den Feldern, die der
Index der ZIM-Datei nicht kennt (Name aus dem Code, Rubrik, Einleitung), und einem Volltext darüber (FTS5).

Unterstrich, Doppelpunkt, Dollar und Backslash gehören zum Wort, damit `array_map`, `Foo::bar` und `$var` ganze Begriffe
bleiben. Der Stand des Aufbaus steht in der Datei selbst: so setzt ein abgebrochener Aufbau dort fort.

Metadaten je Inhaltsart (Punkt 11): Frage und Antwort hat je Frage Stimmen, Antworten, Haken und Datum (fragen), ihre
Schlagwörter und die Beiträge mit Autor (beitraege). Die Register (Punkt 10) werden am Ende des Aufbaus daraus
verdichtet, damit Listen über Millionen Fragen sofort antworten.

Abdruck (WIKI-58): je Seite eine kurze Prüfsumme ihres Rohinhalts in der ZIM-Datei; Seiten, die gelesen, aber nicht in den
Index genommen wurden (etwa Konten und Listen einer Frage-Antwort-Seite), stehen mit ihrem Abdruck in `ohne_seite`. So
übernimmt der Index einer neuen Fassung alles Unveränderte aus dem Index der vorigen, statt es neu aufzubereiten.

Anleitungen (iFixit, WIKI-64): je Anleitung Art, Sprache, Schwierigkeit, Zeit, Schritte und Bild (`anleitungen`), ihre
Werkzeuge (`werkzeuge`, verdichtet im Register je Sprache); je Geräteseite Bild und Kurztext (`geraete`), die Pfade ihrer
Unterkategorien (`geraet_kind`, daraus der Baum) und Anleitungen mit dem Bauteil, wie die Geräteseite es nennt
(`geraet_anleitung`). Alle Metadaten hängen an der Nummer ihrer Seite (`nr`), Titel und Pfad stehen in `seiten`.
Bilder stehen als Pfad im Buch, damit sie über Fassungen hinweg gelten. Verdichtet: `register_einordnung` nennt je Anleitung
jede Geräteseite darüber (Gerät, Kategorie, bis zur Startseite), so filtert ein Knoten des Baums seinen ganzen Ast."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

#: Fassung des Schemas; eine andere Fassung baut den Index neu (2: Frage und Antwort mit Registern, WIKI-39)
FASSUNG = 2

SCHEMA = f"""
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS angaben (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS seiten (
  nr INTEGER PRIMARY KEY, pfad TEXT NOT NULL UNIQUE, titel TEXT NOT NULL, name TEXT NOT NULL DEFAULT '',
  rubrik TEXT NOT NULL DEFAULT '', einleitung TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '',
  abdruck TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS ohne_seite (pfad TEXT PRIMARY KEY, abdruck TEXT NOT NULL) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS seiten_name ON seiten (name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS seiten_titel ON seiten (titel COLLATE NOCASE);
CREATE VIRTUAL TABLE IF NOT EXISTS volltext USING fts5(
  titel, name, rubrik, einleitung, text, content='seiten', content_rowid='nr',
  tokenize = "unicode61 remove_diacritics 2 tokenchars '_:$\\\\'", prefix = '2 3');
CREATE TABLE IF NOT EXISTS fragen (
  nr INTEGER PRIMARY KEY, stimmen INTEGER NOT NULL, antworten INTEGER NOT NULL, akzeptiert INTEGER NOT NULL,
  gefragt TEXT NOT NULL DEFAULT '', gewicht REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS schlagwoerter (wort TEXT NOT NULL, nr INTEGER NOT NULL, PRIMARY KEY (wort, nr)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS schlagwoerter_nr ON schlagwoerter (nr);
CREATE TABLE IF NOT EXISTS beitraege (
  nr INTEGER NOT NULL, schluessel TEXT NOT NULL, autor TEXT NOT NULL, art TEXT NOT NULL, stimmen INTEGER NOT NULL,
  datum TEXT NOT NULL, akzeptiert INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS beitraege_schluessel ON beitraege (schluessel);
CREATE INDEX IF NOT EXISTS beitraege_nr ON beitraege (nr);
CREATE TABLE IF NOT EXISTS register_schlagwoerter (wort TEXT PRIMARY KEY, fragen INTEGER NOT NULL, stimmen INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS register_schlagwoerter_fragen ON register_schlagwoerter (fragen DESC);
CREATE TABLE IF NOT EXISTS register_autoren (
  schluessel TEXT PRIMARY KEY, autor TEXT NOT NULL, beitraege INTEGER NOT NULL, fragen INTEGER NOT NULL,
  antworten INTEGER NOT NULL, akzeptiert INTEGER NOT NULL, stimmen INTEGER NOT NULL, von TEXT NOT NULL, bis TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS register_autoren_beitraege ON register_autoren (beitraege DESC);
CREATE INDEX IF NOT EXISTS register_autoren_name ON register_autoren (autor COLLATE NOCASE);
CREATE TABLE IF NOT EXISTS anleitungen (
  nr INTEGER PRIMARY KEY, art TEXT NOT NULL, sprache TEXT NOT NULL, schwierigkeit INTEGER NOT NULL, schwierigkeit_text TEXT NOT NULL,
  zeit TEXT NOT NULL, zeit_von INTEGER, zeit_bis INTEGER, schritte INTEGER NOT NULL, bild TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS anleitungen_sprache ON anleitungen (sprache, art);
CREATE TABLE IF NOT EXISTS werkzeuge (wort TEXT NOT NULL, nr INTEGER NOT NULL, PRIMARY KEY (wort, nr)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS werkzeuge_nr ON werkzeuge (nr);
CREATE TABLE IF NOT EXISTS geraete (nr INTEGER PRIMARY KEY, bild TEXT NOT NULL, kurz TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS geraet_kind (nr INTEGER NOT NULL, kind TEXT NOT NULL, PRIMARY KEY (nr, kind)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS geraet_kind_kind ON geraet_kind (kind);
CREATE TABLE IF NOT EXISTS geraet_anleitung (nr INTEGER NOT NULL, anleitung TEXT NOT NULL, bauteil TEXT NOT NULL, empfohlen INTEGER NOT NULL,
  PRIMARY KEY (nr, anleitung)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS geraet_anleitung_anleitung ON geraet_anleitung (anleitung);
CREATE TABLE IF NOT EXISTS register_werkzeuge (wort TEXT NOT NULL, sprache TEXT NOT NULL, anleitungen INTEGER NOT NULL, PRIMARY KEY (wort, sprache));
CREATE TABLE IF NOT EXISTS register_einordnung (oben TEXT NOT NULL, nr INTEGER NOT NULL, PRIMARY KEY (oben, nr)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS register_einordnung_nr ON register_einordnung (nr);
INSERT OR IGNORE INTO angaben (schluessel, wert) VALUES ('fassung', '{FASSUNG}');
"""


def dateiname(kennung: str) -> str:
    """Name der Indexdatei eines Buchs; die Kennung trägt die Fassung des Buchs, so hat jede Fassung ihren Index."""
    return f"{kennung}.sqlite"


def autor_schluessel(autor_nr: str, autor: str) -> str:
    """Wer ein Autor im Buch ist: die Kontonummer, sonst der Name (gleiche Namen ohne Konto fallen zusammen)."""
    return autor_nr or f"name:{autor}"


def oeffnen(pfad: Path) -> sqlite3.Connection:
    """Zum Bauen: legt fehlende Tabellen an (auch die Spalte des Abdrucks in einem Index, der vor WIKI-58 begann)."""
    v = sqlite3.connect(pfad)
    v.row_factory = sqlite3.Row
    if v.execute("SELECT 1 FROM sqlite_master WHERE name='seiten'").fetchone() and not mit_abdruck(v):
        v.execute("ALTER TABLE seiten ADD COLUMN abdruck TEXT NOT NULL DEFAULT ''")
    v.executescript(SCHEMA)
    return v


def mit_abdruck(v: sqlite3.Connection) -> bool:
    """Trägt der Index Abdrücke (gebaut seit WIKI-58)? Nur dann taugt er als Vorlage für die nächste Fassung."""
    return any(z[1] == "abdruck" for z in v.execute("PRAGMA table_info(seiten)"))


def abdruck(inhalt: bytes) -> str:
    """Kurze Prüfsumme des Rohinhalts einer Seite (128 Bit reichen, um Gleiches sicher zu erkennen)."""
    return hashlib.blake2b(inhalt, digest_size=16).hexdigest()


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
