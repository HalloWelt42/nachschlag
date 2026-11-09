"""Die Originalseiten auf ihrer eigenen Herkunft (WIKI-85). Keine Anmeldung: der Schein im Weg gilt für genau ein Buch."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .herkunft import PRAEFIX, Originalherkunft
from .seite import bruecke_einsetzen, inhaltsregeln

BRUECKE = (Path(__file__).parent / "bruecke.js").read_bytes()
#: Inhalte eines Buchs ändern sich nie (neue Fassung = neue Datei, neue Kennung); die Adresse trägt den Schein des Tages
DAUERHAFT = "private, max-age=604800, immutable"


def router(bibliothek: Bibliothek, herkunft: Originalherkunft) -> APIRouter:
    r = APIRouter(prefix=PRAEFIX, tags=["originalansicht"])

    @r.get("/bruecke.js")
    async def bruecke() -> Response:
        """Die Brücke zwischen Originalseite und App (jede Seite fragt nach, ob sie neu ist)."""
        return Response(BRUECKE, media_type="text/javascript", headers={"Cache-Control": "no-cache"})

    @r.get("/{schein}/{buch}/{pfad:path}")
    async def seite(request: Request, schein: str, buch: str, pfad: str) -> Response:
        """Eine Seite oder Datei des Buchs, wie sie im Buch steht, Skripte eingeschlossen; Seiten bekommen die Brücke."""
        if not herkunft.gilt(schein, buch):
            raise HTTPException(status_code=403, detail="Diese Adresse gilt nicht mehr: die Seite in Nachschlag neu öffnen")
        try:
            e = await bibliothek.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise HTTPException(status_code=404, detail=str(f))
        seite = e.mime.startswith("text/html")
        return Response(bruecke_einsetzen(e.inhalt) if seite else e.inhalt, media_type=e.mime,
                        headers={"Cache-Control": DAUERHAFT, "Content-Security-Policy": inhaltsregeln(request.url)})

    return r
