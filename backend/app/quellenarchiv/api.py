"""Schnittstelle des Archivs der Quellen (WIKI-46): eine Quelle archivieren, wieder aktiv setzen oder mitnutzen. Den
Archivstand jeder Quelle liefert /api/v1/buecher."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from appkern.app import Geruest

from ..bibliothek import BuchFehlt
from ..modell.buch import Buch
from .dienst import Quellenarchiv


class ArchivAenderung(BaseModel):
    zustand: Literal["archiv", "aktiv"] | None = Field(None, description="archiv, aktiv oder leer (wie von selbst: ältere "
                                                                          "Fassungen im Archiv)")
    mitnutzen: bool | None = Field(None, description="leer: wie bisher")


def router(geruest: Geruest, archiv: Quellenarchiv) -> APIRouter:
    r = APIRouter(prefix="/api/v1/buecher", tags=["quellenarchiv"], dependencies=[geruest.pflicht])

    @r.put("/{buch}/archiv", response_model=Buch)
    async def aendern(buch: str, aenderung: ArchivAenderung) -> Buch:
        try:
            return await archiv.setzen(buch, aenderung.zustand, aenderung.mitnutzen)
        except BuchFehlt as f:
            raise HTTPException(status_code=404, detail=str(f))

    return r
