"""Schnittstelle des Bücherladers (WIKI-57): Stand mit Abos und Platz, das Verzeichnis seitenweise, Durchsicht anstoßen,
abonnieren und abbestellen, auf eine neue Fassung umschalten und zurück. Durchsicht und Laden laufen als Aufträge
(/api/v1/auftraege)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from appkern.app import Geruest
from appkern.auftraege import Auftrag

from ..modell.buecherlader import Katalogfilter, Laderstand, Verzeichnisseite
from .dienst import Buecherlader, LaderFehler


class Abonniert(BaseModel):
    anzahl: int = Field(description="so viele Bücher sind jetzt abonniert")


def router(geruest: Geruest, lader: Buecherlader) -> APIRouter:
    r = APIRouter(prefix="/api/v1/buecherlader", tags=["buecherlader"], dependencies=[geruest.pflicht])

    def konflikt(f: LaderFehler) -> HTTPException:
        return HTTPException(status_code=409, detail=str(f))

    @r.get("", response_model=Laderstand, summary="Stand des Bücherladers")
    async def stand() -> Laderstand:
        """Regeln, letzter und nächster Durchgang, Zahl der ungesehenen Neuigkeiten, Abos mit dem Vergleich zur eigenen
        Bibliothek und der Platz auf dem Datenträger der Bücher."""
        return await lader.stand()

    @r.get("/verzeichnis", response_model=Verzeichnisseite, summary="Bücher des Verzeichnisses")
    async def verzeichnis(f: Annotated[Katalogfilter, Query()], grenze: int = Query(50, ge=1, le=200),
                          versatz: int = Query(0, ge=0)) -> Verzeichnisseite:
        """Nur die Sprachen aus den Einstellungen, gefiltert (Sprache, Bereich, Ausgabe, Größe, Stand zur eigenen
        Bibliothek, neu, abonniert); Neues zuerst, sonst nach der gewählten Sortierung."""
        return await lader.verzeichnis(f, grenze=grenze, versatz=versatz)

    @r.post("/durchsicht", response_model=Auftrag, summary="Verzeichnis jetzt durchsehen")
    async def durchsehen(von: str = Depends(geruest.wer)) -> Auftrag:
        """Stößt eine Durchsicht an (läuft schon eine, kommt diese zurück)."""
        try:
            return await lader.durchsehen(von)
        except LaderFehler as f:
            raise konflikt(f)

    @r.post("/gesehen", status_code=204, summary="Neuigkeiten als gesehen merken")
    async def gesehen() -> None:
        await lader.gesehen()

    @r.put("/abo/{stamm}", status_code=204, summary="Buch abonnieren")
    async def abonnieren(stamm: str, von: str = Depends(geruest.wer)) -> None:
        """Lädt die jüngste Fassung, wenn sie fehlt, und künftig jede neuere."""
        try:
            await lader.abonnieren(stamm, von)
        except LookupError as f:
            raise HTTPException(status_code=404, detail=str(f))

    @r.delete("/abo/{stamm}", status_code=204, summary="Abo beenden")
    async def abbestellen(stamm: str) -> None:
        """Lädt es gerade, wird das abgebrochen. Die Bücher in der Bibliothek bleiben."""
        await lader.abbestellen(stamm)

    @r.post("/abo/bestand", response_model=Abonniert, summary="Alle eigenen Bücher abonnieren")
    async def bestand(von: str = Depends(geruest.wer)) -> Abonniert:
        """Jedes Buch der Bibliothek wird abonniert; neuere Fassungen laden danach von selbst."""
        return Abonniert(anzahl=await lader.bestand_abonnieren(von))

    @r.post("/umschalten/{stamm}", status_code=204, summary="Auf die neue Fassung umschalten")
    async def umschalten(stamm: str) -> None:
        """Die geladene, geprüfte Fassung wird aktiv; die vorige bleibt als Rückfall bis zum Ende der Frist."""
        try:
            await lader.umschalten(stamm)
        except LaderFehler as f:
            raise konflikt(f)

    @r.post("/zurueck/{stamm}", status_code=204, summary="Zurück auf die vorige Fassung")
    async def zurueck(stamm: str) -> None:
        """Die vorige Fassung wird wieder aktiv, die neue wartet wieder aufs Umschalten."""
        try:
            await lader.zurueck(stamm)
        except LaderFehler as f:
            raise konflikt(f)

    return r
