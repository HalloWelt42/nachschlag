"""Suche über die Bücher der Bibliothek: der Index antwortet immer (der eigene, wenn das Buch einen hat, sonst der
Index der ZIM-Datei); die Bedeutungssuche läuft gleichzeitig mit einer
Wartezeit. Gemischt wird nach Rang (Reciprocal Rank Fusion, k = 60): ein Treffer, den beide Wege finden, steigt.
Antwortet die Bedeutungssuche nicht rechtzeitig oder ist sie nicht angebunden, steht `nur_index` in der Antwort."""

from __future__ import annotations

import asyncio
import html
import time
from collections.abc import Callable

from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..eigenindex import abfrage
from ..eigenindex.ablage import Eigenindizes
from ..modell.buch import Buch
from ..modell.suche import Suchergebnis, Treffer, Vorschlag, Zeiten
from . import index
from .bedeutung import Bedeutung, BedeutungFehlt, Fundstelle

RRF_K = 60


def _rang(platz: int) -> float:
    return 1.0 / (RRF_K + platz)


class Suche:
    def __init__(self, bibliothek: Bibliothek, bedeutung: Bedeutung, wartezeit_s: Callable[[], float],
                 bedeutungsbuch: Callable[[], str], medien: Callable[[str, str], str], eigen: Eigenindizes) -> None:
        """`bedeutungsbuch`: Kennung des Buchs, zu dem die Bedeutungssuche gehört (ihre Treffer zeigen in dieses Buch)."""
        self._bib, self._bedeutung, self._warten, self._bedeutungsbuch = bibliothek, bedeutung, wartezeit_s, bedeutungsbuch
        self._medien, self._eigen = medien, eigen

    async def _buecher(self, auswahl: list[str]) -> list[Buch]:
        alle = (await self._bib.stand()).buecher
        return [b for b in alle if (b.faehigkeiten.volltext or self._eigen.datei(b.kennung))
                and (not auswahl or b.kennung in auswahl)]

    def _eigen_suchen(self, b: Buch, frage: str, anzahl: int) -> tuple[list[Treffer], int] | None:
        """Treffer aus dem eigenen Index des Buchs (Ausschnitte aus dem Index, ohne das Buch zu lesen); None ohne ihn."""
        datei = self._eigen.datei(b.kennung)
        if datei is None:
            return None
        funde, gesamt = abfrage.suchen(datei, frage, anzahl)
        return [Treffer(buch=b.kennung, pfad=f.pfad, titel=f.titel, ausschnitt=f.ausschnitt, wege=["index"], rang=_rang(platz),
                        frage=f.frage) for platz, f in enumerate(funde, 1)], gesamt

    async def _index(self, buecher: list[Buch], frage: str, anzahl: int) -> tuple[list[Treffer], int]:
        """Treffer aller gewählten Bücher, je Buch nach Platz gerankt (die Indizes verschiedener Bücher sind nicht
        vergleichbar; der Platz schon)."""
        def suchen(b: Buch) -> tuple[list[Treffer], int]:
            if (eigen := self._eigen_suchen(b, frage, anzahl)) is not None:
                return eigen
            a = self._bib.archiv(b.kennung)
            pfade, gesamt = index.volltext(a, frage, 0, anzahl)
            treffer, gesehen = [], set()
            for platz, pfad in enumerate(pfade, 1):
                try:
                    # Weiterleitungen und Sprungseiten (Vulpes_vulpes -> Rotfuchs) zeigen auf ihr Ziel; jedes Ziel einmal
                    ziel, _, anker = (self._bib.weiterleitung(b.kennung, pfad) or pfad).partition("#")
                    if ziel in gesehen:
                        continue
                    e = a.get_entry_by_path(ziel)
                    inhalt = bytes(e.get_item().content)
                except (KeyError, RuntimeError):
                    continue
                gesehen.add(ziel)
                treffer.append(Treffer(buch=b.kennung, pfad=ziel, anker=anker, titel=e.title, ausschnitt=index.ausschnitt(inhalt, frage),
                                       wege=["index"], rang=_rang(platz)))
            return treffer, gesamt

        ergebnisse = await asyncio.gather(*(asyncio.to_thread(suchen, b) for b in buecher))
        return [t for liste, _ in ergebnisse for t in liste], sum(g for _, g in ergebnisse)

    async def _bedeutung_suchen(self, frage: str, anzahl: int) -> list[Fundstelle]:
        return await asyncio.wait_for(self._bedeutung.suchen(frage, anzahl), timeout=self._warten())

    async def suchen(self, frage: str, buecher: list[str] | None = None, anzahl: int = 20,
                     wege: str = "beide") -> Suchergebnis:
        gewaehlt = await self._buecher(buecher or [])
        start = time.perf_counter()
        mit_bedeutung = wege in ("beide", "bedeutung") and self._bedeutung.angebunden() and (
            not buecher or self._bedeutungsbuch() in buecher)
        aufgabe = asyncio.create_task(self._bedeutung_suchen(frage, anzahl)) if mit_bedeutung else None
        try:
            index_treffer, gesamt = await self._index(gewaehlt, frage, anzahl) if wege != "bedeutung" else ([], 0)
        except BaseException:
            if aufgabe:
                aufgabe.cancel()
            raise
        index_ms = int((time.perf_counter() - start) * 1000)

        stellen: list[Fundstelle] = []
        hinweis = "" if aufgabe else ("keine Bedeutungssuche angebunden" if not self._bedeutung.angebunden() else "")
        bedeutung_ms: int | None = None
        if aufgabe:
            try:
                stellen = await aufgabe
                bedeutung_ms = int((time.perf_counter() - start) * 1000)
            except asyncio.TimeoutError:
                hinweis = f"Bedeutungssuche antwortete nicht innerhalb von {self._warten():.1f} s"
            except BedeutungFehlt as f:
                hinweis = f.meldung

        gemischt: dict[tuple[str, str], Treffer] = {}
        for t in index_treffer:
            gemischt[(t.buch, t.pfad)] = t
        buch = self._bedeutungsbuch()
        beste: Treffer | None = None
        for platz, s in enumerate(stellen, 1):
            schluessel = (buch, s.pfad)
            stelle_text = html.escape(s.text[:320]) + (" ..." if len(s.text) > 320 else "")
            if schluessel in gemischt:
                t = gemischt[schluessel]
                t.wege = ["bedeutung", "index"]
                t.rang += _rang(platz)
                if not t.abschnitt:
                    t.abschnitt, t.ausschnitt = s.abschnitt, stelle_text
            else:
                gemischt[schluessel] = Treffer(buch=buch, pfad=s.pfad, titel=s.titel or s.pfad.replace("_", " "),
                                               abschnitt=s.abschnitt, ausschnitt=stelle_text, wege=["bedeutung"],
                                               rang=_rang(platz))
            if beste is None:
                beste = gemischt[schluessel].model_copy()
        liste = sorted(gemischt.values(), key=lambda t: t.rang, reverse=True)[:anzahl]
        return Suchergebnis(frage=frage, treffer=liste, beste_stelle=beste, nur_index=not stellen, hinweis=hinweis,
                            bedeutung_angebunden=self._bedeutung.angebunden(),
                            zeiten=Zeiten(index_ms=index_ms, bedeutung_ms=bedeutung_ms), index_gesamt=gesamt)

    async def vorschlaege(self, anfang: str, buecher: list[str] | None = None, anzahl: int = 8) -> list[Vorschlag]:
        gewaehlt = [b for b in await self._buecher(buecher or []) if b.faehigkeiten.titelindex]

        def holen(b: Buch) -> list[Vorschlag]:
            a = self._bib.archiv(b.kennung)
            ergebnis = []
            for pfad in index.titel(a, anfang, anzahl):
                try:
                    e = a.get_entry_by_path(pfad)
                    weiter = self._bib.weiterleitung(b.kennung, pfad)
                except (KeyError, EintragFehlt):
                    continue
                ergebnis.append(Vorschlag(buch=b.kennung, pfad=pfad, titel=e.title, weiterleitung=weiter))
            return ergebnis

        listen = await asyncio.gather(*(asyncio.to_thread(holen, b) for b in gewaehlt))
        return [v for liste in listen for v in liste][:anzahl]


__all__ = ["Suche", "BuchFehlt", "EintragFehlt"]
