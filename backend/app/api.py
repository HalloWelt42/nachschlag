"""Schnittstelle von Nachschlag unter /api/v1 (die Oberfläche nutzt nur diese Wege). Lesen von Büchern, Artikeln,
Vorschlägen und Suche braucht die Anmeldung; Medien liegen unter /api/v1/inhalt und laden mit dem Lesezugang der Sitzung
(Cookie, gilt nur für diesen Pfad), weil `<img>` keine Köpfe sendet. Originalseiten laufen abgeschirmt mit einem Schein
im Weg (originalansicht, WIKI-85)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from appkern.app import Geruest

from .artikel import Artikelleser
from .bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from .bilder import Grossbilder
from .eigenindex.abfrage import rueckverweise
from .eigenindex.ablage import Eigenindizes
from .modell.artikel import Artikel, Nachbar, Rueckverweise
from .modell.buch import Bibliotheksstand, Buch
from .modell.suche import Suchergebnis, Suchregeln, Vorschlag
from .quellenarchiv import Quellenarchiv
from .suche import Suche

#: Inhalte eines Buchs ändern sich nie (neue Fassung = neue Datei, neue Kennung)
DAUERHAFT = "private, max-age=604800, immutable"


_HINTERGRUND: set[asyncio.Task] = set()


def _nebenbei(aufruf) -> None:
    """Läuft neben der Antwort her (die Antwort wartet nicht darauf); gehalten, bis es fertig ist."""
    aufgabe = asyncio.create_task(aufruf)
    _HINTERGRUND.add(aufgabe)
    aufgabe.add_done_callback(_HINTERGRUND.discard)


def _fehlt(f: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(f))


def router(geruest: Geruest, bibliothek: Bibliothek, leser: Artikelleser, suche: Suche, quellen: Quellenarchiv,
           suchregeln: Callable[[], Suchregeln] | None = None, eigen: Eigenindizes | None = None,
           grossbilder: Grossbilder | None = None) -> APIRouter:
    """`grossbilder`: große Bilder des Bildholers (WIKI-80); geöffnete Artikel merken ihre Bilder vor."""
    r = APIRouter(prefix="/api/v1", tags=["nachschlag"])
    pflicht, lesen = [geruest.pflicht], [geruest.lesen]

    @r.get("/buecher", response_model=Bibliotheksstand, dependencies=pflicht)
    async def buecher() -> Bibliotheksstand:
        """Alle Bücher im Ordner mit ihren Angaben, Fähigkeiten und dem Archivstand (WIKI-46); Dateien, die sich nicht
        öffnen ließen, mit Grund."""
        return await quellen.stand()

    @r.get("/buecher/{buch}", response_model=Buch, dependencies=pflicht)
    async def buch(buch: str) -> Buch:
        try:
            return await quellen.buch(buch)
        except BuchFehlt as f:
            raise _fehlt(f)

    @r.get("/artikel/{buch}/{pfad:path}", response_model=Artikel, dependencies=pflicht)
    async def artikel(buch: str, pfad: str) -> Artikel:
        """Ein Artikel, aufbereitet vom Baustein der Art des Buchs; Weiterleitungen sind aufgelöst (`anker` zeigt den
        Abschnitt). Ohne eigenes Lesedesign `darstellung: original` mit der Adresse der unveränderten Seite
        (Originalansicht mit Schein, WIKI-85)."""
        try:
            a = await leser.lesen(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)
        if grossbilder:
            _nebenbei(grossbilder.geoeffnet(a))
        return a

    @r.get("/zufall/{buch}", dependencies=pflicht)
    async def zufall(buch: str) -> dict[str, str]:
        try:
            return {"buch": buch, "pfad": await leser.zufall(buch)}
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)

    @r.get("/vorschlaege", response_model=list[Vorschlag], dependencies=pflicht)
    async def vorschlaege(anfang: str = Query(min_length=1, max_length=200), buecher: list[str] = Query(default=[]),
                          anzahl: int = Query(8, ge=1, le=30)) -> list[Vorschlag]:
        """Titel, die mit dem Getippten beginnen oder es enthalten (Titelindex der Bücher)."""
        return await suche.vorschlaege(anfang, buecher, anzahl)

    @r.get("/rueckverweise/{buch}", response_model=Rueckverweise, dependencies=pflicht)
    async def rueckverweise_von(buch: str, pfad: str, anzahl: int = Query(50, ge=1, le=500)) -> Rueckverweise:
        """Seiten desselben Buchs, die auf `pfad` verweisen ("verweist hierher"); nur mit einem eigenen Index, der die
        Verweise kennt, sonst `bekannt` falsch."""
        datei = eigen.datei(buch) if eigen else None
        r = await asyncio.to_thread(rueckverweise, datei, pfad, anzahl) if datei else None
        if r is None:
            return Rueckverweise(bekannt=False)
        return Rueckverweise(bekannt=True, gesamt=r[1], seiten=[Nachbar(pfad=x.pfad, titel=x.titel) for x in r[0]])

    @r.get("/suche/regeln", response_model=Suchregeln, dependencies=pflicht)
    async def regeln() -> Suchregeln:
        """Was die Oberfläche aus den Einstellungen der Suche braucht: Vorschläge beim Tippen, Treffer an der Stelle öffnen."""
        return suchregeln() if suchregeln else Suchregeln(vorschlaege="titel_stellen", an_der_stelle=True)

    @r.get("/suche", response_model=Suchergebnis, dependencies=pflicht)
    async def suchen(frage: str = Query(min_length=1, max_length=400), buecher: list[str] = Query(default=[]),
                     wege: Literal["beide", "bedeutung", "index"] = "beide",
                     anzahl: int = Query(20, ge=1, le=50),
                     nachliefern: bool = Query(False, description="nach `bedeutung_ausstehend`: länger auf die "
                                                                  "Bedeutungssuche warten (WIKI-98)")) -> Suchergebnis:
        """Index immer, Bedeutung dazu, gemischt nach Rang; `nur_index` und `hinweis`, wenn die Bedeutungssuche nicht
        antwortete, `bedeutung_ausstehend`, wenn sie noch läuft. Kein Fehler: auch dann kommt 200."""
        return await suche.suchen(frage, buecher, anzahl, wege, nachliefern)

    @r.get("/inhalt/medien/{buch}/{pfad:path}", dependencies=lesen)
    async def medien(buch: str, pfad: str, gross: bool = Query(False, description="das große Bild des Bildholers, wenn "
                                                                                      "er es schon hat (WIKI-80)")) -> Response:
        """Bilder und andere Medien aus dem Buch, unverändert; mit `gross` das große Bild, sonst das aus dem Buch."""
        if gross and grossbilder and (gefunden := grossbilder.finden(buch, pfad)):
            return FileResponse(gefunden[0], media_type=gefunden[1].mime, headers={"Cache-Control": DAUERHAFT})
        try:
            e = await bibliothek.eintrag(buch, pfad)
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)
        return Response(e.inhalt, media_type=e.mime, headers={"Cache-Control": DAUERHAFT})

    @r.get("/inhalt/symbol/{buch}", dependencies=lesen)
    async def symbol(buch: str) -> Response:
        """Das Symbol, das das Buch mitbringt (PNG, größte Fassung); 404, wenn es keins hat (WIKI-88). Die Kennung trägt
        den Stand, darum darf der Browser es dauerhaft behalten."""
        try:
            return Response(await bibliothek.symbol(buch), media_type="image/png", headers={"Cache-Control": DAUERHAFT})
        except (BuchFehlt, EintragFehlt) as f:
            raise _fehlt(f)

    return r
