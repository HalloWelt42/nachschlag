"""Register (WIKI-39, docs/SUCHE.md Punkt 10): Schlagwörter und Autoren aus den eigenen Indizes der Frage-Antwort-Bücher,
über alle Bücher oder eines. Gezählt wird beim Bau (Tabellen register_* im Index); hier wird nur gelesen, über die
Bücher zusammengeführt und geblättert. Ein Buch ohne geltenden Index steht in `ohne_index` (sein Register entsteht
mit dem Index, Seite Aufträge)."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from ..bausteine.html import datum
from ..bibliothek import Bibliothek, BuchFehlt
from ..eigenindex import schema
from ..eigenindex.ablage import Eigenindizes
from ..modell.register import (AutorBeitrag, AutorEintrag, AutorenSeite, AutorSeite, FragenSeite, RegisterFrage,
                               SchlagwortEintrag, SchlagwortSeite, Sortierung)

ART = "frage_antwort"


def _bereich(anfang: str) -> tuple[str, str]:
    """Bereich für "beginnt mit" über einen Index ohne Groß und Klein; U+10FFFF liegt hinter jedem Zeichen."""
    return anfang, anfang + chr(0x10FFFF)


def _lesen(datei: Path, arbeit):
    v = schema.lesen(datei)
    try:
        return arbeit(v)
    finally:
        v.close()


def _autor(buch: str, z: sqlite3.Row) -> AutorEintrag:
    return AutorEintrag(buch=buch, schluessel=z["schluessel"], autor=z["autor"], beitraege=z["beitraege"], fragen=z["fragen"],
                        antworten=z["antworten"], akzeptiert=z["akzeptiert"], stimmen=z["stimmen"], von=z["von"], bis=z["bis"])


class Register:
    def __init__(self, bibliothek: Bibliothek, eigen: Eigenindizes) -> None:
        self._bib, self._eigen = bibliothek, eigen

    async def _quellen(self, buch: str = "") -> tuple[list[tuple[str, Path]], list[str]]:
        """Frage-Antwort-Bücher (oder das eine) mit geltendem Index und die Kennungen derer, die noch keinen haben."""
        buecher = [b for b in (await self._bib.stand()).buecher if b.art == ART and (not buch or b.kennung == buch)]
        if buch and not buecher:
            raise BuchFehlt(f"Eine Frage-Antwort-Quelle {buch} gibt es in der Bibliothek nicht")
        mit = [(b.kennung, d) for b in buecher if (d := self._eigen.datei(b.kennung))]
        return mit, [b.kennung for b in buecher if not self._eigen.datei(b.kennung)]

    # ----- Schlagwörter ----------------------------------------------------------------------------------------------

    async def schlagwoerter(self, buch: str = "", anfang: str = "", ab: int = 0, anzahl: int = 50) -> SchlagwortSeite:
        quellen, ohne = await self._quellen(buch)
        von, bis = _bereich(anfang.strip().lower())

        def holen(datei: Path) -> list[sqlite3.Row]:
            return _lesen(datei, lambda v: v.execute("SELECT wort, fragen, stimmen FROM register_schlagwoerter WHERE wort >= ? "
                                                     "AND wort < ?", (von, bis)).fetchall())

        gesammelt: dict[str, SchlagwortEintrag] = {}
        for kennung, zeilen in zip((k for k, _ in quellen),
                                   await asyncio.gather(*(asyncio.to_thread(holen, d) for _, d in quellen)), strict=True):
            for z in zeilen:
                e = gesammelt.setdefault(z["wort"], SchlagwortEintrag(wort=z["wort"], fragen=0, stimmen=0, buecher=[]))
                e.fragen += z["fragen"]
                e.stimmen += z["stimmen"]
                e.buecher.append(kennung)
        liste = sorted(gesammelt.values(), key=lambda e: (-e.fragen, e.wort))
        return SchlagwortSeite(eintraege=liste[ab:ab + anzahl], gesamt=len(liste), ohne_index=ohne)

    async def fragen(self, wort: str, buch: str = "", sortierung: Sortierung = "stimmen", ab: int = 0,
                     anzahl: int = 30) -> FragenSeite:
        quellen, ohne = await self._quellen(buch)
        wort = wort.strip().lower()
        reihenfolge = "f.stimmen DESC" if sortierung == "stimmen" else "f.gefragt DESC, f.stimmen DESC"

        def holen(kennung: str, datei: Path) -> tuple[list[RegisterFrage], int]:
            def arbeit(v):
                zeilen = v.execute(f"SELECT s.nr, s.pfad, s.titel, s.einleitung, f.stimmen, f.antworten, f.akzeptiert, f.gefragt "
                                   f"FROM schlagwoerter w JOIN fragen f ON f.nr = w.nr JOIN seiten s ON s.nr = w.nr "
                                   f"WHERE w.wort = ? ORDER BY {reihenfolge} LIMIT ?", (wort, ab + anzahl)).fetchall()
                gesamt = v.execute("SELECT fragen FROM register_schlagwoerter WHERE wort = ?", (wort,)).fetchone()
                fragen = [RegisterFrage(buch=kennung, pfad=z["pfad"], titel=z["titel"], auszug=z["einleitung"][:300],
                                        stimmen=z["stimmen"], antworten=z["antworten"], akzeptiert=bool(z["akzeptiert"]),
                                        gefragt=datum(z["gefragt"]),
                                        schlagwoerter=[w["wort"] for w in v.execute("SELECT wort FROM schlagwoerter WHERE nr = ?",
                                                                                    (z["nr"],))])
                          for z in zeilen]
                return fragen, gesamt["fragen"] if gesamt else 0
            return _lesen(datei, arbeit)

        teile = await asyncio.gather(*(asyncio.to_thread(holen, k, d) for k, d in quellen))
        alle = [f for liste, _ in teile for f in liste]
        if sortierung == "stimmen":
            alle.sort(key=lambda f: -f.stimmen)
        else:
            alle.sort(key=lambda f: ("-".join(reversed(f.gefragt.split("."))), f.stimmen), reverse=True)
        return FragenSeite(wort=wort, eintraege=alle[ab:ab + anzahl], gesamt=sum(g for _, g in teile), ohne_index=ohne)

    # ----- Autoren ---------------------------------------------------------------------------------------------------

    async def autoren(self, buch: str = "", anfang: str = "", ab: int = 0, anzahl: int = 50) -> AutorenSeite:
        quellen, ohne = await self._quellen(buch)
        von, bis = _bereich(anfang.strip())

        def holen(kennung: str, datei: Path) -> tuple[list[AutorEintrag], int]:
            def arbeit(v):
                filter_, werte = ("WHERE autor >= ? COLLATE NOCASE AND autor < ? COLLATE NOCASE", [von, bis]) if anfang.strip() else ("", [])
                zeilen = v.execute(f"SELECT * FROM register_autoren {filter_} ORDER BY beitraege DESC, stimmen DESC LIMIT ?",
                                   [*werte, ab + anzahl]).fetchall()
                gesamt = v.execute(f"SELECT COUNT(*) FROM register_autoren {filter_}", werte).fetchone()[0]
                return [_autor(kennung, z) for z in zeilen], gesamt
            return _lesen(datei, arbeit)

        teile = await asyncio.gather(*(asyncio.to_thread(holen, k, d) for k, d in quellen))
        alle = sorted((a for liste, _ in teile for a in liste), key=lambda a: (-a.beitraege, -a.stimmen))
        return AutorenSeite(eintraege=alle[ab:ab + anzahl], gesamt=sum(g for _, g in teile), ohne_index=ohne)

    async def autor(self, buch: str, schluessel: str, ab: int = 0, anzahl: int = 30) -> AutorSeite | None:
        quellen, _ = await self._quellen(buch)
        if not quellen:
            return None
        datei = quellen[0][1]

        def arbeit(v) -> AutorSeite | None:
            z = v.execute("SELECT * FROM register_autoren WHERE schluessel = ?", (schluessel,)).fetchone()
            if z is None:
                return None
            zeilen = v.execute("SELECT s.pfad, s.titel, b.art, b.stimmen, b.datum, b.akzeptiert FROM beitraege b "
                               "JOIN seiten s ON s.nr = b.nr WHERE b.schluessel = ? ORDER BY b.stimmen DESC LIMIT ? OFFSET ?",
                               (schluessel, anzahl, ab)).fetchall()
            return AutorSeite(autor=_autor(buch, z), gesamt=z["beitraege"],
                              beitraege=[AutorBeitrag(pfad=r["pfad"], titel=r["titel"], art=r["art"], stimmen=r["stimmen"],
                                                      datum=datum(r["datum"]), akzeptiert=bool(r["akzeptiert"])) for r in zeilen])

        return await asyncio.to_thread(_lesen, datei, arbeit)
