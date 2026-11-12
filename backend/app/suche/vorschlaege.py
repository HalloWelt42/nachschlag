"""Rangfolge der Vorschläge beim Tippen (WIKI-93).

Der Titelindex eines Buchs liefert Titel in seiner eigenen Ordnung: zu "Leipzig" erst Weiterleitungen wie "Leipziger
Bucht", der Artikel selbst später oder gar nicht. Darum je Buch mehr Kandidaten holen, den genauen Titel eigens
nachschlagen und über alle Bücher ordnen: genauer Titel, dann Titelanfang, dann Wortanfang, dann der Rest; innerhalb
einer Stufe Artikel vor Weiterleitungen, kürzere Titel zuerst. Mehrere Titel, die auf dieselbe Seite führen, zählen
einmal (der beste bleibt)."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..modell.suche import Vorschlag

#: so viele Titel je Buch aus dem Index, aus denen die besten gewählt werden
KANDIDATEN_JE_BUCH = 15
_WORT = re.compile(r"[\s\-_/(),.:;]+")


def genaue_wege(anfang: str) -> list[str]:
    """Pfade und Titel, unter denen der genaue Titel stehen kann (Wikipedia: Leerzeichen als Unterstrich, großer
    Anfangsbuchstabe)."""
    a = anfang.strip()
    if not a:
        return []
    gross = a[:1].upper() + a[1:]
    return list(dict.fromkeys([a, gross, a.replace(" ", "_"), gross.replace(" ", "_")]))


def stufe(titel: str, anfang: str) -> int:
    t, a = titel.casefold().strip(), anfang.casefold().strip()
    if t == a:
        return 0
    if t.startswith(a):
        return 1
    if any(w.startswith(a) for w in _WORT.split(t) if w):
        return 2
    return 3


def ordnen(vorschlaege: Iterable[Vorschlag], anfang: str, buchrang: dict[str, int], anzahl: int) -> list[Vorschlag]:
    def ziel(v: Vorschlag) -> tuple[str, str]:
        return v.buch, (v.weiterleitung or v.pfad).split("#", 1)[0]

    def schluessel(v: Vorschlag) -> tuple:
        return stufe(v.titel, anfang), bool(v.weiterleitung), buchrang.get(v.buch, 99), len(v.titel), v.titel.casefold()

    gesehen: set[tuple[str, str]] = set()
    aus: list[Vorschlag] = []
    for v in sorted(vorschlaege, key=schluessel):
        if ziel(v) in gesehen:
            continue
        gesehen.add(ziel(v))
        aus.append(v)
        if len(aus) >= anzahl:
            break
    return aus
