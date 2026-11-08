"""Suche im eigenen Index eines Buchs, in drei Stufen: der genaue Name oder Titel (array_map, Rotfuchs), dann Namen und
Titel, die mit der Frage beginnen, dann der Volltext nach bm25 (Name und Titel wiegen am meisten). Jede Stufe nimmt nur,
was die vorige nicht schon hat. Die Ausschnitte kommen aus dem Index selbst; das Buch wird dafür nicht gelesen."""

from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..bausteine.html import gerade
from ..modell.suche import Fragezahlen
from ..suche.index import markieren
from . import schema

#: Gewichte der Spalten im Volltext: Titel, Name, Rubrik, Einleitung, Text
GEWICHTE = (10.0, 12.0, 2.0, 3.0, 1.0)
#: So stark heben Stimmen eine Frage (Gewicht aus dem Bau, logarithmisch) gegen die Passung des Volltexts
STIMMEN_ZAEHLEN = 1.5
#: Wörter wie im Tokenizer des Index (Unterstrich, Doppelpunkt, Dollar und Backslash gehören zum Wort)
WORT = re.compile(r"[\w:$\\]+", re.UNICODE)
#: Weiter zählt die Gesamtzahl nicht (häufige Wörter in großen Büchern); darüber gilt sie als "mindestens"
ZAEHLEN_BIS = 10_000
AUSSCHNITT = 240
_AUF, _ZU = chr(2), chr(3)   # Marken des Ausschnitts (char(2), char(3) in der Abfrage)

Stufe = Literal["name", "anfang", "volltext"]


@dataclass
class Fund:
    pfad: str
    titel: str
    rubrik: str
    ausschnitt: str      # reiner Text, maskiert, Fundwörter in <em>
    stufe: Stufe
    frage: Fragezahlen | None = None


def ausdruck(frage: str) -> str:
    """Die Frage als Ausdruck des Volltexts: jedes Wort muss vorkommen, ab zwei Zeichen auch als Wortanfang."""
    woerter = [w.strip(":") for w in WORT.findall(frage)]
    return " ".join('"' + w.replace('"', '""') + '"' + ("*" if len(w) >= 2 else "") for w in woerter if w)


def _stelle(z: sqlite3.Row, frage: str) -> str:
    text = gerade(z["einleitung"] or z["text"] or "")
    stueck = text[:AUSSCHNITT]
    return markieren(html.escape(stueck), frage) + (" ..." if len(text) > AUSSCHNITT else "")


def _snippet(roh: str) -> str:
    return html.escape(gerade(roh)).replace(_AUF, "<em>").replace(_ZU, "</em>")


def suchen(datei: Path, frage: str, anzahl: int = 20) -> tuple[list[Fund], int]:
    """Funde und Zahl der Treffer im Volltext (höchstens ZAEHLEN_BIS)."""
    frage = frage.strip()
    if not frage:
        return [], 0
    v = schema.lesen(datei)
    try:
        funde: list[Fund] = []
        gesehen: set[int] = set()

        def nehmen(zeilen, stufe: Stufe, stelle) -> None:
            for z in zeilen:
                if z["nr"] in gesehen or len(funde) >= anzahl:
                    continue
                gesehen.add(z["nr"])
                funde.append(Fund(pfad=z["pfad"], titel=z["titel"], rubrik=z["rubrik"], ausschnitt=stelle(z), stufe=stufe))

        spalten = "nr, pfad, titel, rubrik, einleitung, text"
        nehmen(v.execute(f"SELECT {spalten} FROM seiten WHERE name = ? COLLATE NOCASE OR titel = ? COLLATE NOCASE "
                         "ORDER BY length(titel) LIMIT ?", (frage, frage, anzahl)), "name", lambda z: _stelle(z, frage))
        # Wortanfang über die Indizes auf Name und Titel (ohne Groß und Klein); U+10FFFF liegt hinter jedem Zeichen
        bis = frage + chr(0x10FFFF)
        nehmen(v.execute(f"SELECT {spalten} FROM seiten WHERE (name >= ? COLLATE NOCASE AND name < ? COLLATE NOCASE) "
                         "OR (titel >= ? COLLATE NOCASE AND titel < ? COLLATE NOCASE) ORDER BY length(titel), titel LIMIT ?",
                         (frage, bis, frage, bis, anzahl)), "anfang", lambda z: _stelle(z, frage))

        gesamt = 0
        suchausdruck = ausdruck(frage)
        if suchausdruck and len(funde) < anzahl:
            try:
                gewichte = ", ".join(str(g) for g in GEWICHTE)
                zeilen = v.execute(
                    f"SELECT s.nr, s.pfad, s.titel, s.rubrik, snippet(volltext, -1, char(2), char(3), ' ... ', 24) AS stelle "
                    f"FROM volltext JOIN seiten s ON s.nr = volltext.rowid LEFT JOIN fragen f ON f.nr = s.nr "
                    f"WHERE volltext MATCH ? ORDER BY bm25(volltext, {gewichte}) - COALESCE(f.gewicht, 0) * {STIMMEN_ZAEHLEN} "
                    f"LIMIT ?", (suchausdruck, anzahl + len(gesehen))).fetchall()
                nehmen(zeilen, "volltext", lambda z: _snippet(z["stelle"]))
                gesamt = v.execute("SELECT COUNT(*) FROM (SELECT 1 FROM volltext WHERE volltext MATCH ? LIMIT ?)",
                                   (suchausdruck, ZAEHLEN_BIS)).fetchone()[0]
            except sqlite3.OperationalError:
                pass                                       # Ausdruck, den der Volltext nicht versteht: nur die Namen
        for f in funde:
            f.frage = _fragezahlen(v, f.pfad)
        return funde, max(gesamt, len(funde))
    finally:
        v.close()


def _fragezahlen(v: sqlite3.Connection, pfad: str) -> Fragezahlen | None:
    z = v.execute("SELECT f.nr, f.stimmen, f.antworten, f.akzeptiert FROM fragen f JOIN seiten s ON s.nr = f.nr WHERE s.pfad = ?",
                  (pfad,)).fetchone()
    if z is None:
        return None
    woerter = [w["wort"] for w in v.execute("SELECT wort FROM schlagwoerter WHERE nr = ?", (z["nr"],))]
    return Fragezahlen(stimmen=z["stimmen"], antworten=z["antworten"], akzeptiert=bool(z["akzeptiert"]), schlagwoerter=woerter)


@dataclass
class Rueckverweis:
    pfad: str
    titel: str


def rueckverweise(datei: Path, pfad: str, anzahl: int = 50) -> tuple[list[Rueckverweis], int] | None:
    """Seiten, die auf `pfad` verweisen (nach Titel), und ihre Zahl (WIKI-20); None, wenn dieser Index die Verweise
    nicht kennt (gebaut, bevor es sie gab): dann weiß er es nicht, statt "keine" zu sagen."""
    v = schema.lesen(datei)
    try:
        if schema.angabe(v, "verweise", "") != "1":
            return None
        gesamt = v.execute("SELECT COUNT(*) FROM verweise WHERE ziel = ?", (pfad,)).fetchone()[0]
        zeilen = v.execute("SELECT s.pfad, s.titel FROM verweise w JOIN seiten s ON s.nr = w.nr WHERE w.ziel = ? "
                           "ORDER BY s.titel COLLATE NOCASE LIMIT ?", (pfad, anzahl)).fetchall()
        return [Rueckverweis(z["pfad"], z["titel"]) for z in zeilen], gesamt
    finally:
        v.close()
