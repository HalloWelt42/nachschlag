"""Schnittstelle von Ausprobieren (WIKI-48): ob es geht (welche Sprachen, bei PHP welche Fassungen), ein Probelauf und
die Funktionen je PHP-Fassung für den Editor (WIKI-52)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from appkern.app import Geruest

from .dienst import Ausprobieren, Ausprobierstand, Probelauf, Sprache


class Probe(BaseModel):
    code: str = Field(min_length=1, max_length=20_000)
    sprache: Sprache
    fassung: str = Field("", max_length=10, description="PHP-Fassung, etwa 8.3; leer: die neueste")
    eingabe: list[str] = Field(default_factory=list, max_length=50)


def router(geruest: Geruest, ausprobieren: Ausprobieren) -> APIRouter:
    r = APIRouter(prefix="/api/v1/ausprobieren", tags=["ausprobieren"], dependencies=[geruest.mensch])

    @r.get("", response_model=Ausprobierstand)
    async def stand() -> Ausprobierstand:
        return await ausprobieren.stand()

    @r.post("", response_model=Probelauf)
    async def laufen(probe: Probe) -> Probelauf:
        """Den Code in der Sandbox der Codeschmiede laufen lassen; geht es nicht, steht der Grund in `grund`."""
        return await ausprobieren.laufen(probe.code, probe.sprache, probe.fassung, probe.eingabe)

    @r.get("/funktionen/php", response_model=dict[str, list[str]])
    async def funktionen() -> dict[str, list[str]]:
        """Je PHP-Fassung die eingebauten Funktionen (klein geschrieben); leer, wenn die Codeschmiede nicht antwortet."""
        return await ausprobieren.funktionen()

    return r
