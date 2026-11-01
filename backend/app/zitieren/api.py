"""Schnittstelle des Zitierens (WIKI-31): eine Seite in allen Zitierformen, für das Notizblatt (die Form wählt das
Gerät; alle Formen kommen vorab mit, weil Browser die Zwischenablage nur direkt im Klick erlauben)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from appkern.app import Geruest

from ..artikel import Artikelleser
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .angaben import aus_artikel
from .formen import Zitate, zitate


def router(geruest: Geruest, bibliothek: Bibliothek, leser: Artikelleser) -> APIRouter:
    r = APIRouter(prefix="/api/v1/zitate", tags=["zitieren"], dependencies=[geruest.pflicht])

    @r.get("/{buch}/{pfad:path}", response_model=Zitate)
    async def seite(buch: str, pfad: str) -> Zitate:
        """Die Angaben der Seite und die Seite als einfaches Zitat, nach APA, nach DIN ISO 690 und als BibTeX."""
        try:
            return zitate(aus_artikel(await bibliothek.buch(buch), await leser.lesen(buch, pfad)))
        except (BuchFehlt, EintragFehlt) as f:
            raise HTTPException(status_code=404, detail=str(f))

    return r
