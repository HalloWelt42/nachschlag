"""Bilder fürs Buch (WIKI-45): die Adresse eines Bilds in der App (Medien eines Buchs) wird zu Daten und Art, auf Wunsch
das große Bild des Bildholers mit Urheber und Lizenz. Nur Bilder aus der Bibliothek, nie aus dem Netz."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .epub import BILDARTEN

MEDIEN = re.compile(r"^/api/v1/inhalt/medien/(?P<buch>[^/?#]+)/(?P<pfad>[^?#]+)")


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
