"""Schnittstelle von Nachschlag unter /api/v1 (die Oberfläche nutzt nur diese Wege). Lesen von Büchern, Artikeln,
Vorschlägen und Suche braucht die Anmeldung; Medien und Originalseiten liegen unter /api/v1/inhalt und laden Bilder und
Rahmen mit dem Lesezugang der Sitzung (Cookie, gilt nur für diesen Pfad), weil `<img>` und `<iframe>` keine Köpfe senden."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from appkern.app import Geruest

from .artikel import Artikelleser
from .bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .modell.artikel import Artikel
from .modell.buch import Bibliotheksstand, Buch
from .modell.suche import Suchergebnis, Vorschlag
from .suche import Suche

#: Inhalte eines Buchs ändern sich nie (neue Fassung = neue Datei, neue Kennung)
DAUERHAFT = "private, max-age=604800, immutable"


def _fehlt(f: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(f))


def router(geruest: Geruest, bibliothek: Bibliothek, leser: Artikelleser, suche: Suche) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["nachschlag"])
    pflicht, lesen = [geruest.pflicht], [geruest.lesen]

    @r.get("/buecher", response_model=Bibliotheksstand, dependencies=pflicht)
    async def buecher() -> Bibliotheksstand:
        """Alle Bücher im Ordner mit ihren Angaben und Fähigkeiten; Dateien, die sich nicht öffnen ließen, mit Grund."""
        return await bibliothek.stand()

    @r.get("/buecher/{buch}", response_model=Buch, dependencies=pflicht)
    async def buch(buch: str) -> Buch:
        try:
            return await bibliothek.buch(buch)
        except BuchFehlt as f:
            raise _fehlt(f)

    @r.get("/artikel/{buch}/{pfad:path}", response_model=Artikel, dependencies=pflicht)
    async def artikel(buch: str, pfad: str) -> Artikel:
        """Ein Artikel, aufbereitet vom Baustein der Art des Buchs; Weiterleitungen sind aufgelöst (`anker` zeigt den
        Abschnitt). Ohne eigenes Lesedesign `darstellung: original` mit der Adresse der unveränderten Seite."""
        try:
            return await leser.lesen(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)

    @r.get("/zufall/{buch}", dependencies=pflicht)
    async def zufall(buch: str) -> dict[str, str]:
        try:
            return {"buch": buch, "pfad": await leser.zufall(buch)}
        except BuchFehlt as f:
            raise _fehlt(f)

    @r.get("/vorschlaege", response_model=list[Vorschlag], dependencies=pflicht)
    async def vorschlaege(anfang: str = Query(min_length=1, max_length=200), buecher: list[str] = Query(default=[]),
                          anzahl: int = Query(8, ge=1, le=30)) -> list[Vorschlag]:
        """Titel, die mit dem Getippten beginnen oder es enthalten (Titelindex der Bücher)."""
        return await suche.vorschlaege(anfang, buecher, anzahl)

    @r.get("/suche", response_model=Suchergebnis, dependencies=pflicht)
    async def suchen(frage: str = Query(min_length=1, max_length=400), buecher: list[str] = Query(default=[]),
                     wege: Literal["beide", "bedeutung", "index"] = "beide",
                     anzahl: int = Query(20, ge=1, le=50)) -> Suchergebnis:
        """Index immer, Bedeutung dazu, gemischt nach Rang; `nur_index` und `hinweis`, wenn die Bedeutungssuche nicht
        antwortete. Kein Fehler: auch dann kommt 200."""
        return await suche.suchen(frage, buecher, anzahl, wege)

    @r.get("/inhalt/medien/{buch}/{pfad:path}", dependencies=lesen)
    async def medien(buch: str, pfad: str) -> Response:
        """Bilder und andere Medien aus dem Buch, unverändert."""
        try:
            e = await bibliothek.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)
        return Response(e.inhalt, media_type=e.mime, headers={"Cache-Control": DAUERHAFT})

    @r.get("/inhalt/original/{buch}/{pfad:path}", dependencies=lesen)
    async def original(buch: str, pfad: str) -> Response:
        """Die Seite unverändert (Originalansicht), mit allen Dateien, die sie lädt. Abgeschirmt ohne Skripte: so behält
        sie die Herkunft der App (Stile und Bilder laden mit dem Lesezugang), kann aber nichts in der App tun."""
        try:
            e = await bibliothek.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)
        koepfe = {"Cache-Control": DAUERHAFT}
        if e.mime.startswith("text/html"):
            koepfe["Content-Security-Policy"] = "sandbox allow-same-origin allow-popups; script-src 'none'; frame-ancestors 'self'"
        return Response(e.inhalt, media_type=e.mime, headers=koepfe)

    return r
