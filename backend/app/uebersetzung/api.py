"""Schnittstelle der übersetzten Suche (WIKI-40): eine Frage übersetzen (gemerkt oder über die Leitstelle) und eine
Übersetzung korrigieren. Ohne Leitstelle 503 mit dem Grund; die Suche läuft dann ohne Übersetzung."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from appkern.app import Geruest

from .dienst import Uebersetzer, Uebersetzung, UebersetzungFehlt


class Korrektur(BaseModel):
    frage: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=500)


def router(geruest: Geruest, uebersetzer: Uebersetzer) -> APIRouter:
    r = APIRouter(prefix="/api/v1/uebersetzung", tags=["uebersetzung"], dependencies=[geruest.pflicht])

    @r.get("", response_model=Uebersetzung)
    async def uebersetzen(frage: str = Query(min_length=1, max_length=500)) -> Uebersetzung:
        """Die Frage auf Englisch für die englischen Quellen."""
        try:
            return await uebersetzer.uebersetzen(frage)
        except UebersetzungFehlt as f:
            raise HTTPException(503, str(f)) from f

    @r.put("", response_model=Uebersetzung)
    async def korrigieren(eingabe: Korrektur) -> Uebersetzung:
        return await uebersetzer.korrigieren(eingabe.frage, eingabe.text)

    return r
