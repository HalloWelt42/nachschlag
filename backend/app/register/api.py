"""Schnittstelle des Registers (WIKI-39): Schlagwörter, Fragen zu einem Schlagwort, Autoren, Seite eines Autors. Ohne
`buch` über alle Frage-Antwort-Bücher; Listen seitenweise mit `ab` und `anzahl`."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from appkern.app import Geruest

from ..bibliothek import BuchFehlt
from ..modell.register import AutorenSeite, AutorSeite, FragenSeite, SchlagwortSeite, Sortierung
from .dienst import Register

HOECHSTENS = 200


def router(geruest: Geruest, register: Register) -> APIRouter:
    r = APIRouter(prefix="/api/v1/register", tags=["register"], dependencies=[geruest.pflicht])

    def fehlt(f: BuchFehlt) -> HTTPException:
        return HTTPException(404, str(f))

    @r.get("/schlagwoerter", response_model=SchlagwortSeite)
    async def schlagwoerter(buch: str = "", anfang: str = "", ab: int = Query(0, ge=0),
                            anzahl: int = Query(50, ge=1, le=HOECHSTENS)) -> SchlagwortSeite:
        """Schlagwörter nach Zahl der Fragen; `anfang` filtert auf den Wortanfang."""
        try:
            return await register.schlagwoerter(buch, anfang, ab, anzahl)
        except BuchFehlt as f:
            raise fehlt(f)

    @r.get("/schlagwoerter/{wort}", response_model=FragenSeite)
    async def fragen(wort: str, buch: str = "", sortierung: Sortierung = "stimmen", ab: int = Query(0, ge=0),
                     anzahl: int = Query(30, ge=1, le=HOECHSTENS)) -> FragenSeite:
        """Die Fragen mit diesem Schlagwort, nach Stimmen oder die neuesten zuerst."""
        try:
            return await register.fragen(wort, buch, sortierung, ab, anzahl)
        except BuchFehlt as f:
            raise fehlt(f)

    @r.get("/autoren", response_model=AutorenSeite)
    async def autoren(buch: str = "", anfang: str = "", ab: int = Query(0, ge=0),
                      anzahl: int = Query(50, ge=1, le=HOECHSTENS)) -> AutorenSeite:
        """Autoren nach Zahl ihrer Beiträge; `anfang` filtert auf den Anfang des Namens."""
        try:
            return await register.autoren(buch, anfang, ab, anzahl)
        except BuchFehlt as f:
            raise fehlt(f)

    @r.get("/autoren/{buch}/{schluessel}", response_model=AutorSeite)
    async def autor(buch: str, schluessel: str, ab: int = Query(0, ge=0),
                    anzahl: int = Query(30, ge=1, le=HOECHSTENS)) -> AutorSeite:
        """Ein Autor mit Zahlen, Zeitraum und seinen Beiträgen (nach Stimmen)."""
        try:
            seite = await register.autor(buch, schluessel, ab, anzahl)
        except BuchFehlt as f:
            raise fehlt(f)
        if seite is None:
            raise HTTPException(404, "Diesen Autor kennt das Register nicht (oder die Quelle hat noch keinen eigenen Index)")
        return seite

    return r
