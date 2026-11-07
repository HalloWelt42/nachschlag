"""Schnittstelle der Anleitungssuche (WIKI-64): Treffer mit Filtern und Facetten, Werkzeuge für Ich habe, Einordnung einer
Seite im Gerätebaum."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from appkern.app import Geruest

from ..bibliothek import BuchFehlt
from ..modell.anleitungen import Anleitungsfrage, Anleitungsfunde, Einordnung, Werkzeugeintrag
from .dienst import Anleitungen


def _frage(frage: Annotated[Anleitungsfrage, Query()]) -> Anleitungsfrage:
    return frage


def router(geruest: Geruest, anleitungen: Anleitungen) -> APIRouter:
    r = APIRouter(prefix="/api/v1/anleitungen", tags=["anleitungen"], dependencies=[geruest.pflicht])

    async def mit(arbeit):
        try:
            return await arbeit
        except BuchFehlt as f:
            raise HTTPException(404, str(f))

    @r.get("/{buch}", response_model=Anleitungsfunde)
    async def finden(buch: str, frage: Anleitungsfrage = Depends(_frage)) -> Anleitungsfunde:
        """Anleitungen (oder Zerlegungen, Geräte) mit Filtern: Text, Sprachen, Schwierigkeit, Zeit, Ich habe, Gerät, Bauteil."""
        return await mit(anleitungen.finden(buch, frage))

    @r.get("/{buch}/werkzeuge", response_model=list[Werkzeugeintrag])
    async def werkzeuge(buch: str, sprachen: Annotated[list[str], Query()] = ["de"], anfang: str = "") -> list[Werkzeugeintrag]:  # noqa: B006
        """Werkzeuge nach Zahl der Anleitungen, die sie brauchen; `anfang` filtert auf den Wortanfang."""
        return await mit(anleitungen.werkzeuge(buch, sprachen, anfang))

    @r.get("/{buch}/einordnung", response_model=Einordnung)
    async def einordnung(buch: str, pfad: str) -> Einordnung:
        """Weg von der Startseite zu einer Geräteseite oder (über ihr Gerät) zu einer Anleitung, samt Bauteil."""
        return await mit(anleitungen.einordnung(buch, pfad))

    return r
