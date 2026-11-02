"""Schnittstelle der Stapelarbeit je Sammlung (WIKI-44): Stand (Aufträge und Ergebnisse) und Anstoßen, je Konto; dazu
die Stimmen fürs Vertonen (dieselbe Auswahl wie in den Einstellungen)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from appkern.anmeldung import Konto
from appkern.app import Geruest
from appkern.einstellungen import Angebot, Option

from .dienst import Arbeit, Sammlungen, Sammlungsstand
from .ton import Format


class SammlungStart(BaseModel):
    arbeiten: list[Arbeit] = Field(min_length=1)
    bereich: str | None = Field(None, description="nur dieser Bereich des Themas; leer: das ganze Thema")
    wann: Literal["jetzt", "nachts"] = "jetzt"
    stimme: str = Field("", max_length=200, description="Vertonen: Stimme; leer: wie beim Vorlesen")
    format: Format = "opus"


def router(geruest: Geruest, sammlungen: Sammlungen, stimmen: Callable[[], Awaitable[Angebot]]) -> APIRouter:
    r = APIRouter(prefix="/api/v1/meins/sammlungen", tags=["sammlungen"])

    @r.get("/stimmen", response_model=list[Option])
    async def stimmenwahl(konto: Konto = geruest.mensch) -> list[Option]:
        """Die Stimmen fürs Vertonen: eigene, die die Vertonung freigibt, und der Katalog des Sprechdienstes."""
        return (await stimmen()).optionen

    @r.get("/{thema}", response_model=Sammlungsstand)
    async def stand(thema: str, konto: Konto = geruest.mensch) -> Sammlungsstand:
        return await sammlungen.stand(konto.id, thema)

    @r.post("/{thema}", response_model=Sammlungsstand)
    async def anstossen(thema: str, start: SammlungStart, konto: Konto = geruest.mensch) -> Sammlungsstand:
        """Ein Auftrag je gewählter Arbeit, jetzt oder für heute Nacht (bis dahin zurückgestellt)."""
        try:
            return await sammlungen.anstossen(konto.id, konto.name, thema, start.arbeiten, start.bereich, start.wann,
                                              start.stimme, start.format)
        except KeyError:
            raise HTTPException(status_code=404, detail="Das Thema gibt es nicht")

    return r
