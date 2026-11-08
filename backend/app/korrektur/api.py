"""Schnittstelle der Suchkorrektur (WIKI-41): ein Vorschlag zur Frage, zuerst aus dem Wortschatz der Quellen; mit
`modell` (nur wenn die Suche nichts fand) auch über das lokale Modell. Ohne Vorschlag ist `vorschlag` leer."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Query

from appkern.app import Geruest

from .dienst import Korrektor, Korrektur


def router(geruest: Geruest, korrektor: Korrektor, an: Callable[[], bool] = lambda: True) -> APIRouter:
    """`an`: Einstellung Tippfehler verzeihen (WIKI-79); aus heißt: nie ein Vorschlag, auch wenn die Oberfläche fragt."""
    r = APIRouter(prefix="/api/v1/korrektur", tags=["korrektur"], dependencies=[geruest.pflicht])

    @r.get("", response_model=Korrektur)
    async def korrigieren(frage: str = Query(min_length=1, max_length=500), buecher: list[str] = Query(default_factory=list),
                          modell: bool = False) -> Korrektur:
        if not an():
            return Korrektur(frage=frage)
        return await korrektor.korrigieren(frage, buecher, mit_modell=modell)

    return r
