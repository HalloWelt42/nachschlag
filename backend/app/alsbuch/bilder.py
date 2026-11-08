"""Bilder fürs Buch (WIKI-45): die Adresse eines Bilds in der App (Medien eines Buchs) wird zu Daten und Art, auf Wunsch
das große Bild des Bildholers mit Urheber und Lizenz. Nur Bilder aus der Bibliothek, nie aus dem Netz. WebP (so liegen
viele Bilder in den Büchern) kennen ältere Lesegeräte nicht: es wird JPEG, mit Durchsicht PNG."""

from __future__ import annotations

import asyncio
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from PIL import Image, UnidentifiedImageError

from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .epub import BILDARTEN

MEDIEN = re.compile(r"^/api/v1/inhalt/medien/(?P<buch>[^/?#]+)/(?P<pfad>[^?#]+)")
#: Güte beim Umwandeln von WebP in JPEG
JPEG_GUETE = 88


@dataclass
class Bilddatei:
    daten: bytes
    art: str
    urheber: str = ""
    lizenz: str = ""


class Bildquelle:
    def __init__(self, bibliothek: Bibliothek, gross: Callable[[str, str], tuple[Path, object] | None]) -> None:
        """`gross(buch, pfad)`: das große Bild des Bildholers (Datei und Angaben mit mime, urheber, lizenz) oder None."""
        self._bib, self._gross = bibliothek, gross

    async def holen(self, adresse: str, gross: bool = False) -> Bilddatei | None:
        m = MEDIEN.match(adresse)
        if not m:
            return None
        buch, pfad = unquote(m["buch"]), unquote(m["pfad"])
        if gross and (gefunden := self._gross(buch, pfad)):
            datei, angaben = gefunden
            art = getattr(angaben, "mime", "")
            if art in BILDARTEN:
                return Bilddatei(await asyncio.to_thread(datei.read_bytes), art, getattr(angaben, "urheber", ""),
                                 getattr(angaben, "lizenz", ""))
        try:
            e = await self._bib.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt):
            return None
        art = e.mime.split(";")[0].strip()
        return Bilddatei(e.inhalt, art) if art in BILDARTEN else None


def fuer_jedes_lesegeraet(d: Bilddatei) -> Bilddatei:
    """WebP als JPEG (mit Durchsicht als PNG); alles andere bleibt. Ein Bild, das sich nicht lesen lässt, bleibt auch."""
    if d.art != "image/webp":
        return d
    try:
        with Image.open(io.BytesIO(d.daten)) as bild:
            aus = io.BytesIO()
            if bild.mode in ("RGBA", "LA") or "transparency" in bild.info:
                bild.save(aus, "PNG", optimize=True)
                return Bilddatei(aus.getvalue(), "image/png", d.urheber, d.lizenz)
            bild.convert("RGB").save(aus, "JPEG", quality=JPEG_GUETE)
            return Bilddatei(aus.getvalue(), "image/jpeg", d.urheber, d.lizenz)
    except (UnidentifiedImageError, OSError):
        return d
