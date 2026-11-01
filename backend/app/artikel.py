"""Artikel lesen: Eintrag aus der Bibliothek holen, Baustein nach der Art des Buchs wählen, aufbereiten."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from .bausteine import Wege, baustein_fuer
from .bausteine.basis import Aufbereitet
from .bausteine.html import online_adresse
from .bibliothek import Bibliothek, EintragFehlt
from .modell.artikel import Artikel


#: so oft zieht der Zufall neu, wenn er eine Sprungseite ohne Ziel in der Quelle trifft
ZUFALL_ZUEGE = 12


def _pfad(pfad: str) -> str:
    return quote(pfad, safe="/()_-,.:'!*~")


def wege(bibliothek: Bibliothek) -> Wege:
    """Die Adressen der App für Verweise und Medien, an einer Stelle."""
    return Wege(artikel=lambda buch, pfad: f"/lesen/{quote(buch)}/{_pfad(pfad)}",
                medien=lambda buch, pfad: f"/api/v1/inhalt/medien/{quote(buch)}/{_pfad(pfad)}",
                original=lambda buch, pfad: f"/api/v1/inhalt/original/{quote(buch)}/{_pfad(pfad)}",
                gibt_es=bibliothek.gibt_es, datei=bibliothek.datei,
                schlagwort=lambda buch, wort: f"/register/schlagwoerter/{quote(wort, safe='')}?buch={quote(buch)}",
                autor=lambda buch, nr: f"/register/autoren/{quote(buch)}/{quote(nr, safe='')}")


def _verfasser(fertig: Aufbereitet) -> dict[str, str]:
    """Autor und Datum für Zitate: bei Frage und Antwort, wer fragte und wann; sonst nennt die Quelle niemanden."""
    if fertig.frage is None:
        return {}
    frage = next((b for b in fertig.frage.beitraege if b.art == "frage"), None)
    return {"autor": frage.autor if frage else "", "datum": fertig.frage.gefragt}


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
                       darstellung=fertig.darstellung or baustein.darstellung, baustein=baustein.kennung,
                       html=fertig.html, einleitung=fertig.einleitung, abschnitte=fertig.abschnitte,
                       steckbrief=fertig.steckbrief, bild=fertig.bild, verweise=fertig.verweise, online=fertig.online,
                       original=self._wege.original(buch, eintrag.pfad), kacheln=fertig.kacheln,
                       gruppen=fertig.gruppen, rubrik=fertig.rubrik, rubrik_pfad=fertig.rubrik_pfad, nachbarn=fertig.nachbarn, titelart=fertig.titelart,
                       fragen=fertig.fragen, zurueck=fertig.zurueck, weiter=fertig.weiter, belege=fertig.belege,
                       quelle_url=online_adresse(b, eintrag.pfad), **_verfasser(fertig))

    async def zufall(self, buch: str) -> str:
        """Pfad eines zufälligen Artikels, der sich lesen lässt. Weiterleitungen sind aufgelöst; eine Sprungseite, deren
        Ziel in dieser Quelle fehlt (Auszüge wie climate-change verweisen auf Artikel, die nicht dabei sind), wird
        übergangen und neu gezogen. Findet sich nach einigen Zügen nichts, `EintragFehlt`."""
        a = self._bib.archiv(buch)
        for _ in range(ZUFALL_ZUEGE):
            pfad = await asyncio.to_thread(lambda: a.get_random_entry().path)
            try:
                return (await self._bib.eintrag(buch, pfad)).pfad
            except EintragFehlt:
                continue
        raise EintragFehlt(f"In {buch} fand sich in {ZUFALL_ZUEGE} Zügen kein lesbarer Artikel")
