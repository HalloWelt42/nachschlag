"""Artikel lesen: Eintrag aus der Bibliothek holen, Baustein nach der Art des Buchs wählen, aufbereiten."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from .bausteine import Wege, baustein_fuer
from .bibliothek import Bibliothek
from .modell.artikel import Artikel


def _pfad(pfad: str) -> str:
    return quote(pfad, safe="/()_-,.:'!*~")


def wege(bibliothek: Bibliothek) -> Wege:
    """Die Adressen der App für Verweise und Medien, an einer Stelle."""
    return Wege(artikel=lambda buch, pfad: f"/lesen/{quote(buch)}/{_pfad(pfad)}",
                medien=lambda buch, pfad: f"/api/v1/inhalt/medien/{quote(buch)}/{_pfad(pfad)}",
                original=lambda buch, pfad: f"/api/v1/inhalt/original/{quote(buch)}/{_pfad(pfad)}",
                gibt_es=bibliothek.gibt_es)


class Artikelleser:
    def __init__(self, bibliothek: Bibliothek) -> None:
        self._bib = bibliothek
        self._wege = wege(bibliothek)

    async def lesen(self, buch: str, pfad: str) -> Artikel:
        b = await self._bib.buch(buch)
        eintrag = await self._bib.eintrag(buch, pfad)
        baustein = baustein_fuer(b, eintrag)
        fertig = await asyncio.to_thread(baustein.aufbereiten, b, eintrag, self._wege)
        return Artikel(buch=buch, pfad=eintrag.pfad, angefragt=pfad, anker=eintrag.anker, titel=fertig.titel,
                       darstellung="lesedesign" if baustein.lesedesign else "original", baustein=baustein.kennung,
                       html=fertig.html, einleitung=fertig.einleitung, abschnitte=fertig.abschnitte,
                       steckbrief=fertig.steckbrief, bild=fertig.bild, verweise=fertig.verweise, online=fertig.online,
                       original=self._wege.original(buch, eintrag.pfad))

    async def zufall(self, buch: str) -> str:
        """Pfad eines zufälligen Artikels (ohne Weiterleitungen)."""
        a = self._bib.archiv(buch)
        return await asyncio.to_thread(lambda: a.get_random_entry().path)
