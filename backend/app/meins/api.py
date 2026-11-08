"""Schnittstelle Meins unter /api/v1/meins: nur für Menschen (je Konto), nie für andere Apps."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Response, UploadFile
from fastapi.responses import StreamingResponse

from appkern.anmeldung import Konto
from appkern.app import Geruest

from ..modell.meins import (Beispiel, BeispielAenderung, BeispielNeu, Bewertung, BewertungNeu, Lesestand, Merkeintrag, Merken, Notiz, NotizAenderung,
                            NotizNeu, Suchmeldung, Verlaufseintrag, Vorliebe)
from ..markdownablage import Markdownablage, MarkdownFehler
from ..modell.meins import Markdownstand
from .bilder import HOECHSTENS_BYTES, BildFehler, Notizbilder
from .speicher import Meins


def router(geruest: Geruest, meins: Meins, bilder: Notizbilder, markdown: Markdownablage) -> APIRouter:
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

    @r.post("/notizen/markdown", response_model=Markdownstand)
    async def notizen_als_markdown(konto: Konto = geruest.mensch) -> Markdownstand:
        """Alle Notizen als Markdown in die Ablage (WIKI-23; Kellerwolke oder Datenordner): je Artikel eine Datei unter
        Notizen/<Quelle>/."""
        try:
            dateien, ordner = await markdown.alle_ablegen(konto.id)
        except MarkdownFehler as f:
            raise HTTPException(status_code=503, detail=f.meldung) from f
        return Markdownstand(dateien=dateien, ordner=ordner)

    @r.post("/notizen", response_model=Notiz)
    async def notieren(eingabe: NotizNeu, aufgaben: BackgroundTasks, konto: Konto = geruest.mensch) -> Notiz:
        """Notiz am ganzen Artikel (ohne Zitat) oder an einer Stelle (mit Zitat); ohne Text eine Markierung."""
        notiz = await meins.notieren(konto.id, eingabe)
        aufgaben.add_task(markdown.nach_aenderung, konto.id, notiz)
        return notiz

    @r.patch("/notizen/{kennung}", response_model=Notiz)
    async def notiz_aendern(kennung: str, aenderung: NotizAenderung, aufgaben: BackgroundTasks,
                            konto: Konto = geruest.mensch) -> Notiz:
        notiz = await meins.notiz_aendern(konto.id, kennung, aenderung)
        if not notiz:
            raise HTTPException(status_code=404, detail="Diese Notiz gibt es nicht")
        aufgaben.add_task(markdown.nach_aenderung, konto.id, notiz)
        return notiz

    @r.delete("/notizen/{kennung}", status_code=204)
    async def notiz_loeschen(kennung: str, aufgaben: BackgroundTasks, konto: Konto = geruest.mensch) -> Response:
        notiz = await meins.notiz(konto.id, kennung)
        if notiz is None or not await meins.notiz_loeschen(konto.id, kennung):
            raise HTTPException(status_code=404, detail="Diese Notiz gibt es nicht")
        await bilder.alle_entfernen(notiz)
        aufgaben.add_task(markdown.nach_aenderung, konto.id, notiz)
        return Response(status_code=204)

    @r.post("/notizen/{kennung}/bilder", response_model=Notiz)
    async def bild_anfuegen(kennung: str, datei: UploadFile, konto: Konto = geruest.mensch) -> Notiz:
        """Ein Bild an die Notiz (WIKI-51): aus der Zwischenablage oder einer Datei; PNG, JPEG, GIF oder WebP."""
        try:
            return await bilder.anfuegen(konto.id, kennung, datei.filename or "", await datei.read(HOECHSTENS_BYTES + 1))
        except BildFehler as f:
            raise HTTPException(status_code=f.status, detail=f.meldung) from f

    @r.delete("/notizen/{kennung}/bilder/{bild_id}", status_code=204)
    async def bild_entfernen(kennung: str, bild_id: str, konto: Konto = geruest.mensch) -> Response:
        """Das Bild von der Notiz; die Datei geht aus der Ablage (in der Kellerwolke: in den Papierkorb)."""
        try:
            await bilder.entfernen(konto.id, kennung, bild_id)
        except BildFehler as f:
            raise HTTPException(status_code=f.status, detail=f.meldung) from f
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

    @r.get("/bewertungen", response_model=list[Bewertung])
    async def bewertungen(buch: str, konto: Konto = geruest.mensch) -> list[Bewertung]:
        """Die eigenen Bewertungen der Seiten eines Buchs (WIKI-71)."""
        return await meins.bewertungen(konto.id, buch)

    @r.put("/bewertungen", response_model=Bewertung | None)
    async def bewerten(eingabe: BewertungNeu, konto: Konto = geruest.mensch) -> Bewertung | None:
        """1 bis 5 Sterne für eine Seite; 0 nimmt die Bewertung weg."""
        return await meins.bewerten(konto.id, eingabe)

    @r.get("/verlauf", response_model=list[Verlaufseintrag])
    async def verlauf(anzahl: int = Query(50, ge=1, le=200), ab: int = Query(0, ge=0),
                      art: str = Query("", pattern="^(|artikel|suche)$"), konto: Konto = geruest.mensch) -> list[Verlaufseintrag]:
        """Gelesenes und Gesuchtes, jüngstes zuerst, seitenweise."""
        return await meins.verlauf(konto.id, anzahl, ab, art)

    @r.get("/verlauf/lesestand", response_model=Verlaufseintrag | None)
    async def lesestand_von(buch: str, pfad: str, konto: Konto = geruest.mensch) -> Verlaufseintrag | None:
        """Wo das Lesen einer Seite zuletzt stand (Abschnitt, Anteil); keiner: null."""
        return await meins.lesestand_von(konto.id, buch, pfad)

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


def inhalt_router(geruest: Geruest, bilder: Notizbilder) -> APIRouter:
    """Bilder an Notizen für <img>: unter /api/v1/inhalt mit dem Cookie des Lesezugangs (der Browser schickt beim Laden
    eines Bilds keinen Kopf)."""
    r = APIRouter(prefix="/api/v1/inhalt", tags=["meins"])

    @r.get("/notizbilder/{kennung}/{bild_id}", response_class=StreamingResponse)
    async def bild(kennung: str, bild_id: str, konto: Konto = geruest.lesen) -> StreamingResponse:
        """Das Bild aus der Ablage; ein Bild ändert sich nie (neues Bild, neue Kennung)."""
        try:
            b, inhalt = await bilder.lesen(konto.id, kennung, bild_id)
        except BildFehler as f:
            raise HTTPException(status_code=f.status, detail=f.meldung) from f
        return StreamingResponse(inhalt, media_type=b.typ, headers={"Cache-Control": "private, max-age=2592000, immutable"})

    return r
