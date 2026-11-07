"""Dienst der Anleitungssuche: findet den geltenden eigenen Index des Buchs und fragt ihn in einem Hilfsfaden ab (SQLite
blockiert). Ohne Index antwortet er leer mit `index = False`; der Index entsteht als Auftrag (Seite Aufträge)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from ..bausteine import Wege
from ..bibliothek import Bibliothek, BuchFehlt
from ..eigenindex import schema
from ..eigenindex.ablage import Eigenindizes
from ..modell.anleitungen import Anleitungsfrage, Anleitungsfunde, Einordnung, Werkzeugeintrag
from . import abfrage

ART = "anleitung"
T = TypeVar("T")


class Anleitungen:
    def __init__(self, bibliothek: Bibliothek, eigen: Eigenindizes, wege: Wege) -> None:
        self._bib, self._eigen, self._wege = bibliothek, eigen, wege

    async def _datei(self, buch: str) -> Path | None:
        if not any(b.kennung == buch and b.art == ART for b in (await self._bib.stand()).buecher):
            raise BuchFehlt(f"Ein Anleitungsbuch {buch} gibt es in der Bibliothek nicht")
        return self._eigen.datei(buch)

    async def _fragen(self, buch: str, arbeit: Callable, leer: T) -> T:
        datei = await self._datei(buch)
        if datei is None:
            return leer

        def lesen():
            v = schema.lesen(datei)
            try:
                return arbeit(v)
            finally:
                v.close()
        return await asyncio.to_thread(lesen)

    async def finden(self, buch: str, frage: Anleitungsfrage) -> Anleitungsfunde:
        def medien(pfad: str) -> str:
            return self._wege.medien(buch, pfad)
        return await self._fragen(buch, lambda v: abfrage.finden(v, frage, medien), Anleitungsfunde(index=False))

    async def werkzeuge(self, buch: str, sprachen: list[str], anfang: str = "") -> list[Werkzeugeintrag]:
        return await self._fragen(buch, lambda v: abfrage.werkzeuge(v, sprachen, anfang), [])

    async def einordnung(self, buch: str, pfad: str) -> Einordnung:
        return await self._fragen(buch, lambda v: abfrage.einordnung(v, pfad), Einordnung())
