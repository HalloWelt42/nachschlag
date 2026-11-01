"""Schnittstelle Meins unter /api/v1/meins: nur für Menschen (je Konto), nie für andere Apps."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from appkern.anmeldung import Konto
from appkern.app import Geruest

from ..modell.meins import Lesestand, Merkeintrag, Merken, Suchmeldung, Verlaufseintrag, Vorliebe
from .speicher import Meins


def router(geruest: Geruest, meins: Meins) -> APIRouter:
    r = APIRouter(prefix="/api/v1/meins", tags=["meins"])

    @r.get("/merkzettel", response_model=list[Merkeintrag])
    async def merkzettel(konto: Konto = geruest.mensch) -> list[Merkeintrag]:
        """Gemerkte Seiten und Stellen, zuletzt gemerkte zuerst, mit gelesenem Anteil aus dem Verlauf."""
        return await meins.merkzettel(konto.id)

    @r.post("/merkzettel", response_model=Merkeintrag)
    async def merken(eingabe: Merken, konto: Konto = geruest.mensch) -> Merkeintrag:
        """Merken; dieselbe Seite (Stelle) zweimal bleibt ein Eintrag."""
        return await meins.merken(konto.id, eingabe)

    @r.delete("/merkzettel/{kennung}", status_code=204)
    async def vergessen(kennung: str, konto: Konto = geruest.mensch) -> Response:
        if not await meins.vergessen(konto.id, kennung):
            raise HTTPException(status_code=404, detail="Diesen Eintrag gibt es im Merkzettel nicht")
        return Response(status_code=204)

    @r.get("/verlauf", response_model=list[Verlaufseintrag])
    async def verlauf(anzahl: int = Query(50, ge=1, le=200), ab: int = Query(0, ge=0),
                      art: str = Query("", pattern="^(|artikel|suche)$"), konto: Konto = geruest.mensch) -> list[Verlaufseintrag]:
        """Gelesenes und Gesuchtes, jüngstes zuerst, seitenweise."""
        return await meins.verlauf(konto.id, anzahl, ab, art)

    @r.put("/verlauf/lesestand", status_code=204)
    async def lesestand(stand: Lesestand, konto: Konto = geruest.mensch) -> Response:
        await meins.lesestand(konto.id, stand)
        return Response(status_code=204)

    @r.post("/verlauf/suche", status_code=204)
    async def gesucht(meldung: Suchmeldung, konto: Konto = geruest.mensch) -> Response:
        await meins.gesucht(konto.id, meldung)
        return Response(status_code=204)

    @r.delete("/verlauf", status_code=204)
    async def verlauf_leeren(konto: Konto = geruest.mensch) -> Response:
        await meins.verlauf_leeren(konto.id)
        return Response(status_code=204)

    @r.get("/vorlieben", response_model=dict[str, str])
    async def vorlieben(konto: Konto = geruest.mensch) -> dict[str, str]:
        """Vorlieben des Kontos (etwa `fassung:<buch>`), auf allen Geräten gleich."""
        return await meins.vorlieben(konto.id)

    @r.put("/vorlieben/{schluessel}", status_code=204)
    async def vorliebe(schluessel: str, eingabe: Vorliebe, konto: Konto = geruest.mensch) -> Response:
        if len(schluessel) > 120:
            raise HTTPException(status_code=422, detail="Schlüssel zu lang")
        await meins.vorliebe(konto.id, schluessel, eingabe.wert)
        return Response(status_code=204)

    return r
