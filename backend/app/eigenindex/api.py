"""Schnittstelle für den Index-Dienst auf dem Mac (WIKI-17): Auftrag abholen, Fortschritt melden, die fertige Datei in
Stücken hochladen, fertig melden. Nur mit dem Schlüssel des Index-Dienstes (Einstellungen, Suche), nie mit einer
Anmeldung der Oberfläche; ohne eingestellten Schlüssel antwortet sie gar nicht."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .auftrag import Abholung, AuftragWeg, FalscheStelle, Fertigmeldung, Indexauftraege, Macstand

#: Größtes Stück je Anfrage (der Index-Dienst schickt kleinere)
STUECK_HOECHSTENS = 16 << 20


class Fehlermeldung(BaseModel):
    meldung: str = Field("", max_length=500)


class Uebertragen(BaseModel):
    da: int = Field(description="Bytes der Indexdatei, die hier sind")


@contextmanager
def _laufend(auftrag: str) -> Iterator[None]:
    """Ein Auftrag, der hier nicht (mehr) läuft, ist 410: der Index-Dienst lässt ihn dann fallen."""
    try:
        yield
    except AuftragWeg as f:
        raise HTTPException(410, f"Auftrag {auftrag} läuft nicht (mehr)") from f


def router(auftraege: Indexauftraege) -> APIRouter:
    def pruefen(authorization: str = Header("")) -> None:
        passt = auftraege.schluessel_passt(authorization)
        if passt is None:
            raise HTTPException(503, "Kein Schlüssel für den Index-Dienst eingestellt")
        if not passt:
            raise HTTPException(401, "Schlüssel fehlt oder stimmt nicht")
        auftraege.gemeldet()

    r = APIRouter(prefix="/api/v1/indexdienst", tags=["Index-Dienst"], dependencies=[Depends(pruefen)])

    @r.post("/abholen", response_model=Abholung, responses={204: {"description": "kein Auftrag offen"}})
    async def abholen():
        """Der laufende Auftrag, an dem der Index-Dienst arbeiten soll; 204, wenn keiner läuft."""
        a = auftraege.abholen()
        return a if a else Response(status_code=204)

    @r.put("/{auftrag}/stand", status_code=204)
    async def stand(auftrag: str, eingabe: Macstand) -> None:
        with _laufend(auftrag):
            auftraege.melden(auftrag, eingabe)

    @r.post("/{auftrag}/fehler", status_code=204)
    async def fehler(auftrag: str, eingabe: Fehlermeldung) -> None:
        with _laufend(auftrag):
            auftraege.scheitern(auftrag, eingabe.meldung)

    @r.get("/{auftrag}/datei", response_model=Uebertragen)
    async def datei(auftrag: str) -> Uebertragen:
        with _laufend(auftrag):
            return Uebertragen(da=auftraege.da(auftrag))

    @r.put("/{auftrag}/datei", response_model=Uebertragen)
    async def hochladen(auftrag: str, request: Request, ab: int = Query(ge=0), gesamt: int = Query(ge=0)) -> Uebertragen:
        """Ein Stück der Indexdatei ab Byte `ab`; setzt es nicht dort an, wo die Datei hier endet, kommt 409 mit dem
        Stand zurück, und der Index-Dienst schickt ab dort."""
        daten = await request.body()
        if len(daten) > STUECK_HOECHSTENS:
            raise HTTPException(413, "Stück zu groß")
        with _laufend(auftrag):
            try:
                return Uebertragen(da=await auftraege.anhaengen(auftrag, ab, gesamt, daten))
            except FalscheStelle as f:
                raise HTTPException(409, str(f)) from f

    @r.post("/{auftrag}/fertig", status_code=202)
    async def fertig(auftrag: str, eingabe: Fertigmeldung) -> None:
        """Die Datei ist vollständig hochgeladen; geprüft und ausgetauscht wird im Auftrag."""
        with _laufend(auftrag):
            auftraege.fertig(auftrag, eingabe)

    return r
