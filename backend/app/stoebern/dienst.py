"""Stöbern über die Bücher: Zufallsfund mit Filtern, der Entdeckungspfad (wohin es von einem Artikel aus weitergeht) und
Blättern in der Reihenfolge des Buchs.

Blättern: libzim 4 kennt keinen Gang über den Titelindex; die Einträge liegen aber nach Pfad geordnet in der Datei
(`get_entry_by_id`), und Pfade sind in den Büchern die Titel. Eine Seite sammelt von einer Stelle aus Artikel (HTML, keine
Weiterleitung) vorwärts oder rückwärts; ein Buchstabe wird per Halbierung über die Pfade gefunden.

Hat das Buch einen eigenen Index mit Titelfolge (WIKI-21), blättert es in deutscher Ordnung (Umlaute bei ihrem Grundlaut,
Groß und Klein gleich); die Stellen sind dann Plätze in dieser Folge statt Einträge der Datei."""

from __future__ import annotations

import asyncio
import html
import random
import re
from collections.abc import Awaitable, Callable
from urllib.parse import quote, unquote

from libzim.reader import Archive
from lxml import html as lhtml

from ..artikel import Artikelleser
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..eigenindex import schema as indexschema
from ..eigenindex.abfrage import rueckverweise
from ..eigenindex.ablage import Eigenindizes
from ..modell.artikel import Artikel
from ..modell.stoebern import Blatteintrag, Buchseite, Fund, Nachbar, Pfadschritt, Richtung
from ..suche import Suche

#: So oft wird ein Zufallsfund gezogen, bis einer zu den Filtern passt
ZUFALL_VERSUCHE = 25
#: Länge des Auszugs (erster Absatz) in Zeichen
AUSZUG_ZEICHEN = 420
#: Wie viele Schritte je Spalte des Entdeckungspfads
SCHRITTE_JE_SPALTE = 6
#: Ab so vielen Zeichen Text gilt ein Artikel als lang (Filter "lang", WIKI-24)
LANG_ZEICHEN = 15000
#: Höchstens so viele Einträge der Datei werden für eine Buchseite angesehen (Bilder und Beiwerk liegen dazwischen)
BLAETTERN_HOECHSTENS = 4000

_EM = re.compile(r"</?em>")


def _auszug(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= AUSZUG_ZEICHEN else text[:AUSZUG_ZEICHEN].rsplit(" ", 1)[0] + " ..."


def _textlaenge(artikel: Artikel) -> int:
    return len(lhtml.fragment_fromstring(artikel.html, create_parent="div").text_content()) if artikel.html else 0


def fund_aus(artikel: Artikel) -> Fund:
    return Fund(buch=artikel.buch, pfad=artikel.pfad, titel=artikel.titel, bild=artikel.bild, auszug=_auszug(artikel.einleitung))


def verweise_aus(artikel: Artikel, anzahl: int) -> list[Nachbar]:
    """Verweise im Text auf Artikel desselben Buchs, in ihrer Reihenfolge, jeder einmal, mit dem Abschnitt, in dem er steht."""
    vorne = f"/lesen/{quote(artikel.buch)}/"
    doc = lhtml.fragment_fromstring(artikel.html or "<div></div>", create_parent="div")
    abschnitt, gesehen, nachbarn = "Einleitung", {artikel.pfad}, []
    for el in doc.iter("h2", "h3", "a"):
        if el.tag in ("h2", "h3"):
            abschnitt = el.text_content().strip() or abschnitt
            continue
        href = el.get("href", "")
        if not href.startswith(vorne):
            continue
        pfad = unquote(href[len(vorne):].split("#", 1)[0])
        titel = el.text_content().strip()
        if not pfad or not titel or pfad in gesehen:
            continue
        gesehen.add(pfad)
        nachbarn.append(Nachbar(pfad=pfad, titel=titel, hinweis=f"im Abschnitt {abschnitt}" if abschnitt != "Einleitung" else "in der Einleitung"))
        if len(nachbarn) == anzahl:
            break
    return nachbarn


def _ist_artikel(a: Archive, nummer: int, springt: Callable[[str], bool]) -> Blatteintrag | None:
    """Ein Artikel zum Blättern: HTML, keine Weiterleitung und keine Sprungseite, kein Beiwerk (Pfade mit _)."""
    e = a.get_entry_by_id(nummer)
    if e.is_redirect or e.path.startswith("_"):
        return None
    try:
        if not e.get_item().mimetype.startswith("text/html") or springt(e.path):
            return None
    except RuntimeError:
        return None
    return Blatteintrag(pfad=e.path, titel=e.title)


def _erste_ab(a: Archive, anfang: str) -> int:
    """Stelle des ersten Eintrags, dessen Pfad nicht vor `anfang` liegt (Halbierung über die geordneten Pfade)."""
    unten, oben = 0, a.entry_count
    while unten < oben:
        mitte = (unten + oben) // 2
        if a.get_entry_by_id(mitte).path < anfang:
            unten = mitte + 1
        else:
            oben = mitte
    return unten


def buchseite(a: Archive, start: int, richtung: Richtung, anzahl: int, springt: Callable[[str], bool]) -> Buchseite:
    """Bis zu `anzahl` Artikel ab `start` vorwärts (oder vor `start` rückwärts), in Buchreihenfolge."""
    schritt = 1 if richtung == "vor" else -1
    nummer = start if richtung == "vor" else start - 1
    gefunden: list[tuple[int, Blatteintrag]] = []
    angesehen = 0
    while 0 <= nummer < a.entry_count and len(gefunden) < anzahl and angesehen < BLAETTERN_HOECHSTENS:
        if eintrag := _ist_artikel(a, nummer, springt):
            gefunden.append((nummer, eintrag))
        nummer += schritt
        angesehen += 1
    gefunden.sort(key=lambda x: x[0])
    if not gefunden:
        return Buchseite(eintraege=[], erste=start, naechste=-1)
    ende = gefunden[-1][0] + 1
    return Buchseite(eintraege=[e for _, e in gefunden], erste=gefunden[0][0], naechste=ende if ende < a.entry_count else -1)


_FOLGE = ("SELECT s.pfad, s.titel FROM titelfolge t JOIN seiten s ON s.nr = t.nr "
          "ORDER BY t.schluessel, t.nr LIMIT ? OFFSET ?")


def titelseite(v, start: int, richtung: Richtung, anzahl: int) -> Buchseite:
    """Bis zu `anzahl` Seiten ab Platz `start` vorwärts (oder vor `start` rückwärts) in deutscher Ordnung."""
    gesamt = v.execute("SELECT COUNT(*) FROM titelfolge").fetchone()[0]
    von = max(start, 0) if richtung == "vor" else max(start - anzahl, 0)
    bis = min(von + anzahl, gesamt) if richtung == "vor" else max(start, 0)
    zeilen = v.execute(_FOLGE, (max(bis - von, 0), von)).fetchall()
    eintraege = [Blatteintrag(pfad=z["pfad"], titel=z["titel"]) for z in zeilen]
    if not eintraege:
        return Buchseite(eintraege=[], erste=start, naechste=-1)
    return Buchseite(eintraege=eintraege, erste=von, naechste=von + len(eintraege) if von + len(eintraege) < gesamt else -1)


def platz_von(v, pfad: str) -> int | None:
    """Platz einer Seite in der Titelfolge; nicht im Index: None."""
    z = v.execute("SELECT t.schluessel, t.nr FROM seiten s JOIN titelfolge t ON t.nr = s.nr WHERE s.pfad = ?", (pfad,)).fetchone()
    if z is None:
        return None
    return v.execute("SELECT COUNT(*) FROM titelfolge WHERE (schluessel, nr) < (?, ?)", (z["schluessel"], z["nr"])).fetchone()[0]


def platz_ab(v, buchstabe: str) -> int:
    return v.execute("SELECT COUNT(*) FROM titelfolge WHERE schluessel < ?", (indexschema.sortierschluessel(buchstabe),)).fetchone()[0]


class Stoebern:
    def __init__(self, bibliothek: Bibliothek, leser: Artikelleser, suche: Suche,
                 gelesen: Callable[[str, str, str], Awaitable[bool]], eigen: Eigenindizes | None = None,
                 themenartikel: Callable[[str], Awaitable[list[tuple[str, str]]]] | None = None) -> None:
        """`gelesen(konto, buch, pfad)`: hat das Konto die Seite schon geöffnet (Verlauf)? `eigen`: die eigenen
        Indizes; kennt der des Buchs die Verweise, sind "erwähnt in" echte Rückverweise (WIKI-20). `themenartikel(konto)`:
        Buch und Pfad jedes Artikels in den Themen des Kontos (Filter "nahe an meinen Themen", WIKI-24)."""
        self._bib, self._leser, self._suche, self._gelesen, self._eigen = bibliothek, leser, suche, gelesen, eigen
        self._themenartikel = themenartikel

    async def fund(self, buch: str, pfad: str) -> Fund:
        return fund_aus(await self._leser.lesen(buch, pfad))

    async def zufall(self, konto: str, buch: str, mit_bild: bool, ungelesen: bool, lang: bool = False,
                     nahe: bool = False) -> Fund:
        """Ein Zufallsfund, der zu den Filtern passt; nach so vielen Versuchen ohne passenden der letzte gezogene.
        `lang`: nur Artikel mit viel Text; `nahe`: ein Artikel, auf den ein Artikel der eigenen Themen verweist und der
        selbst in keinem Thema steht (ohne Themen wie sonst)."""
        nachbarn = await self._nahe(konto, buch) if nahe else []
        fund: Fund | None = None
        for _ in range(ZUFALL_VERSUCHE):
            if nachbarn:
                von, pfad = random.choice(nachbarn)
                artikel = await self._leser.lesen(von, pfad)
            else:
                artikel = await self._leser.lesen(buch, await self._leser.zufall(buch))
            fund = fund_aus(artikel)
            if ((mit_bild and not fund.bild) or (lang and _textlaenge(artikel) < LANG_ZEICHEN)
                    or (ungelesen and await self._gelesen(konto, artikel.buch, fund.pfad))):
                continue
            return fund
        assert fund is not None
        return fund

    async def _nahe(self, konto: str, buch: str) -> list[tuple[str, str]]:
        """Artikel, auf die Artikel der eigenen Themen verweisen (im gewählten Buch zuerst), ohne die schon in Themen."""
        if not self._themenartikel:
            return []
        alle = await self._themenartikel(konto)
        drin = set(alle)
        quellen = [a for a in alle if a[0] == buch] or alle
        nachbarn: list[tuple[str, str]] = []
        for von, pfad in random.sample(quellen, min(len(quellen), 5)):
            try:
                artikel = await self._leser.lesen(von, pfad)
            except (BuchFehlt, EintragFehlt):
                continue
            nachbarn += [(von, n.pfad) for n in verweise_aus(artikel, 40) if (von, n.pfad) not in drin]
        return nachbarn

    async def schritt(self, buch: str, pfad: str) -> Pfadschritt:
        artikel = await self._leser.lesen(buch, pfad)
        (nennen, hierher), aehnlich = await asyncio.gather(self._nennen(artikel), self._aehnlich(artikel))
        return Pfadschritt(fund=fund_aus(artikel), von_hier=verweise_aus(artikel, SCHRITTE_JE_SPALTE), erwaehnt_in=nennen,
                           verweist_hierher=hierher, aehnlich=aehnlich)

    async def _nennen(self, artikel: Artikel) -> tuple[list[Nachbar], bool]:
        """Seiten, die auf den Artikel verweisen, wenn der eigene Index des Buchs die Verweise kennt (WIKI-20); sonst
        Artikel, die den Titel im Text nennen (Volltext des Buchs), ohne den Artikel selbst. Dazu, welches von beiden."""
        if self._eigen and (datei := self._eigen.datei(artikel.buch)):
            r = await asyncio.to_thread(rueckverweise, datei, artikel.pfad, SCHRITTE_JE_SPALTE)
            if r is not None:
                return [Nachbar(pfad=x.pfad, titel=x.titel, hinweis="verweist hierher") for x in r[0]], True
        ergebnis = await self._suche.suchen(artikel.titel, [artikel.buch], SCHRITTE_JE_SPALTE + 1, wege="index")
        return [Nachbar(pfad=t.pfad, titel=t.titel, hinweis=_auszug(html.unescape(_EM.sub("", t.ausschnitt)))[:120])
                for t in ergebnis.treffer if t.pfad != artikel.pfad][:SCHRITTE_JE_SPALTE], False

    async def _aehnlich(self, artikel: Artikel) -> list[Nachbar]:
        """Ähnlich nach Bedeutung über den Fundus (mit der Einleitung als Frage); ohne Anbindung leer."""
        if not artikel.einleitung:
            return []
        ergebnis = await self._suche.suchen(artikel.einleitung[:300], [artikel.buch], SCHRITTE_JE_SPALTE + 1, wege="bedeutung")
        return [Nachbar(pfad=t.pfad, titel=t.titel, hinweis=t.abschnitt)
                for t in ergebnis.treffer if t.pfad != artikel.pfad][:SCHRITTE_JE_SPALTE]

    async def blaettern(self, buch: str, *, um: str = "", buchstabe: str = "", ab: int = -1, bis: int = -1, anzahl: int = 13) -> Buchseite:
        """Eine Buchseite: um einen Artikel herum (er in der Mitte), ab einem Buchstaben, ab einer Stelle vorwärts oder vor
        einer Stelle rückwärts."""
        a = self._bib.archiv(buch)
        springt = lambda pfad: bool(self._bib.weiterleitung(buch, pfad))  # noqa: E731
        datei = self._eigen.datei(buch) if self._eigen else None

        def nach_titelfolge() -> Buchseite | None:
            """In deutscher Ordnung, wenn der eigene Index die Titelfolge trägt; sonst None (dann die Datei)."""
            if datei is None or not indexschema.aktuell(datei):
                return None
            v = indexschema.lesen(datei)
            try:
                if um:
                    ziel = (self._bib.weiterleitung(buch, um) or um).partition("#")[0]
                    platz = platz_von(v, ziel)
                    if platz is None:
                        return None
                    davor = titelseite(v, platz, "zurueck", anzahl // 2)
                    danach = titelseite(v, platz, "vor", anzahl - len(davor.eintraege))
                    return Buchseite(eintraege=davor.eintraege + danach.eintraege,
                                     erste=davor.erste if davor.eintraege else danach.erste, naechste=danach.naechste, hier=ziel)
                if buchstabe:
                    return titelseite(v, platz_ab(v, buchstabe), "vor", anzahl)
                if bis >= 0:
                    return titelseite(v, bis, "zurueck", anzahl)
                return titelseite(v, max(ab, 0), "vor", anzahl)
            finally:
                v.close()

        def arbeit() -> Buchseite:
            if (seite := nach_titelfolge()) is not None:
                return seite
            if um:
                ziel = (self._bib.weiterleitung(buch, um) or um).partition("#")[0]
                stelle = a.get_entry_by_path(ziel)._index
                davor = buchseite(a, stelle, "zurueck", anzahl // 2, springt)
                danach = buchseite(a, stelle, "vor", anzahl - len(davor.eintraege), springt)
                return Buchseite(eintraege=davor.eintraege + danach.eintraege, erste=davor.erste if davor.eintraege else danach.erste,
                                 naechste=danach.naechste, hier=ziel)
            if buchstabe:
                # Pfade sind byteweise geordnet: Großbuchstaben vor Kleinbuchstaben; Handbücher beginnen oft klein
                seite = buchseite(a, _erste_ab(a, buchstabe.upper()), "vor", anzahl, springt)
                if seite.eintraege and seite.eintraege[0].pfad[:1].upper() == buchstabe.upper():
                    return seite
                klein = buchseite(a, _erste_ab(a, buchstabe.lower()), "vor", anzahl, springt)
                return klein if klein.eintraege and klein.eintraege[0].pfad[:1].lower() == buchstabe.lower() else seite
            if bis >= 0:
                return buchseite(a, bis, "zurueck", anzahl, springt)
            return buchseite(a, max(ab, 0), "vor", anzahl, springt)

        return await asyncio.to_thread(arbeit)
