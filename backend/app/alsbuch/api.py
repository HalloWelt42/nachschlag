"""Schnittstelle Als Buch (WIKI-45): eigene Bücher je Konto unter /api/v1/meins/buecher (Seite Als Buch, Schätzung,
Probekapitel, Bauen, Regal, Lesen, Nachbauen, Löschen) und die Vorlagen unter /api/v1/buchvorlagen (gemeinsam für die App;
eigene sind Dateien in der Kellerwolke). Nur für Menschen. Die Dateien zum Herunterladen liegen unter /api/v1/inhalt mit
dem Lesezugang der Sitzung (Cookie), weil ein Verweis zum Herunterladen keine Köpfe sendet."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from appkern.anmeldung import Konto
from appkern.app import Geruest
from appkern.auftraege.modelle import Auftrag

from ..modell.alsbuch import (
    Bestellung, Buchwahl, Leseansicht, Nachbau, Probe, Probewunsch, Regal, Schaetzung, Teilkatalog, Vorlage, Vorlagenliste,
    VorlageNeu,
)
from .dienst import Buecher
from .teile import KATALOG
from .umformung import REGELN_KURZ
from .vorlagen import VorlagenFehler, als_toml


def _fehlt(f: Exception) -> HTTPException:
    return HTTPException(status_code=404, detail=str(f) or "Gibt es nicht")


def _datei(name: str) -> str:
    """Content-Disposition mit Umlauten im Namen (RFC 6266) und einem einfachen Ersatz."""
    einfach = name.encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return f"attachment; filename=\"{einfach}\"; filename*=UTF-8''{quote(name)}"


def router(geruest: Geruest, buecher: Buecher) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["bücher"])

    # ----- Eigene Bücher ---------------------------------------------------------------------------------------------
    @r.get("/meins/buecher", response_model=Regal)
    async def regal(konto: Konto = geruest.mensch) -> Regal:
        """Eigene Bücher: was gerade entsteht (Aufträge mit Stufen je Kapitel) und die fertigen, neueste zuerst; hat sich
        ein Thema seit dem Bau geändert, steht es am Buch (Nachbauen)."""
        return await buecher.regal(konto.id)

    @r.get("/meins/buecher/thema/{thema}", response_model=Buchwahl)
    async def buchwahl(thema: str, konto: Konto = geruest.mensch) -> Buchwahl:
        """Was ein Thema für ein Buch hergibt: Bereiche als Kapitel, Notizen, gemerkte Stellen, Bilder, Steckbriefe,
        Artikel in anderer Sprache, Titelbilder, Modell und die zuletzt gebaute Bestellung."""
        try:
            return await buecher.buchwahl(konto.id, thema)
        except LookupError as f:
            raise _fehlt(f) from f

    @r.post("/meins/buecher/schaetzung", response_model=Schaetzung)
    async def schaetzung(b: Bestellung, konto: Konto = geruest.mensch) -> Schaetzung:
        """Dauer und Umfang vor dem Bauen, aus dem gemessenen Tempo des Modells (sonst der Hausmessung)."""
        try:
            return await buecher.schaetzen(konto.id, b)
        except LookupError as f:
            raise _fehlt(f) from f
        except ValueError as f:
            raise HTTPException(status_code=409, detail=str(f)) from f

    @r.post("/meins/buecher", response_model=Auftrag, status_code=201)
    async def bauen(b: Bestellung, konto: Konto = geruest.mensch) -> Auftrag:
        """Ein Buch bauen: ein Auftrag, jetzt oder heute Nacht (bis dahin zurückgestellt). Läuft schon einer für dieses
        Thema und diese Vorlage, kommt der zurück."""
        try:
            return await buecher.bestellen(konto.id, konto.name, b)
        except LookupError as f:
            raise _fehlt(f) from f
        except ValueError as f:
            raise HTTPException(status_code=409, detail=str(f)) from f

    @r.post("/meins/buecher/probe", response_model=Auftrag, status_code=201)
    async def probe_anstossen(w: Probewunsch, konto: Konto = geruest.mensch) -> Auftrag:
        """Ein Probekapitel: der Anfang eines Artikels nach der Vorlage, mit Prüfung; mit `neu` nur diese Absätze der
        letzten Probe neu schreiben lassen. Das Ergebnis liegt danach unter GET .../probe/{thema}."""
        try:
            return await buecher.probe_anstossen(konto.id, konto.name, w)
        except LookupError as f:
            raise _fehlt(f) from f
        except ValueError as f:
            raise HTTPException(status_code=409, detail=str(f)) from f

    @r.get("/meins/buecher/probe/{thema}", response_model=Probe | None)
    async def probe(thema: str, konto: Konto = geruest.mensch) -> Probe | None:
        """Das letzte Probekapitel des Themas: Original und Ergebnis mit Belegen und Prüfung; null, wenn es keins gibt."""
        return await buecher.probe(konto.id, thema)

    @r.get("/meins/buecher/{buch}/lesen", response_model=Leseansicht)
    async def lesen(buch: str, konto: Konto = geruest.mensch) -> Leseansicht:
        """Ein fertiges Buch zum Lesen in der App (Bilder aus den Büchern der Bibliothek)."""
        try:
            return await buecher.leseansicht(konto.id, buch)
        except LookupError as f:
            raise _fehlt(f) from f

    @r.post("/meins/buecher/{buch}/nachbauen", response_model=Auftrag, status_code=201)
    async def nachbauen(buch: str, n: Nachbau, konto: Konto = geruest.mensch) -> Auftrag:
        """Ein Buch mit dem heutigen Stand des Themas neu bauen; schon Umgeformtes kommt aus dem Zwischenspeicher, nur
        neue und geänderte Artikel gehen an das Modell."""
        try:
            return await buecher.nachbauen(konto.id, konto.name, buch, n.wann)
        except LookupError as f:
            raise _fehlt(f) from f
        except ValueError as f:
            raise HTTPException(status_code=409, detail=str(f)) from f

    @r.delete("/meins/buecher/{buch}", status_code=204)
    async def loeschen(buch: str, konto: Konto = geruest.mensch) -> Response:
        """Ein Buch aus dem Regal nehmen; seine Dateien gehen in den Papierkorb der Kellerwolke."""
        if not await buecher.loeschen(konto.id, buch):
            raise HTTPException(status_code=404, detail="Dieses Buch gibt es nicht")
        return Response(status_code=204)

    # ----- Vorlagen --------------------------------------------------------------------------------------------------
    @r.get("/buchvorlagen", response_model=Vorlagenliste)
    async def vorlagen(konto: Konto = geruest.mensch) -> Vorlagenliste:
        """Alle Vorlagen: die mitgelieferten und die eigenen aus der Kellerwolke (Ordner Vorlagen der App)."""
        return await buecher.vorlagen.liste()

    @r.get("/buchvorlagen/teile", response_model=Teilkatalog)
    async def teile(konto: Konto = geruest.mensch) -> Teilkatalog:
        """Die Teile, aus denen eine Vorlage ein Buch baut (Beschriftung, Herkunft, Platz), und die festen Regeln."""
        return Teilkatalog(teile=KATALOG, regeln=REGELN_KURZ)

    @r.get("/buchvorlagen/{kennung}", response_model=Vorlage)
    async def vorlage(kennung: str, konto: Konto = geruest.mensch) -> Vorlage:
        """Eine Vorlage."""
        try:
            v = await buecher.vorlagen.holen(kennung)
        except VorlagenFehler as f:
            raise HTTPException(status_code=503, detail=f.meldung) from f
        if v is None:
            raise HTTPException(status_code=404, detail="Diese Vorlage gibt es nicht")
        return v

    @r.put("/buchvorlagen/{kennung}", response_model=Vorlage)
    async def speichern(kennung: str, v: Vorlage, konto: Konto = geruest.mensch) -> Vorlage:
        """Eine eigene Vorlage speichern (neue Fassung ihrer Datei in der Kellerwolke); mitgelieferte sind fest."""
        if v.kennung != kennung:
            raise HTTPException(status_code=422, detail="Die Kennung im Weg und in der Vorlage unterscheiden sich")
        try:
            return await buecher.vorlagen.speichern(v)
        except VorlagenFehler as f:
            raise HTTPException(status_code=409, detail=f.meldung) from f

    @r.post("/buchvorlagen/{kennung}/kopie", response_model=Vorlage, status_code=201)
    async def kopieren(kennung: str, neu: VorlageNeu, konto: Konto = geruest.mensch) -> Vorlage:
        """Eine Vorlage als eigene kopieren (so entstehen eigene Vorlagen)."""
        try:
            return await buecher.vorlagen.kopieren(kennung, neu.titel)
        except LookupError as f:
            raise HTTPException(status_code=404, detail="Diese Vorlage gibt es nicht") from f
        except VorlagenFehler as f:
            raise HTTPException(status_code=409, detail=f.meldung) from f

    @r.delete("/buchvorlagen/{kennung}", status_code=204)
    async def vorlage_loeschen(kennung: str, konto: Konto = geruest.mensch) -> Response:
        """Eine eigene Vorlage in den Papierkorb der Kellerwolke."""
        try:
            if not await buecher.vorlagen.loeschen(kennung):
                raise HTTPException(status_code=404, detail="Diese Vorlage gibt es nicht")
        except VorlagenFehler as f:
            raise HTTPException(status_code=409, detail=f.meldung) from f
        return Response(status_code=204)

    return r


def inhalt_router(geruest: Geruest, buecher: Buecher) -> APIRouter:
    """Herunterladen unter /api/v1/inhalt (Cookie des Lesezugangs): Bücher als EPUB oder PDF, Vorlagen als TOML."""
    r = APIRouter(prefix="/api/v1/inhalt", tags=["bücher"])

    @r.get("/buecher/{buch}/{format}", response_class=StreamingResponse,
           responses={200: {"content": {"application/epub+zip": {}, "application/pdf": {}},
                            "description": "Die Datei aus der Kellerwolke"}})
    async def datei(buch: str, format: str, konto: Konto = geruest.lesen) -> StreamingResponse:
        """Ein Buch als EPUB oder PDF zum Herunterladen (aus der Kellerwolke)."""
        if format not in ("epub", "pdf"):
            raise HTTPException(status_code=404, detail="Format epub oder pdf")
        try:
            name, art, inhalt = await buecher.datei(konto.id, buch, format)
        except LookupError as f:
            raise _fehlt(f) from f
        return StreamingResponse(inhalt, media_type=art, headers={"Content-Disposition": _datei(name)})

    @r.get("/buchvorlagen/{kennung}", response_class=Response,
           responses={200: {"content": {"application/toml": {}}, "description": "Die Vorlage als TOML-Datei"}})
    async def vorlage_datei(kennung: str, konto: Konto = geruest.lesen) -> Response:
        """Eine Vorlage als Datei zum Weitergeben (TOML, wie sie in der Kellerwolke liegt)."""
        try:
            v = await buecher.vorlagen.holen(kennung)
        except VorlagenFehler as f:
            raise HTTPException(status_code=503, detail=f.meldung) from f
        if v is None:
            raise HTTPException(status_code=404, detail="Diese Vorlage gibt es nicht")
        return Response(als_toml(v), media_type="application/toml", headers={"Content-Disposition": _datei(f"{kennung}.toml")})

    return r
