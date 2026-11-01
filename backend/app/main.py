"""Nachschlag: liest jedes Buch der Bibliothek. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port 8711
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI

from appkern.app import Geruest

from .api import router
from .arten import arten
from .einstellungen import AppEinstellungen
from .fassung import FASSUNG, WURZEL


def app_bauen(daten: Path, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """`transport` nur für Tests (Kellerwolke und Leitstelle nachgestellt)."""
    geruest = Geruest(name="Nachschlag", kennung="nachschlag", rolle="liest jedes Buch der Bibliothek", symbol="fa-book-open", farbe="#08758b", fassung=FASSUNG,
                      daten=daten, einstellungen=AppEinstellungen, oberflaeche=WURZEL / "frontend" / "dist",
                      transport=transport)
    geruest.auftraege.anmelden(*arten(geruest))
    app = geruest.fastapi()
    app.state.geruest = geruest
    app.include_router(router(geruest))
    geruest.oberflaeche_ausliefern(app)
    return app


def daten_ordner() -> Path:
    """Wo die App ihre Daten hält: `NACHSCHLAG_DATEN` (im Container /app/daten), sonst daten/ im Repo."""
    return Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten")


app = app_bauen(daten_ordner())
