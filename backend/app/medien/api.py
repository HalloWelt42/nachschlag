"""Schnittstelle Medien unter /api/v1/medien (die Dateien selbst liefert /api/v1/inhalt/medien)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from appkern.app import Geruest

from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.medien import Medienart, Medienergebnis, Medium
from .dienst import Medien


def router(geruest: Geruest, medien: Medien) -> APIRouter:
    r = APIRouter(prefix="/api/v1/medien", tags=["medien"], dependencies=[geruest.pflicht])

    @r.get("", response_model=Medienergebnis)
    async def suchen(frage: str = Query(min_length=1, max_length=200), buecher: list[str] = Query(default=[]),
                     art: Medienart | None = Query(None, description="nur Bilder, Karten oder Töne; leer: alle"),
                     gross: bool = Query(False, description="nur Bilder, deren große Fassung der Bildholer schon geholt hat")
                     ) -> Medienergebnis:
        """Bilder, Karten und Töne aus den Artikeln zur Frage; die, deren Unterschrift die Frage trägt, zuerst."""
        return await medien.suchen(frage, buecher, art, gross)

    @r.get("/artikel/{buch}/{pfad:path}", response_model=list[Medium])
    async def im_artikel(buch: str, pfad: str) -> list[Medium]:
        """Alle Bilder eines Artikels in Lesereihenfolge (Streifen der großen Bildansicht)."""
        try:
            return await medien.im_artikel(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise HTTPException(status_code=404, detail=str(f))

    return r
