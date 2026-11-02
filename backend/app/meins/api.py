"""Schnittstelle Meins unter /api/v1/meins: nur für Menschen (je Konto), nie für andere Apps."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response

from appkern.anmeldung import Konto
from appkern.app import Geruest

from ..modell.meins import (Beispiel, BeispielAenderung, BeispielNeu, Lesestand, Merkeintrag, Merken, Notiz, NotizAenderung,
                            NotizNeu, Suchmeldung, Verlaufseintrag, Vorliebe)
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

    @r.get("/notizen", response_model=list[Notiz])
    async def notizen(buch: str = "", pfad: str = "", konto: Konto = geruest.mensch) -> list[Notiz]:
        """Notizen und Markierungen, zuletzt geänderte zuerst; mit `buch` und `pfad` nur die eines Artikels."""
        return await meins.notizen(konto.id, buch, pfad)

    @r.post("/notizen", response_model=Notiz)
    async def notieren(eingabe: NotizNeu, konto: Konto = geruest.mensch) -> Notiz:
        """Notiz am ganzen Artikel (ohne Zitat) oder an einer Stelle (mit Zitat); ohne Text eine Markierung."""
        return await meins.notieren(konto.id, eingabe)

    @r.patch("/notizen/{kennung}", response_model=Notiz)
    async def notiz_aendern(kennung: str, aenderung: NotizAenderung, konto: Konto = geruest.mensch) -> Notiz:
        notiz = await meins.notiz_aendern(konto.id, kennung, aenderung)
        if not notiz:
            raise HTTPException(status_code=404, detail="Diese Notiz gibt es nicht")
        return notiz

    @r.delete("/notizen/{kennung}", status_code=204)
    async def notiz_loeschen(kennung: str, konto: Konto = geruest.mensch) -> Response:
        if not await meins.notiz_loeschen(konto.id, kennung):
            raise HTTPException(status_code=404, detail="Diese Notiz gibt es nicht")
        return Response(status_code=204)

    @r.get("/beispiele", response_model=list[Beispiel])
    async def beispiele(buch: str, pfad: str, konto: Konto = geruest.mensch) -> list[Beispiel]:
        """Die eigenen Beispiele eines Artikels (WIKI-48), in der Reihenfolge des Anlegens."""
        return await meins.beispiele(konto.id, buch, pfad)

    @r.post("/beispiele", response_model=Beispiel)
    async def beispiel_anlegen(eingabe: BeispielNeu, konto: Konto = geruest.mensch) -> Beispiel:
        """Die Kopie aus Ausprobieren als eigenes Beispiel am Artikel behalten; das Original bleibt unverändert."""
        return await meins.beispiel_anlegen(konto.id, eingabe)

    @r.patch("/beispiele/{kennung}", response_model=Beispiel)
    async def beispiel_aendern(kennung: str, aenderung: BeispielAenderung, konto: Konto = geruest.mensch) -> Beispiel:
        beispiel = await meins.beispiel_aendern(konto.id, kennung, aenderung)
        if not beispiel:
            raise HTTPException(status_code=404, detail="Dieses Beispiel gibt es nicht")
        return beispiel

    @r.delete("/beispiele/{kennung}", status_code=204)
    async def beispiel_loeschen(kennung: str, konto: Konto = geruest.mensch) -> Response:
        if not await meins.beispiel_loeschen(konto.id, kennung):
            raise HTTPException(status_code=404, detail="Dieses Beispiel gibt es nicht")
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
