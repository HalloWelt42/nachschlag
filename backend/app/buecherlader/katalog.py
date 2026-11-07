"""Titel, Beschreibung und Zahl der Einträge aus dem Katalog der Bücher (Atom-Feed), damit das Verzeichnis lesbar wird.
Wahlweise: ohne Katalog zeigt Nachschlag den Stamm des Namens. Zugeordnet wird über den Dateinamen im Verweis zum Laden,
der den Stamm trägt (`.../wikipedia_de_all_maxi_2026-10.zim.meta4`)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from .verzeichnis import zerlegen

_ATOM = "{http://www.w3.org/2005/Atom}"
#: Sprachen im Namen der Dateien und im Katalog (ISO 639-3)
KATALOGSPRACHE = {"de": "deu", "en": "eng", "mul": "mul"}


@dataclass(frozen=True)
class Katalogeintrag:
    titel: str
    beschreibung: str
    eintraege: int


def eintraege_aus(feed: str | bytes) -> dict[str, Katalogeintrag]:
    """Je Stamm Titel, Beschreibung und Zahl der Artikel; Einträge ohne Verweis auf eine ZIM-Datei fallen weg."""
    aus: dict[str, Katalogeintrag] = {}
    for e in ET.fromstring(feed).iter(f"{_ATOM}entry"):
        ziel = next((l.get("href", "") for l in e.iter(f"{_ATOM}link") if l.get("type") == "application/x-zim"), "")
        name = zerlegen(ziel.rsplit("/", 1)[-1].removesuffix(".meta4"))
        if not name:
            continue
        zahl = (e.findtext(f"{_ATOM}articleCount") or "0").strip()
        aus[name.stamm] = Katalogeintrag(titel=(e.findtext(f"{_ATOM}title") or "").strip(),
                                         beschreibung=(e.findtext(f"{_ATOM}summary") or "").strip(),
                                         eintraege=int(zahl) if zahl.isdigit() else 0)
    return aus
