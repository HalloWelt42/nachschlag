"""Medien der Artikel: jedes Bild mit Unterschrift, Abschnitt und Größe, an einer Stelle aus dem aufbereiteten Artikel
gelesen (Mediensuche und große Bildansicht nutzen dasselbe).

Die Mediensuche baut keinen eigenen Index über alle Unterschriften (das hieße, jedes Buch einmal ganz zu lesen): sie
sucht Artikel zur Frage über den Index der Bücher und sammelt deren Bilder; Bilder, deren Unterschrift die Frage trägt,
stehen vorn."""

from __future__ import annotations

import asyncio
from urllib.parse import unquote

from lxml import html as lhtml

from ..artikel import Artikelleser
from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.artikel import Artikel
from ..modell.medien import Medienergebnis, Medium
from ..suche import Suche

#: Aus so vielen Artikeln zur Frage werden Bilder gesammelt
ARTIKEL_JE_SUCHE = 10
#: So viele Artikel werden gleichzeitig gelesen
GLEICHZEITIG = 4


def _zahl(wert: str | None) -> int:
    try:
        return int(wert or 0)
    except ValueError:
        return 0


def _medium(artikel: Artikel, img: lhtml.HtmlElement, unterschrift: str, abschnitt: str) -> Medium:
    quelle = img.get("src", "")
    return Medium(buch=artikel.buch, pfad=artikel.pfad, artikel=artikel.titel, abschnitt=abschnitt, bild=quelle,
                  breite=_zahl(img.get("width")), hoehe=_zahl(img.get("height")),
                  unterschrift=" ".join((unterschrift or img.get("alt", "")).split()), datei=unquote(quelle.rsplit("/", 1)[-1]))


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
        for el in text.iter("h2", "h3", "figure", "img"):
            if el.tag in ("h2", "h3"):
                abschnitt = el.text_content().strip()
            elif el.tag == "figure":
                img = next(el.iter("img"), None)
                unter = next(el.iter("figcaption"), None)
                if img is not None:
                    nehmen(_medium(artikel, img, unter.text_content() if unter is not None else "", abschnitt))
            elif next(el.iterancestors("figure"), None) is None:
                nehmen(_medium(artikel, el, "", abschnitt))
    return medien


class Medien:
    def __init__(self, leser: Artikelleser, suche: Suche) -> None:
        self._leser, self._suche = leser, suche

    async def im_artikel(self, buch: str, pfad: str) -> list[Medium]:
        return medien_aus(await self._leser.lesen(buch, pfad))

    async def suchen(self, frage: str, buecher: list[str]) -> Medienergebnis:
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
        alle = [m for liste in je_artikel for m in liste]
        passende = [m for m in alle if passt(m)]
        uebrige = [m for m in alle if not passt(m)]
        return Medienergebnis(frage=frage, medien=passende + uebrige, artikel=sum(1 for liste in je_artikel if liste), passend=len(passende))
