"""Index eines Buchs (in der ZIM-Datei eingebaut): Volltext für die Suche, Titel für Vorschläge beim Tippen. Gemessen
auf dem Pi (01.11.2026, deutsche Enzyklopädie): Volltext rund 11 ms, Vorschläge rund 70 ms."""

from __future__ import annotations

import html
import re

from libzim.reader import Archive
from libzim.search import Query, Searcher
from libzim.suggestion import SuggestionSearcher
from lxml import html as lhtml

from ..bausteine.html import gerade

WORT = re.compile(r"\w{3,}", re.UNICODE)


def volltext(a: Archive, frage: str, ab: int, anzahl: int) -> tuple[list[str], int]:
    """Pfade der Treffer und geschätzte Gesamtzahl."""
    suche = Searcher(a).search(Query().set_query(frage))
    return [r.path for r in suche.get_results(ab, anzahl)], suche.get_estimated_matches()


def titel(a: Archive, anfang: str, anzahl: int) -> list[str]:
    return list(SuggestionSearcher(a).suggest(anfang).get_results(0, anzahl))


def ausschnitt(inhalt: bytes, frage: str, laenge: int = 240) -> str:
    """Stelle um die ersten Fundwörter als reiner Text, Fundwörter in <em> (alles andere maskiert)."""
    try:
        doc = lhtml.fromstring(inhalt.decode("utf-8", "replace"))
    except (ValueError, lhtml.etree.ParserError):
        return ""
    absaetze = [re.sub(r"\s+", " ", p.text_content()).strip() for p in doc.iter("p")]
    text = gerade(" ".join(a for a in absaetze if len(a) > 30))
    woerter = [w.lower() for w in WORT.findall(frage)]
    unten = text.lower()
    stelle = min((i for w in woerter if (i := unten.find(w)) >= 0), default=0)
    anfang = max(0, stelle - laenge // 3)
    stueck = text[anfang:anfang + laenge]
    return ("... " if anfang else "") + markieren(html.escape(stueck), frage) + (" ..." if anfang + laenge < len(text) else "")


def markieren(sicher: str, frage: str) -> str:
    """Fundwörter der Frage (auch als Wortanfang) in schon maskiertem Text mit <em> auszeichnen."""
    for w in sorted({w.lower() for w in WORT.findall(frage)}, key=len, reverse=True):
        sicher = re.sub(f"({re.escape(html.escape(w))}\\w*)", r"<em>\1</em>", sicher, flags=re.I)
    return sicher
