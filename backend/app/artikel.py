"""Artikel lesen: Eintrag aus der Bibliothek holen, Baustein nach der Art des Buchs wählen, aufbereiten."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from urllib.parse import quote

from .bausteine import Wege, baustein_fuer
from .bausteine.basis import Aufbereitet
from .bausteine.html import online_adresse
from .bibliothek import Bibliothek, EintragFehlt
from .kategorien.abfrage import Kategorienindex
from .modell.artikel import Artikel
from .originalansicht import Originalherkunft


#: so oft zieht der Zufall neu, wenn er eine Sprungseite ohne Ziel in der Quelle trifft
ZUFALL_ZUEGE = 12


def _pfad(pfad: str) -> str:
    return quote(pfad, safe="/()_-,.:'!*~")


def wege(bibliothek: Bibliothek) -> Wege:
    """Die Adressen der App für Verweise und Medien, an einer Stelle."""
    return Wege(artikel=lambda buch, pfad: f"/lesen/{quote(buch)}/{_pfad(pfad)}",
                medien=lambda buch, pfad: f"/api/v1/inhalt/medien/{quote(buch)}/{_pfad(pfad)}",
                gibt_es=bibliothek.gibt_es, datei=bibliothek.datei,
                schlagwort=lambda buch, wort: f"/register/schlagwoerter/{quote(wort, safe='')}?buch={quote(buch)}",
                autor=lambda buch, nr: f"/register/autoren/{quote(buch)}/{quote(nr, safe='')}")


def _verfasser(fertig: Aufbereitet) -> dict[str, str]:
    """Autor und Datum für Zitate: bei Frage und Antwort, wer fragte und wann; sonst nennt die Quelle niemanden."""
    if fertig.frage is None:
        return {}
    frage = next((b for b in fertig.frage.beitraege if b.art == "frage"), None)
    return {"autor": frage.autor if frage else "", "datum": fertig.frage.gefragt}


def original_weg(herkunft: Originalherkunft) -> Callable[[str, str], str]:
    """(buch, pfad) -> Weg der unveränderten Seite auf der eigenen Herkunft der Originalseiten (WIKI-85)."""
    return lambda buch, pfad: herkunft.weg(buch, f"{quote(buch)}/{_pfad(pfad)}")


class Artikelleser:
    def __init__(self, bibliothek: Bibliothek, kategorien: Kategorienindex | None = None,
                 original: Callable[[str, str], str] = lambda buch, pfad: "") -> None:
        """`kategorien`: Kategorien aus den Datenabzügen für Bücher, die keine mitbringen (WIKI-75). `original`: der Weg
        der unveränderten Seite (`original_weg`); ohne ihn haben Artikel keine Originalseite."""
        self._bib = bibliothek
        self._wege = wege(bibliothek)
        self._kategorien = kategorien
        self._original = original

    async def lesen(self, buch: str, pfad: str) -> Artikel:
        b = await self._bib.buch(buch)
        try:
            eintrag = await self._bib.eintrag(buch, pfad)
        except EintragFehlt:
            seite = await self._kategorieseite(buch, pfad)
            if seite is None:
                raise
            return seite
        baustein = baustein_fuer(b, eintrag)
        fertig = await asyncio.to_thread(baustein.aufbereiten, b, eintrag, self._wege)
        if not fertig.kategorien and self._kategorien and (fertig.darstellung or baustein.darstellung) == "lesedesign":
            fertig.kategorien = await self._kategorien.der_seite(buch, eintrag.pfad)
        return Artikel(buch=buch, pfad=eintrag.pfad, angefragt=pfad, anker=eintrag.anker, titel=fertig.titel,
                       darstellung=fertig.darstellung or baustein.darstellung, baustein=baustein.kennung,
                       html=fertig.html, einleitung=fertig.einleitung, abschnitte=fertig.abschnitte,
                       steckbrief=fertig.steckbrief, bild=fertig.bild, verweise=fertig.verweise, online=fertig.online,
                       original=self._original(buch, eintrag.pfad), kacheln=fertig.kacheln,
                       gruppen=fertig.gruppen, rubrik=fertig.rubrik, rubrik_pfad=fertig.rubrik_pfad, nachbarn=fertig.nachbarn, titelart=fertig.titelart,
                       fragen=fertig.fragen, zurueck=fertig.zurueck, weiter=fertig.weiter, belege=fertig.belege,
                       quelle_url=online_adresse(b, eintrag.pfad), anleitung=fertig.anleitung, geraet=fertig.geraet,
                       uebung=fertig.uebung, kurse=fertig.kurse, kategorien=fertig.kategorien, kategorie=fertig.kategorie,
                       **_verfasser(fertig))

    async def _kategorieseite(self, buch: str, pfad: str) -> Artikel | None:
        """Eine Kategorie aus der Kategoriendatei (das Buch selbst hat keine Seite dafür); keine solche: None."""
        gefunden = await self._kategorien.kategorie(buch, pfad) if self._kategorien else None
        if gefunden is None:
            return None
        titel, angaben, anzahl = gefunden
        rubrik = " · ".join(["Kategorie", *([f"{len(angaben.unter)} Unterkategorien"] if angaben.unter else []),
                             *([f"{anzahl} Seiten"] if anzahl else [])])
        return Artikel(buch=buch, pfad=pfad, angefragt=pfad, titel=titel, darstellung="kategorie", baustein="kategorie", original="",
                       html="", rubrik=rubrik, kategorie=angaben, kategorien=angaben.ober)

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
