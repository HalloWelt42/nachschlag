"""Wege der großen Bilder (WIKI-80): Stand des Bildholers, anhalten und fortsetzen, Angaben zu einem großen Bild
(Urheber, Lizenz, Breite). Das Bild selbst liefert der Medienweg mit `gross=1`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from appkern.app import Geruest
from bildholer.ablage import Angaben
from bildholer.modelle import Stand

from .dienst import Grossbilder


def router(geruest: Geruest, bilder: Grossbilder) -> APIRouter:
    r = APIRouter(prefix="/api/v1/bilder", tags=["bilder"])

    @r.get("/stand", response_model=Stand, dependencies=[geruest.pflicht], summary="Stand des Bildholers")
    async def stand() -> Stand:
        s = await bilder.stand()
        if s is None:
            raise HTTPException(503, "Der Bildholer antwortet nicht")
        return s

    @r.post("/anhalten", response_model=Stand, dependencies=[geruest.mensch], summary="Bildholer anhalten")
    async def anhalten() -> Stand:
        return await _oder_503(bilder.anhalten(True))

    @r.post("/fortsetzen", response_model=Stand, dependencies=[geruest.mensch], summary="Bildholer fortsetzen")
    async def fortsetzen() -> Stand:
        return await _oder_503(bilder.anhalten(False))

    @r.get("/angaben/{buch}/{pfad:path}", response_model=Angaben, dependencies=[geruest.lesen],
           summary="Urheber und Lizenz eines großen Bilds")
    async def angaben(buch: str, pfad: str) -> Angaben:
        gefunden = bilder.finden(buch, pfad)
        if gefunden is None:
            raise HTTPException(404, "Kein großes Bild (noch nicht geholt)")
        return gefunden[1]

    return r


async def _oder_503(aufruf) -> Stand:
    s = await aufruf
    if s is None:
        raise HTTPException(503, "Der Bildholer antwortet nicht")
    return s
