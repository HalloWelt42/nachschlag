"""Abfragen über den eigenen Index eines Anleitungsbuchs (WIKI-64). Eine Trefferliste (`_Treffer`) aus Filtern und
Volltext liegt jeder Antwort zugrunde: Liste, Zahlen, Facetten. Bilder stehen im Index als Pfad im Buch; `medien` macht
daraus Adressen."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field

from ..eigenindex import schema
from ..eigenindex.abfrage import GEWICHTE, ausdruck
from ..modell.anleitungen import (Anleitungsfrage, Anleitungsfunde, Anleitungstreffer, Einordnung, Einordnungsschritt,
                                  Facette, Geraetetreffer, Werkzeugeintrag)

#: So viele Bauteile zeigt die Facette; ein Bauteil braucht mindestens so viele Anleitungen
BAUTEILE = 15
BAUTEIL_AB = 2
#: Weiter geht der Weg im Baum nicht (ein Kreis in der Quelle hält ihn nicht auf)
TIEFE = 20


def _liste(werte: list) -> str:
    return ",".join("?" * len(werte))


@dataclass
class _Treffer:
    """Die Anleitungen zu einer Frage als Unterabfrage (`sql` liefert nr und rang) mit ihren Parametern."""
    sql: str
    werte: list = field(default_factory=list)


def _treffer(f: Anleitungsfrage, nur_passend: bool) -> _Treffer:
    """Filter und Volltext; `nur_passend`: mit Ich habe nur Anleitungen, für die meine Werkzeuge reichen."""
    von, bedingungen, werte = "anleitungen a", ["a.art = ?"], [f.art]
    rang = "0"
    if f.text.strip() and (frage := ausdruck(f.text)):
        von += (f" JOIN (SELECT rowid AS nr, bm25(volltext, {', '.join(map(str, GEWICHTE))}) AS rang FROM volltext "
                f"WHERE volltext MATCH ?) t ON t.nr = a.nr")
        werte.insert(0, frage)
        rang = "t.rang"
    if f.sprachen:
        bedingungen.append(f"a.sprache IN ({_liste(f.sprachen)})")
        werte += f.sprachen
    if f.schwierigkeit:
        bedingungen.append(f"a.schwierigkeit IN ({_liste(f.schwierigkeit)})")
        werte += f.schwierigkeit
    if f.zeit_bis:
        bedingungen.append("a.zeit_bis IS NOT NULL AND a.zeit_bis <= ?")
        werte.append(f.zeit_bis)
    if f.geraet:
        bedingungen.append("a.nr IN (SELECT nr FROM register_einordnung WHERE oben = ?)")
        werte.append(f.geraet)
    if f.bauteil:
        bedingungen.append("a.nr IN (SELECT x.nr FROM geraet_anleitung g JOIN seiten x ON x.pfad = g.anleitung WHERE g.bauteil = ?)")
        werte.append(f.bauteil)
    if nur_passend and f.werkzeuge:
        bedingungen.append(f"NOT EXISTS (SELECT 1 FROM werkzeuge w WHERE w.nr = a.nr AND w.wort NOT IN ({_liste(f.werkzeuge)}))")
        werte += f.werkzeuge
    return _Treffer(f"SELECT a.nr AS nr, {rang} AS rang FROM {von} WHERE {' AND '.join(bedingungen)}", werte)


def _zahl(v: sqlite3.Connection, t: _Treffer) -> int:
    return v.execute(f"SELECT COUNT(*) FROM ({t.sql})", t.werte).fetchone()[0]


def _reihenfolge(f: Anleitungsfrage) -> str:
    titel = "s.titel COLLATE NOCASE"
    if f.reihenfolge == "einfach":
        return f"a.schwierigkeit = 0, a.schwierigkeit, {titel}"
    if f.reihenfolge == "schnell":
        return f"a.zeit_bis IS NULL, a.zeit_bis, {titel}"
    if f.reihenfolge == "passend" and f.text.strip():
        return f"t.rang, {titel}"
    return titel


def _anleitungen(v: sqlite3.Connection, f: Anleitungsfrage, t: _Treffer, medien: Callable[[str], str]) -> list[Anleitungstreffer]:
    mein = set(f.werkzeuge)
    zeilen = v.execute(f"SELECT s.nr, s.pfad, s.titel, a.art, a.sprache, a.schwierigkeit, a.schwierigkeit_text, a.zeit, "
                       f"a.schritte, a.bild FROM ({t.sql}) t JOIN anleitungen a ON a.nr = t.nr JOIN seiten s ON s.nr = t.nr "
                       f"ORDER BY {_reihenfolge(f)} LIMIT ? OFFSET ?", [*t.werte, f.anzahl, f.ab]).fetchall()
    aus = []
    for z in zeilen:
        werkzeuge = [w[0] for w in v.execute("SELECT wort FROM werkzeuge WHERE nr = ? ORDER BY wort", (z["nr"],))]
        geraet = v.execute("SELECT s.titel, g.bauteil FROM geraet_anleitung g JOIN seiten s ON s.nr = g.nr WHERE g.anleitung = ? "
                           "ORDER BY g.empfohlen DESC, s.nr LIMIT 1", (z["pfad"],)).fetchone()
        aus.append(Anleitungstreffer(pfad=z["pfad"], titel=z["titel"], art=z["art"], sprache=z["sprache"],
                                     schwierigkeit=z["schwierigkeit"], schwierigkeit_text=z["schwierigkeit_text"], zeit=z["zeit"],
                                     schritte=z["schritte"], bild=medien(z["bild"]) if z["bild"] else "", werkzeuge=werkzeuge,
                                     fehlt=[w for w in werkzeuge if mein and w not in mein],
                                     geraet=geraet["titel"] if geraet else "", bauteil=geraet["bauteil"] if geraet else ""))
    return aus


def _kinder(v: sqlite3.Connection, pfad: str) -> list[tuple[str, str]]:
    """Unterkategorien und Geräte einer Geräteseite (Pfad, Titel), wie die Seite sie aufführt."""
    return [(z[0], z[1]) for z in v.execute(
        "SELECT k.kind, COALESCE(c.titel, k.kind) FROM geraet_kind k JOIN seiten s ON s.nr = k.nr AND s.pfad = ? "
        "LEFT JOIN seiten c ON c.pfad = k.kind", (pfad,))]


def _unter(v: sqlite3.Connection, knoten: str, t: _Treffer) -> list[Facette]:
    kinder = _kinder(v, knoten)
    if not kinder:
        return []
    titel = dict(kinder)
    zahlen = v.execute(f"SELECT e.oben, COUNT(*) FROM register_einordnung e WHERE e.oben IN ({_liste(kinder)}) "
                       f"AND e.nr IN (SELECT nr FROM ({t.sql})) GROUP BY e.oben", [*titel, *t.werte]).fetchall()
    return sorted((Facette(wert=o, titel=titel[o], zahl=n) for o, n in zahlen if n), key=lambda x: (-x.zahl, x.titel.lower()))


def _bauteile(v: sqlite3.Connection, t: _Treffer) -> list[Facette]:
    zeilen = v.execute(f"SELECT g.bauteil, COUNT(DISTINCT x.nr) AS n FROM geraet_anleitung g JOIN seiten x ON x.pfad = g.anleitung "
                       f"WHERE x.nr IN (SELECT nr FROM ({t.sql})) AND g.bauteil != '' GROUP BY g.bauteil HAVING n >= ? "
                       f"ORDER BY n DESC, g.bauteil LIMIT ?", [*t.werte, BAUTEIL_AB, BAUTEILE]).fetchall()
    return [Facette(wert=b, titel=b, zahl=n) for b, n in zeilen]


def weg(v: sqlite3.Connection, pfad: str) -> list[Einordnungsschritt]:
    """Von der Startseite zu dieser Geräteseite, über den jeweils ersten Elternteil."""
    start = schema.angabe(v, "startseite", "")
    schritte: list[Einordnungsschritt] = []
    gesehen: set[str] = set()
    while pfad and pfad not in gesehen and len(schritte) < TIEFE:
        gesehen.add(pfad)
        titel = v.execute("SELECT titel FROM seiten WHERE pfad = ?", (pfad,)).fetchone()
        schritte.insert(0, Einordnungsschritt(pfad=pfad, titel=titel[0] if titel else pfad))
        if pfad == start:
            break
        eltern = v.execute("SELECT s.pfad FROM geraet_kind k JOIN seiten s ON s.nr = k.nr WHERE k.kind = ? ORDER BY s.nr LIMIT 1",
                           (pfad,)).fetchone()
        pfad = eltern[0] if eltern else ""
    return schritte


def _geraete(v: sqlite3.Connection, f: Anleitungsfrage, knoten: str, medien: Callable[[str], str]) -> tuple[list[Geraetetreffer], int]:
    """Geräteseiten im Ast des Knotens, mit Volltext nach Passung, sonst nach Titel; je mit Zahl der Anleitungen."""
    ast = ("WITH RECURSIVE ast(pfad) AS (SELECT ? UNION SELECT k.kind FROM geraet_kind k JOIN seiten s ON s.nr = k.nr "
           "JOIN ast ON ast.pfad = s.pfad) ")
    von, werte, ordnung = "geraete g JOIN seiten s ON s.nr = g.nr", [knoten], "s.titel COLLATE NOCASE"
    if f.text.strip() and (frage := ausdruck(f.text)):
        von += " JOIN volltext ON volltext.rowid = g.nr AND volltext MATCH ?"
        werte.append(frage)
        ordnung = f"bm25(volltext, {', '.join(map(str, GEWICHTE))}), {ordnung}"
    bedingung = "s.pfad IN (SELECT pfad FROM ast) AND s.pfad != ?"
    werte.append(knoten)
    gesamt = v.execute(f"{ast} SELECT COUNT(*) FROM {von} WHERE {bedingung}", werte).fetchone()[0]
    sprachen = f.sprachen or ["de", "en"]
    zeilen = v.execute(f"{ast} SELECT s.pfad, s.titel, g.bild, g.kurz, (SELECT COUNT(*) FROM register_einordnung e "
                       f"JOIN anleitungen a ON a.nr = e.nr WHERE e.oben = s.pfad AND a.sprache IN ({_liste(sprachen)})) AS n "
                       f"FROM {von} WHERE {bedingung} ORDER BY {ordnung} LIMIT ? OFFSET ?",
                       [knoten, *sprachen, *werte[1:], f.anzahl, f.ab]).fetchall()
    return [Geraetetreffer(pfad=z["pfad"], titel=z["titel"], bild=medien(z["bild"]) if z["bild"] else "", kurz=z["kurz"],
                           anleitungen=z["n"]) for z in zeilen], gesamt


def finden(v: sqlite3.Connection, f: Anleitungsfrage, medien: Callable[[str], str]) -> Anleitungsfunde:
    knoten = f.geraet or schema.angabe(v, "startseite", "")
    sprachen = f.sprachen or ["de", "en"]
    funde = Anleitungsfunde(
        einordnung=weg(v, f.geraet) if f.geraet else [],
        bestand_anleitungen=v.execute(f"SELECT COUNT(*) FROM anleitungen WHERE art = 'anleitung' AND sprache IN ({_liste(sprachen)})",
                                      sprachen).fetchone()[0],
        bestand_geraete=v.execute("SELECT COUNT(*) FROM geraete g JOIN seiten s ON s.nr = g.nr WHERE s.pfad != ?",
                                  (schema.angabe(v, "startseite", ""),)).fetchone()[0])
    if f.art == "geraet":
        funde.geraete, funde.gesamt = _geraete(v, f, knoten, medien)
        return funde
    t = _treffer(f, nur_passend=not f.mehr_noetig)
    funde.gesamt = _zahl(v, t)
    if f.werkzeuge:
        alle = _zahl(v, _treffer(f, nur_passend=False))
        funde.brauchen_mehr = alle - (funde.gesamt if not f.mehr_noetig else _zahl(v, _treffer(f, nur_passend=True)))
    funde.anleitungen = _anleitungen(v, f, t, medien)
    funde.unter = _unter(v, knoten, t) if knoten else []
    funde.bauteile = [] if f.bauteil else _bauteile(v, t)
    return funde


def werkzeuge(v: sqlite3.Connection, sprachen: list[str], anfang: str = "", anzahl: int = 300) -> list[Werkzeugeintrag]:
    """Werkzeuge nach Zahl der Anleitungen, die sie brauchen (für die Auswahl Ich habe)."""
    sprachen = sprachen or ["de", "en"]
    zeilen = v.execute(f"SELECT wort, SUM(anleitungen) AS n FROM register_werkzeuge WHERE sprache IN ({_liste(sprachen)}) "
                       f"AND wort LIKE ? GROUP BY wort ORDER BY n DESC, wort LIMIT ?",
                       [*sprachen, anfang.replace("%", "") + "%", anzahl]).fetchall()
    return [Werkzeugeintrag(wort=w, anleitungen=n) for w, n in zeilen]


def einordnung(v: sqlite3.Connection, pfad: str) -> Einordnung:
    """Weg im Gerätebaum zu einer Geräteseite; für eine Anleitung über das Gerät, das sie aufführt (empfohlen zuerst)."""
    geraet = v.execute("SELECT s.pfad, g.bauteil FROM geraet_anleitung g JOIN seiten s ON s.nr = g.nr WHERE g.anleitung = ? "
                       "ORDER BY g.empfohlen DESC, s.nr LIMIT 1", (pfad,)).fetchone()
    if geraet:
        return Einordnung(weg=weg(v, geraet[0]), bauteil=geraet[1])
    return Einordnung(weg=weg(v, pfad)[:-1])                 # die Seite selbst steht schon als Titel da
