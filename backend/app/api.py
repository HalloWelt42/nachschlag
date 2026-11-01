"""Eigene Endpunkte von Nachschlag (alle hinter der Anmeldung)."""

from fastapi import APIRouter

from appkern.app import Geruest
from appkern.auftraege import Auftrag

from .arten import ProbeEingabe


def router(geruest: Geruest) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["nachschlag"], dependencies=[geruest.pflicht])

    @r.post("/probe", response_model=Auftrag, status_code=201)
    async def probe(eingabe: ProbeEingabe) -> Auftrag:
        return await geruest.auftraege.einreihen("probe", eingabe, titel=f"Probeauftrag mit {eingabe.schritte} Schritten")

    return r
