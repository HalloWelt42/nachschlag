"""Bilder zu Suchtreffern (WIKI-19): das Leitbild einer Seite, gelesen aus ihrem Rohinhalt ohne volle Aufbereitung
(die kostet je Artikel ein Vielfaches). Das erste Bild, das kein Zeichen ist: kleine Bilder (unter MINDESTBREITE Pixel)
und SVG ohne Größenangabe (Symbole, Flaggen) zählen nicht, Bilder aus dem Netz und eingebettete Daten auch nicht.
Einmal gefunden, merkt es sich die Seite (begrenzt, je Fassung eines Buchs eigen)."""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Callable

from ..bausteine import html as h
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt

IMG = re.compile(rb"<img\b[^>]*>", re.I)
SRC = re.compile(rb"""\bsrc=["']([^"']+)["']""", re.I)
BREITE = re.compile(rb"""\bwidth=["']?(\d+)""", re.I)
MINDESTBREITE = 80
#: so viel vom Anfang einer Seite wird nach dem Leitbild durchsucht (das Leitbild steht vorn)
VORN = 300_000
GEMERKT_HOECHSTENS = 20_000


def leitbild(inhalt: bytes) -> str:
    """Adresse des Leitbilds, wie sie in der Seite steht (relativ zur Seite); keins: leer."""
    for m in IMG.finditer(inhalt[:VORN]):
        tag = m.group(0)
        s = SRC.search(tag)
        if not s:
            continue
        src = s.group(1).decode("utf-8", "replace")
        if src.startswith("data:") or h.ist_online(src):
            continue
        breite = BREITE.search(tag)
        if breite and int(breite.group(1)) < MINDESTBREITE:
            continue
        if not breite and src.lower().split("?")[0].endswith(".svg"):
            continue
        return src
    return ""


class Trefferbilder:
    def __init__(self, bibliothek: Bibliothek, medien: Callable[[str, str], str]) -> None:
        """`medien(buch, pfad)`: Adresse eines Mediums im Buch für die Oberfläche."""
        self._bib, self._medien = bibliothek, medien
        self._gemerkt: OrderedDict[tuple[str, str], str] = OrderedDict()

    async def _lesen(self, buch: str, pfad: str) -> str:
        try:
            e = await self._bib.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt):
            return ""
        if not e.mime.startswith("text/html"):
            return ""
        src = leitbild(e.inhalt)
        return self._medien(buch, h.ziel_im_buch(e.pfad, src)) if src else ""

    async def bild(self, buch: str, pfad: str) -> str:
        schluessel = (buch, pfad)
        if schluessel in self._gemerkt:
            self._gemerkt.move_to_end(schluessel)
            return self._gemerkt[schluessel]
        bild = await self._lesen(buch, pfad)
        self._gemerkt[schluessel] = bild
        if len(self._gemerkt) > GEMERKT_HOECHSTENS:
            self._gemerkt.popitem(last=False)
        return bild
