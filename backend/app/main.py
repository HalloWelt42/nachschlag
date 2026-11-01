"""Nachschlag: liest jedes Buch der Bibliothek. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port 8711
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI

from appkern.app import Geruest
from appkern.einstellungen import Angebot, Option

from .api import router
from .artikel import Artikelleser
from .bibliothek import Bibliothek
from .einstellungen import AppEinstellungen
from .fassung import FASSUNG, WURZEL
from .suche import Suche
from .suche.bedeutung import FundusBedeutung


def app_bauen(daten: Path, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """`transport` nur für Tests (Kellerwolke, Leitstelle und Fundus nachgestellt)."""
    geruest = Geruest(name="Nachschlag", kennung="nachschlag", rolle="liest jedes Buch der Bibliothek", symbol="fa-book-open",
                      farbe="#08758b", fassung=FASSUNG, daten=daten, einstellungen=AppEinstellungen,
                      oberflaeche=WURZEL / "frontend" / "dist", transport=transport)
    e = lambda: geruest.einstellungen.stand  # noqa: E731

    bibliothek = Bibliothek(lambda: e().buecher_ordner)
    leser = Artikelleser(bibliothek)
    bedeutung = FundusBedeutung(lambda: geruest.verbund, lambda: e().fundus_adresse, lambda: e().fundus_sammlung,
                                lambda: e().fundus_vorsilbe)
    suche = Suche(bibliothek, bedeutung, lambda: e().bedeutung_warten_s, lambda: e().bedeutung_buch,
                  lambda buch, pfad: "")

    # Was das System kennt, ist kein Textfeld: die Bücher der Bibliothek als Auswahl, der Fundus aus dem Verzeichnis
    async def buecher() -> Angebot:
        stand = await bibliothek.stand()
        return Angebot(optionen=[Option(wert=b.kennung, titel=b.titel, hinweis=f"{b.kennung}, Stand {b.stand}")
                                 for b in stand.buecher], eigener_wert=False, stand=f"{len(stand.buecher)} Bücher")

    geruest.einstellungen.anbieten("bedeutung_buch", buecher)
    geruest.einstellungen.anbieten("fundus_adresse", geruest.verbund.angebot("Fundus", "fundus", lambda: e().fundus_adresse))
    geruest.verbund.anmelden("Fundus", lambda: e().fundus_adresse)

    app = geruest.fastapi()
    app.state.geruest = geruest
    app.state.bibliothek = bibliothek
    app.include_router(router(geruest, bibliothek, leser, suche))
    geruest.oberflaeche_ausliefern(app)
    return app


def daten_ordner() -> Path:
    """Wo die App ihre Daten hält: `NACHSCHLAG_DATEN` (im Container /app/daten), sonst daten/ im Repo."""
    return Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten")


app = app_bauen(daten_ordner())
