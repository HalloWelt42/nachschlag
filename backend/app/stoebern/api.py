"""Schnittstelle Stöbern unter /api/v1/stoebern. Der Zufall mit "noch nicht gelesen" fragt den Verlauf des Kontos."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from appkern.anmeldung import Konto
from appkern.app import Geruest

from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.stoebern import Buchseite, Fund, Pfadschritt
from .dienst import Stoebern


def router(geruest: Geruest, stoebern: Stoebern) -> APIRouter:
    r = APIRouter(prefix="/api/v1/stoebern", tags=["stoebern"])

    def fehlt(f: Exception) -> HTTPException:
        return HTTPException(status_code=404, detail=str(f) or "Gibt es nicht")

    @r.get("/zufall/{buch}", response_model=Fund)
    async def zufall(buch: str, mit_bild: bool = False, ungelesen: bool = False, konto: Konto = geruest.mensch) -> Fund:
        """Ein zufälliger Artikel mit Bild und erstem Absatz; auf Wunsch nur mit Bild, nur noch nicht gelesene."""
        try:
            return await stoebern.zufall(konto.id, buch, mit_bild, ungelesen)
        except (BuchFehlt, EintragFehlt) as f:
            raise fehlt(f)

    @r.get("/schritt/{buch}/{pfad:path}", response_model=Pfadschritt, dependencies=[geruest.mensch])
    async def schritt(buch: str, pfad: str) -> Pfadschritt:
        """Ein Artikel im Entdeckungspfad: Verweise im Text, Artikel, die ihn nennen, und Ähnliches nach Bedeutung."""
        try:
            return await stoebern.schritt(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise fehlt(f)

    @r.get("/fund/{buch}/{pfad:path}", response_model=Fund, dependencies=[geruest.mensch])
    async def fund(buch: str, pfad: str) -> Fund:
        """Titel, Bild und erster Absatz eines Artikels (Vorschau beim Blättern)."""
        try:
            return await stoebern.fund(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise fehlt(f)

    @r.get("/blaettern/{buch}", response_model=Buchseite, dependencies=[geruest.mensch])
    async def blaettern(buch: str, um: str = "", buchstabe: str = Query("", max_length=4), ab: int = -1, bis: int = -1,
                        anzahl: int = Query(13, ge=3, le=40)) -> Buchseite:
        """Titel in der Reihenfolge des Buchs (ohne Weiterleitungen): um einen Artikel, ab einem Buchstaben, ab einer
        Stelle (`ab`, Seite danach) oder vor einer Stelle (`bis`, Seite davor)."""
        try:
            return await stoebern.blaettern(buch, um=um, buchstabe=buchstabe, ab=ab, bis=bis, anzahl=anzahl)
        except (BuchFehlt, EintragFehlt, KeyError) as f:
            raise fehlt(f)

    return r
