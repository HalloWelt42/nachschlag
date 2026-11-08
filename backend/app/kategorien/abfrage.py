"""Kategorien aus der Kategoriendatei eines Buchs lesen (auf dem Pi): die Kategorien einer Seite und eine Kategorieseite
mit Ober- und Unterkategorien und ihren Seiten, seitenweise in der Ordnung der Titel."""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path

from ..eigenindex.ablage import Eigenindizes
from ..modell.artikel import Kategorieangaben, Kategorieverweis
from . import schema

#: so viele Seiten einer Kategorie auf einmal (eine große Kategorie hat Hunderttausende)
SEITEN_JE_MAL = 2000


class Kategorienindex:
    def __init__(self, ablage: Eigenindizes) -> None:
        self._ablage = ablage
        self._offen: dict[Path, sqlite3.Connection] = {}

    def _verbindung(self, buch: str) -> sqlite3.Connection | None:
        pfad = self._ablage.datei(buch)
        if pfad is None:
            return None
        v = self._offen.get(pfad)
        if v is None:
            v = self._offen[pfad] = schema.lesen(pfad)
        return v

    def namensraum(self, buch: str) -> str:
        v = self._verbindung(buch)
        return schema.angabe(v, "namensraum") if v else ""

    def _verweis(self, v: sqlite3.Connection, titel: str, anzahl: int | None = None) -> Kategorieverweis:
        return Kategorieverweis(pfad=f"{schema.angabe(v, 'namensraum')}:{titel}", titel=schema.anzeigen(titel),
                                anzahl=anzahl)

    # ----- synchron (in einem Faden) ---------------------------------------------------------------------------------

    def _der_seite(self, buch: str, pfad: str) -> list[Kategorieverweis]:
        v = self._verbindung(buch)
        if v is None:
            return []
        zeilen = v.execute("SELECT k.titel FROM seite s JOIN seite_kategorie sk ON sk.seite = s.nr "
                           "JOIN kategorie k ON k.nr = sk.kategorie WHERE s.pfad = ? ORDER BY k.nr", (pfad,)).fetchall()
        return [self._verweis(v, z["titel"]) for z in zeilen]

    def _titel(self, v: sqlite3.Connection, pfad: str) -> str | None:
        praefix = schema.angabe(v, "namensraum") + ":"
        if not pfad.startswith(praefix):
            return None
        return pfad.removeprefix(praefix).replace(" ", "_")

    def _kategorie(self, buch: str, pfad: str) -> tuple[str, Kategorieangaben, int] | None:
        v = self._verbindung(buch)
        titel = self._titel(v, pfad) if v else None
        z = v.execute("SELECT nr, titel, seiten FROM kategorie WHERE titel = ?", (titel,)).fetchone() if titel else None
        if z is None:
            return None
        nr = z["nr"]
        ober = v.execute("SELECT k.titel FROM unterkategorie u JOIN kategorie k ON k.nr = u.ober WHERE u.unter = ? "
                         "ORDER BY k.nr", (nr,)).fetchall()
        unter = v.execute("SELECT k.titel, k.seiten FROM unterkategorie u JOIN kategorie k ON k.nr = u.unter "
                          "WHERE u.ober = ? ORDER BY k.nr", (nr,)).fetchall()
        angaben = Kategorieangaben(ober=[self._verweis(v, o["titel"]) for o in ober],
                                   unter=[self._verweis(v, u["titel"], u["seiten"]) for u in unter],
                                   seiten=self._seiten(v, nr, 0), seiten_gesamt=z["seiten"])
        return schema.anzeigen(z["titel"]), angaben, z["seiten"]

    def _seiten(self, v: sqlite3.Connection, nr: int, ab: int, anzahl: int = SEITEN_JE_MAL) -> list[Kategorieverweis]:
        zeilen = v.execute("SELECT s.nr, s.pfad, s.titel FROM seite_kategorie sk JOIN seite s ON s.nr = sk.seite "
                           "WHERE sk.kategorie = ? AND sk.seite > ? ORDER BY sk.seite LIMIT ?", (nr, ab, anzahl)).fetchall()
        return [Kategorieverweis(pfad=z["pfad"], titel=z["titel"], nr=z["nr"]) for z in zeilen]

    def _weitere(self, buch: str, pfad: str, ab: int) -> list[Kategorieverweis] | None:
        v = self._verbindung(buch)
        titel = self._titel(v, pfad) if v else None
        z = v.execute("SELECT nr FROM kategorie WHERE titel = ?", (titel,)).fetchone() if titel else None
        return self._seiten(v, z["nr"], ab) if z else None

    # ----- für die App -----------------------------------------------------------------------------------------------

    async def der_seite(self, buch: str, pfad: str) -> list[Kategorieverweis]:
        """Die Kategorien einer Seite in der Ordnung ihrer Titel; ohne Kategoriendatei keine."""
        return await asyncio.to_thread(self._der_seite, buch, pfad)

    async def kategorie(self, buch: str, pfad: str) -> tuple[str, Kategorieangaben, int] | None:
        """Titel, Angaben und Zahl der Seiten einer Kategorie (Pfad wie "Kategorie:Planet"); keine solche: None."""
        return await asyncio.to_thread(self._kategorie, buch, pfad)

    async def weitere(self, buch: str, pfad: str, ab: int) -> list[Kategorieverweis] | None:
        """Die nächsten Seiten einer Kategorie nach der Seite mit Nummer `ab`; keine solche Kategorie: None."""
        return await asyncio.to_thread(self._weitere, buch, pfad, ab)
