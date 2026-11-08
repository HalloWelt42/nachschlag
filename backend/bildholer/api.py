"""Schnittstelle des Bildholers für Nachschlag, nur im eigenen Netz der Container (kein Port nach außen): Stand lesen,
Regeln setzen, Bilder vormerken, anhalten und fortsetzen."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI

from .arbeiter import Arbeiter
from .modelle import Regeln, Stand, Vormerkung
from .quelle import Bildquelle
from .schlange import Schlange


def app_bauen(daten: Path, ablage: Path, client: httpx.AsyncClient | None = None, *, arbeiten: bool = True) -> FastAPI:
    schlange = Schlange(daten / "bildholer.sqlite")
    http = client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True)
    arbeiter = Arbeiter(schlange, Bildquelle(http), ablage)

    @asynccontextmanager
    async def leben(_app: FastAPI):
        aufgabe = asyncio.create_task(arbeiter.laufen()) if arbeiten else None
        yield
        if aufgabe:
            aufgabe.cancel()
        await http.aclose()

    app = FastAPI(title="Bildholer", lifespan=leben)
    app.state.arbeiter = arbeiter

    @app.get("/api/v1/stand", response_model=Stand)
    async def stand() -> Stand:
        return arbeiter.stand()

    @app.get("/api/v1/regeln", response_model=Regeln)
    async def regeln() -> Regeln:
        return schlange.regeln()

    @app.put("/api/v1/regeln", response_model=Stand)
    async def regeln_setzen(eingabe: Regeln) -> Stand:
        schlange.regeln_setzen(eingabe)
        arbeiter.regeln_geaendert()
        return arbeiter.stand()

    @app.post("/api/v1/vormerken")
    async def vormerken(eingabe: Vormerkung) -> dict[str, int]:
        neu = schlange.vormerken(eingabe.quelle, eingabe.namen, eingabe.vorrang)
        if neu:
            arbeiter.wecken()
        return {"vorgemerkt": neu}

    @app.post("/api/v1/anhalten", response_model=Stand)
    async def anhalten() -> Stand:
        schlange.anhalten(True)
        return arbeiter.stand()

    @app.post("/api/v1/fortsetzen", response_model=Stand)
    async def fortsetzen() -> Stand:
        arbeiter.fortsetzen()
        return arbeiter.stand()

    return app
