"""Seitenweise Seiten einer Kategorie aus der Kategoriendatei (WIKI-75): eine große Kategorie (etwa "Mann" mit
Hunderttausenden Artikeln) kommt nicht auf einmal; die Kategorieseite holt hier die nächsten ab der letzten gezeigten."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from appkern.app import Geruest

from ..modell.artikel import Kategorieverweis
from .abfrage import Kategorienindex


def router(geruest: Geruest, kategorien: Kategorienindex) -> APIRouter:
    r = APIRouter(prefix="/api/v1/kategorien", tags=["kategorien"], dependencies=[geruest.pflicht])

    @r.get("/{buch}/seiten", response_model=list[Kategorieverweis], summary="Weitere Seiten einer Kategorie")
    async def seiten(buch: str, kategorie: str = Query(min_length=1, max_length=400, description="Pfad der Kategorie, etwa Kategorie:Planet"),
                     ab: int = Query(ge=0, description="Nummer (nr) der letzten schon gezeigten Seite")) -> list[Kategorieverweis]:
        """Die nächsten Seiten der Kategorie in der Ordnung der Titel, ab der Seite mit Nummer `ab` (ausschließlich)."""
        weitere = await kategorien.weitere(buch, kategorie, ab)
        if weitere is None:
            raise HTTPException(404, "Keine solche Kategorie in diesem Buch")
        return weitere

    return r
