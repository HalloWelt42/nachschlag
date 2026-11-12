"""Schnittstelle des Übersetzens. Suche (WIKI-40): eine Frage übersetzen (gemerkt oder über die Leitstelle) und eine
Übersetzung korrigieren. Artikel (WIKI-8): Stand der Übersetzung eines Artikels und Anstoßen (ein Auftrag je Artikel).
Ohne Leitstelle ist das ein Zustand, kein Fehler: mit dem Grund; Suche und Lesen laufen dann ohne Übersetzung."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from appkern.app import Geruest

from ..bibliothek import BuchFehlt, EintragFehlt
from .artikel import Artikeluebersetzer, Artikelstand
from .dienst import Uebersetzer, Uebersetzung, UebersetzungFehlt
from .stelle import HOECHSTENS, Stellenstand, Stellenuebersetzer, Stellenuebersetzung, Ziel


class Stelle(BaseModel):
    text: str = Field(min_length=1, max_length=HOECHSTENS)
    ziel: Ziel = "de"


class Korrektur(BaseModel):
    frage: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=500)


def router(geruest: Geruest, uebersetzer: Uebersetzer, artikel: Artikeluebersetzer, stellen: Stellenuebersetzer) -> APIRouter:
    r = APIRouter(prefix="/api/v1/uebersetzung", tags=["uebersetzung"], dependencies=[geruest.pflicht])

    @r.get("", response_model=Uebersetzung)
    async def uebersetzen(frage: str = Query(min_length=1, max_length=500)) -> Uebersetzung:
        """Die Frage auf Englisch für die englischen Quellen."""
        try:
            return await uebersetzer.uebersetzen(frage)
        except UebersetzungFehlt as f:
            return Uebersetzung(frage=frage, von="keine", grund=str(f))

    @r.put("", response_model=Uebersetzung)
    async def korrigieren(eingabe: Korrektur) -> Uebersetzung:
        return await uebersetzer.korrigieren(eingabe.frage, eingabe.text)

    @r.get("/stelle", response_model=Stellenstand)
    async def stellenstand() -> Stellenstand:
        """Ob markierte Stellen übersetzbar sind (die Leiste zeigt "Übersetzen" nur dann)."""
        return stellen.stand()

    @r.post("/stelle", response_model=Stellenuebersetzung)
    async def stelle(eingabe: Stelle) -> Stellenuebersetzung:
        """Eine markierte Stelle übersetzen (WIKI-47); geht es gerade nicht, steht der Grund in `grund`."""
        return await stellen.uebersetzen(eingabe.text, eingabe.ziel)

    @r.get("/artikel/{buch}/{pfad:path}", response_model=Artikelstand)
    async def artikelstand(buch: str, pfad: str) -> Artikelstand:
        """Abgelegt (mit der Übersetzung), in Arbeit, gescheitert oder fehlend; ohne Leitstelle nicht möglich, für Bücher
        auf Deutsch nicht nötig."""
        try:
            return await artikel.stand(buch, pfad)
        except BuchFehlt as f:
            # eine Abfrage des Stands: ein fehlendes Buch ist ein Zustand mit Grund, kein Fehler (WIKI-97)
            return Artikelstand(zustand="nicht_moeglich", grund=str(f))

    @r.post("/artikel/{buch}/{pfad:path}", response_model=Artikelstand)
    async def artikel_uebersetzen(buch: str, pfad: str, wer: str = Depends(geruest.wer)) -> Artikelstand:
        """Die Übersetzung anstoßen: ein Auftrag je Artikel. Liegt sie schon ab oder ist sie in Arbeit, nur der Stand."""
        try:
            return await artikel.anstossen(buch, pfad, wer)
        except (BuchFehlt, EintragFehlt) as f:
            raise HTTPException(status_code=404, detail=str(f))

    return r
