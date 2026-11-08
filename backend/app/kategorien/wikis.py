"""Welches Wiki von Wikimedia hinter einem Buch steht (für seine Kategorien aus den Datenabzügen, WIKI-75)."""

from __future__ import annotations

import re

#: Projekte von Wikimedia, wie sie im Namen der ZIM-Dateien stehen, und ihr Name in den Datenabzügen
PROJEKTE = {"wikipedia": "wiki", "wikivoyage": "wikivoyage", "wiktionary": "wiktionary", "wikibooks": "wikibooks",
            "wikiquote": "wikiquote", "wikisource": "wikisource", "wikiversity": "wikiversity", "wikinews": "wikinews"}

_KENNUNG = re.compile(r"^(?P<projekt>wiki[a-z]+)_(?P<sprache>[a-z]{2,3})_")


def wiki(kennung: str) -> str | None:
    """Das Wiki eines Buchs aus seiner Kennung (wikipedia_de_all_maxi_2026-01 -> dewiki); kein Wikimedia-Buch: None."""
    m = _KENNUNG.match(kennung)
    if not m or m["projekt"] not in PROJEKTE:
        return None
    return m["sprache"] + PROJEKTE[m["projekt"]]


def host(kennung: str) -> str | None:
    """Die Adresse des Wikis eines Buchs (wikipedia_de_all_maxi_2026-01 -> de.wikipedia.org), etwa für seine Bilder."""
    m = _KENNUNG.match(kennung)
    if not m or m["projekt"] not in PROJEKTE:
        return None
    return f"{m['sprache']}.{m['projekt']}.org"
