"""Suche über die Bücher der Bibliothek: der Index antwortet immer (der eigene, wenn das Buch einen hat, sonst der
Index der ZIM-Datei); die Bedeutungssuche läuft gleichzeitig mit einer
Wartezeit. Gemischt wird nach Rang (Reciprocal Rank Fusion, k = 60): ein Treffer, den beide Wege finden, steigt.
Antwortet die Bedeutungssuche nicht rechtzeitig oder ist sie nicht angebunden, steht `nur_index` in der Antwort; läuft sie
noch, zusätzlich `bedeutung_ausstehend`: eine Suche mit `nachliefern` wartet länger auf dieselbe Anfrage (nachliefern.py)."""

from __future__ import annotations

import asyncio
import html
import time
from collections.abc import Awaitable, Callable

from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..eigenindex import abfrage
from ..eigenindex.ablage import Eigenindizes
from ..modell.buch import Buch
from ..modell.suche import Suchergebnis, Treffer, Vorschlag, Zeiten
from . import index
from .vorschlaege import KANDIDATEN_JE_BUCH, genaue_wege, ordnen
from .bedeutung import Bedeutung, BedeutungFehlt, Fundstelle
from .nachliefern import Ausstehend, LaufendeBedeutung
from .bilder import Trefferbilder

RRF_K = 60
#: Gewichte der beiden Wege je Einstellung Mischung (Index, Bedeutung): der bevorzugte Weg zählt doppelt (WIKI-79)
MISCHUNG: dict[str, tuple[float, float]] = {"index": (2.0, 1.0), "ausgewogen": (1.0, 1.0), "bedeutung": (1.0, 2.0)}


def _rang(platz: int) -> float:
    return 1.0 / (RRF_K + platz)


class Suche:
    def __init__(self, bibliothek: Bibliothek, bedeutung: Bedeutung, wartezeit_s: Callable[[], float],
                 bedeutungsbuch: Callable[[], Awaitable[str]], medien: Callable[[str, str], str], eigen: Eigenindizes,
                 nutzbare: Callable[[], Awaitable[list[Buch]]] | None = None, mischung: Callable[[], str] = lambda: "ausgewogen",
                 vorgewaehlt: Callable[[], Awaitable[list[str]]] | None = None,
                 nachliefern_s: Callable[[], float] = lambda: 30.0) -> None:
        """`bedeutungsbuch`: Kennung des Buchs, zu dem die Bedeutungssuche gehört (ihre Treffer zeigen in dieses Buch); nach
        einer neuen Fassung die neue (WIKI-58).
        `nutzbare`: die Quellen ohne Auswahl (ohne archivierte, die nicht mitgenutzt werden, WIKI-46); sonst alle.
        `mischung`: Einstellung, wie die Wege gewichtet werden (MISCHUNG). `vorgewaehlt`: Kennungen der Bücher, in denen
        ohne eigene Auswahl gesucht wird (Einstellung Bücher in der Suche); leer: alle nutzbaren (WIKI-79).
        `nachliefern_s`: so lange wartet eine Nachfrage auf die Bedeutungssuche (WIKI-98)."""
        self._bib, self._bedeutung, self._warten, self._bedeutungsbuch = bibliothek, bedeutung, wartezeit_s, bedeutungsbuch
        self._medien, self._eigen = medien, eigen
        self._nutzbare, self._mischung, self._vorgewaehlt = nutzbare, mischung, vorgewaehlt
        self._bilder = Trefferbilder(bibliothek, medien) if medien else None
        self._nachliefern_s = nachliefern_s
        self._laufend = LaufendeBedeutung(bedeutung.suchen)

    async def _buecher(self, auswahl: list[str]) -> list[Buch]:
        """Die gewählten Quellen (auch archivierte, wer sie ausdrücklich wählt), ohne Wahl die aus der Einstellung Bücher
        in der Suche, sonst die nutzbaren."""
        if not auswahl and self._vorgewaehlt is not None:
            auswahl = await self._vorgewaehlt()
        alle = (await self._bib.stand()).buecher if auswahl or self._nutzbare is None else await self._nutzbare()
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

    async def suchen(self, frage: str, buecher: list[str] | None = None, anzahl: int = 20,
                     wege: str = "beide", nachliefern: bool = False) -> Suchergebnis:
        """`nachliefern`: die Nachfrage, nachdem die Bedeutungssuche nicht rechtzeitig antwortete; sie wartet länger
        (Einstellung) auf dieselbe Anfrage."""
        gewaehlt = await self._buecher(buecher or [])
        start = time.perf_counter()
        buch = await self._bedeutungsbuch()
        mit_bedeutung = wege in ("beide", "bedeutung") and self._bedeutung.angebunden() and (
            not buecher or buch in buecher)
        warten = self._nachliefern_s() if nachliefern else self._warten()
        aufgabe = asyncio.create_task(self._laufend.suchen(frage, anzahl, warten)) if mit_bedeutung else None
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
        ausstehend = False
        if aufgabe:
            try:
                stellen, bedeutung_ms = await aufgabe
            except Ausstehend:
                ausstehend = not nachliefern
                hinweis = (f"Bedeutungssuche braucht länger als {warten:.1f} s, ihre Treffer kommen nach" if ausstehend
                           else f"Bedeutungssuche antwortete auch nach {warten:.0f} s nicht")
            except BedeutungFehlt as f:
                hinweis = f.meldung

        w_index, w_bedeutung = MISCHUNG.get(self._mischung(), MISCHUNG["ausgewogen"])
        gemischt: dict[tuple[str, str], Treffer] = {}
        for t in index_treffer:
            t.rang *= w_index
            gemischt[(t.buch, t.pfad)] = t
        beste: Treffer | None = None
        for platz, s in enumerate(stellen, 1):
            schluessel = (buch, s.pfad)
            stelle_text = html.escape(s.text[:320]) + (" ..." if len(s.text) > 320 else "")
            if schluessel in gemischt:
                t = gemischt[schluessel]
                t.wege = ["bedeutung", "index"]
                t.rang += w_bedeutung * _rang(platz)
                if not t.abschnitt:
                    t.abschnitt, t.ausschnitt = s.abschnitt, stelle_text
            else:
                gemischt[schluessel] = Treffer(buch=buch, pfad=s.pfad, titel=s.titel or s.pfad.replace("_", " "),
                                               abschnitt=s.abschnitt, ausschnitt=stelle_text, wege=["bedeutung"],
                                               rang=w_bedeutung * _rang(platz))
            if beste is None:
                beste = gemischt[schluessel].model_copy()
        liste = sorted(gemischt.values(), key=lambda t: t.rang, reverse=True)[:anzahl]
        if self._bilder is not None:                      # Leitbild je Treffer (WIKI-19), gleichzeitig gelesen
            for t, bild in zip(liste, await asyncio.gather(*(self._bilder.bild(t.buch, t.pfad) for t in liste)), strict=True):
                t.bild = t.bild or bild
        return Suchergebnis(frage=frage, treffer=liste, beste_stelle=beste, nur_index=not stellen, hinweis=hinweis,
                            bedeutung_ausstehend=ausstehend,
                            bedeutung_angebunden=self._bedeutung.angebunden(),
                            zeiten=Zeiten(index_ms=index_ms, bedeutung_ms=bedeutung_ms), index_gesamt=gesamt)

    async def vorschlaege(self, anfang: str, buecher: list[str] | None = None, anzahl: int = 8) -> list[Vorschlag]:
        """Titel zum Getippten aus allen gewählten Büchern, gemeinsam geordnet (vorschlaege.py, WIKI-93): der genaue
        Titel zuerst, Artikel vor Weiterleitungen, jede Seite einmal."""
        gewaehlt = [b for b in await self._buecher(buecher or []) if b.faehigkeiten.titelindex]

        def holen(b: Buch) -> list[Vorschlag]:
            a = self._bib.archiv(b.kennung)
            pfade = list(index.titel(a, anfang, KANDIDATEN_JE_BUCH))
            for w in genaue_wege(anfang):                      # der genaue Titel, auch wenn der Index ihn spät nennt
                for gibt, holt in ((a.has_entry_by_path, a.get_entry_by_path), (a.has_entry_by_title, a.get_entry_by_title)):
                    try:
                        if gibt(w):
                            pfade.insert(0, holt(w).path)
                    except RuntimeError:
                        pass
            ergebnis = []
            for pfad in dict.fromkeys(pfade):
                try:
                    e = a.get_entry_by_path(pfad)
                    weiter = self._bib.weiterleitung(b.kennung, pfad)
                except (KeyError, EintragFehlt, RuntimeError):
                    continue
                ergebnis.append(Vorschlag(buch=b.kennung, pfad=pfad, titel=e.title, weiterleitung=weiter))
            return ergebnis

        listen = await asyncio.gather(*(asyncio.to_thread(holen, b) for b in gewaehlt))
        rang = {b.kennung: i for i, b in enumerate(gewaehlt)}
        return ordnen((v for liste in listen for v in liste), anfang, rang, anzahl)


__all__ = ["Suche", "BuchFehlt", "EintragFehlt"]
