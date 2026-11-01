"""Schnittstelle des Vorlesens (WIKI-43) für den Vorleser der Oberfläche: `GET /api/v1/vorlesen` sagt, ob es gerade geht
(sonst mit Grund), `POST /api/v1/vorlesen` mit Text und dessen Sprache liefert den Strom Satz für Satz. Der erste Satz
wird abgewartet: was vorher scheitert, ist eine Antwort mit Grund und Status, kein abgebrochener Strom."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from appkern.app import Geruest

from .sprechdienst import NichtBereit, Sprechdienst

NDJSON = "application/x-ndjson"


class Vorlesestand(BaseModel):
    da: bool
    grund: str = ""


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1)
    sprache: str = Field("de", max_length=10, description="Sprache des Texts als Kennzeichen wie im HTML (de, en)")


def router(geruest: Geruest, sprechdienst: Sprechdienst) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["vorlesen"], dependencies=[geruest.pflicht])

    @r.get("/vorlesen", response_model=Vorlesestand)
    async def stand() -> Vorlesestand:
        """Ob Vorlesen gerade geht; die Oberfläche zeigt den Lautsprecher nur dann (nur zeigen, was geht)."""
        try:
            await sprechdienst.pruefen()
        except NichtBereit as f:
            return Vorlesestand(da=False, grund=f.meldung)
        return Vorlesestand(da=True)

    @r.post("/vorlesen", response_class=StreamingResponse)
    async def vorlesen(e: Vorlesetext) -> StreamingResponse:
        zeilen = sprechdienst.zeilen(e.text, e.sprache)
        try:
            erste = await anext(zeilen)
        except StopAsyncIteration:
            erste = b""
        except NichtBereit as f:
            raise HTTPException(f.status, f.meldung) from f

        async def alles() -> AsyncIterator[bytes]:
            yield erste
            async for z in zeilen:
                yield z

        return StreamingResponse(alles(), media_type=NDJSON, headers={"Cache-Control": "no-cache"})

    return r
