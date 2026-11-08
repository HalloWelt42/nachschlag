"""Medien der Artikel: jedes Bild mit Unterschrift, Abschnitt und Größe, an einer Stelle aus dem aufbereiteten Artikel
gelesen (Mediensuche und große Bildansicht nutzen dasselbe).

Die Mediensuche baut keinen eigenen Index über alle Unterschriften (das hieße, jedes Buch einmal ganz zu lesen): sie
sucht Artikel zur Frage über den Index der Bücher und sammelt deren Bilder; Bilder, deren Unterschrift die Frage trägt,
stehen vorn."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from urllib.parse import unquote

from lxml import html as lhtml

from ..artikel import Artikelleser
from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.artikel import Artikel
from ..modell.medien import Medienart, Medienergebnis, Medium
from ..suche import Suche

#: Aus so vielen Artikeln zur Frage werden Bilder gesammelt
ARTIKEL_JE_SUCHE = 10
#: So viele Artikel werden gleichzeitig gelesen
GLEICHZEITIG = 4
#: Woran eine Karte zu erkennen ist (Dateiname oder Unterschrift): Lage-, Übersichts-, Relief- und Verbreitungskarten
KARTE = re.compile(r"karte|(?:\b|_)(?:map|range|lage)(?:\b|_)|locator|location|lageplan|relief|verbreitung|distribution|"
                   r"eingefärbt", re.IGNORECASE)
#: Pfad im Buch aus der Adresse eines Mediums in der App (für den Bildholer)
_IM_BUCH = re.compile(r"^/api/v1/inhalt/medien/[^/]+/(.+)$")


def pfad_im_buch(adresse: str) -> str:
    m = _IM_BUCH.match(adresse.split("?", 1)[0])
    return unquote(m.group(1)) if m else ""


def _zahl(wert: str | None) -> int:
    try:
        return int(wert or 0)
    except ValueError:
        return 0


def _medium(artikel: Artikel, img: lhtml.HtmlElement, unterschrift: str, abschnitt: str) -> Medium:
    quelle = img.get("src", "")
    unter, datei = " ".join((unterschrift or img.get("alt", "")).split()), unquote(quelle.rsplit("/", 1)[-1])
    return Medium(buch=artikel.buch, pfad=artikel.pfad, artikel=artikel.titel, abschnitt=abschnitt, bild=quelle,
                  breite=_zahl(img.get("width")), hoehe=_zahl(img.get("height")), unterschrift=unter, datei=datei,
                  art="karte" if KARTE.search(f"{datei} {unter}") else "bild")


def _ton(artikel: Artikel, el: lhtml.HtmlElement, abschnitt: str) -> Medium | None:
    quelle = el.get("src") or next((s.get("src", "") for s in el.iter("source")), "")
    if not quelle:
        return None
    figur = next(el.iterancestors("figure"), None)
    unter = next(figur.iter("figcaption"), None) if figur is not None else None
    return Medium(buch=artikel.buch, pfad=artikel.pfad, artikel=artikel.titel, abschnitt=abschnitt, bild=quelle, art="ton",
                  unterschrift=" ".join((unter.text_content() if unter is not None else el.get("title", "")).split()),
                  datei=unquote(quelle.rsplit("/", 1)[-1]))


def medien_aus(artikel: Artikel) -> list[Medium]:
    """Alle Bilder eines Artikels in Lesereihenfolge: zuerst das des Steckbriefs, dann die im Text mit ihrem Abschnitt.
    Jedes Bild einmal; Symbole ohne Größe oder unter 40 Pixeln bleiben weg."""
    medien: list[Medium] = []
    gesehen: set[str] = set()

    def nehmen(m: Medium) -> None:
        if m.bild and m.bild not in gesehen and not (0 < m.breite < 40):
            gesehen.add(m.bild)
            medien.append(m)

    if artikel.steckbrief and artikel.steckbrief.html:
        kasten = lhtml.fragment_fromstring(artikel.steckbrief.html, create_parent="div")
        for img in kasten.iter("img"):
            nehmen(_medium(artikel, img, (img.getparent().text_content() if img.getparent() is not None else ""), ""))
    if artikel.html:
        text = lhtml.fragment_fromstring(artikel.html, create_parent="div")
        abschnitt = ""
        for el in text.iter("h2", "h3", "figure", "img", "audio"):
            if el.tag in ("h2", "h3"):
                abschnitt = el.text_content().strip()
            elif el.tag == "audio":
                if (ton := _ton(artikel, el, abschnitt)) and ton.bild not in gesehen:
                    gesehen.add(ton.bild)
                    medien.append(ton)
            elif el.tag == "figure":
                img = next(el.iter("img"), None)
                unter = next(el.iter("figcaption"), None)
                if img is not None:
                    nehmen(_medium(artikel, img, unter.text_content() if unter is not None else "", abschnitt))
            elif next(el.iterancestors("figure"), None) is None:
                nehmen(_medium(artikel, el, "", abschnitt))
    return medien


class Medien:
    def __init__(self, leser: Artikelleser, suche: Suche, gross: Callable[[str, str], bool] | None = None) -> None:
        """`gross(buch, pfad im buch)`: hat der Bildholer das große Bild schon geholt (WIKI-80)?"""
        self._leser, self._suche, self._gross = leser, suche, gross

    def _markieren(self, medien: list[Medium]) -> list[Medium]:
        if self._gross:
            for m in medien:
                m.gross = m.art != "ton" and bool((p := pfad_im_buch(m.bild)) and self._gross(m.buch, p))
        return medien

    async def im_artikel(self, buch: str, pfad: str) -> list[Medium]:
        return self._markieren(medien_aus(await self._leser.lesen(buch, pfad)))

    async def suchen(self, frage: str, buecher: list[str], art: Medienart | None = None, nur_gross: bool = False) -> Medienergebnis:
        """Medien der Artikel zur Frage; wahlweise nur einer Art (Bild, Karte, Ton) und nur Bilder, deren große Fassung
        der Bildholer schon geholt hat (WIKI-24)."""
        treffer = (await self._suche.suchen(frage, buecher, ARTIKEL_JE_SUCHE, wege="index")).treffer
        grenze = asyncio.Semaphore(GLEICHZEITIG)

        async def lesen(buch: str, pfad: str) -> list[Medium]:
            async with grenze:
                try:
                    return await self.im_artikel(buch, pfad)
                except (BuchFehlt, EintragFehlt):
                    return []

        je_artikel = await asyncio.gather(*(lesen(t.buch, t.pfad) for t in treffer))
        woerter = [w for w in frage.casefold().split() if len(w) > 1]
        passt = lambda m: any(w in m.unterschrift.casefold() for w in woerter)  # noqa: E731
        alle = [m for liste in je_artikel for m in liste
                if (art is None or m.art == art) and (not nur_gross or m.gross)]
        passende = [m for m in alle if passt(m)]
        uebrige = [m for m in alle if not passt(m)]
        return Medienergebnis(frage=frage, medien=passende + uebrige, artikel=sum(1 for liste in je_artikel if liste), passend=len(passende))
