"""Schnittstelle Themen unter /api/v1/meins/themen: nur für Menschen (je Konto), nie für andere Apps."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query, Response

from appkern.anmeldung import Konto
from appkern.app import Geruest

from ..modell.themen import (
    Ablehnung, Angebot, Bereich, BereichAenderung, BereichNeu, EintragNeu, Thema, ThemaAenderung, Themeneintrag, Themenkopf,
    ThemaNeu, Verschieben, Zuordnung,
)
from ..artikel import Artikelleser
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..meins import Meins
from ..suche import Suche
from ..zitieren import Form
from .literatur import Literaturliste, literaturliste
from .speicher import Themen

#: Wie viele Treffer der gespeicherten Suche geholt werden, um daraus neue Angebote zu ziehen
ANGEBOTE_AUS_TREFFERN = 40


T = TypeVar("T")


def _fehlt(was: str = "Dieses Thema gibt es nicht") -> HTTPException:
    return HTTPException(status_code=404, detail=was)


def _da(wert: T | None, was: str = "Dieses Thema gibt es nicht") -> T:
    """Der Wert, oder 404, wenn es ihn (für dieses Konto) nicht gibt."""
    if wert is None:
        raise _fehlt(was)
    return wert


def router(geruest: Geruest, themen: Themen, suche: Suche, bibliothek: Bibliothek, meins: Meins, leser: Artikelleser) -> APIRouter:
    """`bibliothek`: Namen und Angaben der Quellen (Angebote mit Bekanntem vergleichen, Literaturliste); `meins`: die
    Notizen mit ihren Belegen (Literaturliste); `leser`: Autor und Datum von Fragen (Literaturliste)."""
    name_von: Callable[[str], Awaitable[str]] = bibliothek.name_von
    r = APIRouter(prefix="/api/v1/meins/themen", tags=["themen"])

    @r.get("", response_model=list[Themenkopf])
    async def liste(konto: Konto = geruest.mensch) -> list[Themenkopf]:
        """Alle Themen des Kontos, ältestes zuerst, mit Zahlen und bis zu vier Bildern."""
        return await themen.liste(konto.id)

    @r.post("", response_model=Thema)
    async def anlegen(neu: ThemaNeu, konto: Konto = geruest.mensch) -> Thema:
        return await themen.anlegen(konto.id, neu)

    @r.get("/zuordnung", response_model=list[Zuordnung])
    async def zuordnung(konto: Konto = geruest.mensch) -> list[Zuordnung]:
        """Welcher Artikel in welchem Thema steht (für Artikelkopf und Notizen)."""
        return await themen.zuordnung(konto.id)

    @r.get("/{thema}", response_model=Thema)
    async def zeigen(thema: str, konto: Konto = geruest.mensch) -> Thema:
        """Ein Thema mit Bereichen und Artikeln (mit Lesestand und Zahl der Notizen)."""
        return _da(await themen.thema(konto.id, thema))

    @r.get("/{thema}/literatur", response_model=Literaturliste)
    async def literatur(thema: str, form: Form = "einfach", konto: Konto = geruest.mensch) -> Literaturliste:
        """Literaturliste des Themas (WIKI-31) in einer Zitierform (einfach, apa, din, bibtex): je Artikel die
        Quellenangabe, darunter die Belege, die der Recherchemodus mit den Notizen gesammelt hat."""
        t = _da(await themen.thema(konto.id, thema))
        buecher = {b.kennung: b for b in (await bibliothek.stand()).buecher}

        async def verfasser(buch: str, pfad: str) -> tuple[str, str]:
            try:
                a = await leser.lesen(buch, pfad)
            except (BuchFehlt, EintragFehlt):
                return "", ""
            return a.autor, a.datum

        return Literaturliste(form=form, text=await literaturliste(t, buecher, await meins.notizen(konto.id), form, verfasser))

    @r.patch("/{thema}", response_model=Thema)
    async def aendern(thema: str, aenderung: ThemaAenderung, konto: Konto = geruest.mensch) -> Thema:
        return _da(await themen.aendern(konto.id, thema, aenderung))

    @r.delete("/{thema}", status_code=204)
    async def loeschen(thema: str, konto: Konto = geruest.mensch) -> Response:
        if not await themen.loeschen(konto.id, thema):
            raise _fehlt()
        return Response(status_code=204)

    @r.post("/{thema}/bereiche", response_model=Bereich)
    async def bereich_anlegen(thema: str, neu: BereichNeu, konto: Konto = geruest.mensch) -> Bereich:
        return _da(await themen.bereich_anlegen(konto.id, thema, neu.titel))

    @r.patch("/{thema}/bereiche/{bereich}", status_code=204)
    async def bereich_aendern(thema: str, bereich: str, aenderung: BereichAenderung, konto: Konto = geruest.mensch) -> Response:
        """Umbenennen oder an eine andere Stelle unter den Bereichen setzen."""
        if not await themen.bereich_aendern(konto.id, thema, bereich, aenderung):
            raise _fehlt("Diesen Bereich gibt es nicht")
        return Response(status_code=204)

    @r.delete("/{thema}/bereiche/{bereich}", status_code=204)
    async def bereich_loeschen(thema: str, bereich: str, konto: Konto = geruest.mensch) -> Response:
        """Der Bereich geht; seine Artikel bleiben im Thema, ohne Bereich."""
        if not await themen.bereich_loeschen(konto.id, thema, bereich):
            raise _fehlt("Diesen Bereich gibt es nicht")
        return Response(status_code=204)

    @r.post("/{thema}/eintraege", response_model=Themeneintrag)
    async def eintragen(thema: str, neu: EintragNeu, konto: Konto = geruest.mensch) -> Themeneintrag:
        """Einen Artikel ins Thema legen (zweimal bleibt einer), auf Wunsch gleich in einen Bereich."""
        return _da(await themen.eintragen(konto.id, thema, neu), "Dieses Thema oder diesen Bereich gibt es nicht")

    @r.patch("/{thema}/eintraege/{eintrag}", status_code=204)
    async def verschieben(thema: str, eintrag: str, ziel: Verschieben, konto: Konto = geruest.mensch) -> Response:
        """In einen anderen Bereich oder an eine andere Stelle."""
        if not await themen.verschieben(konto.id, thema, eintrag, ziel):
            raise _fehlt("Diesen Eintrag oder Bereich gibt es nicht")
        return Response(status_code=204)

    @r.delete("/{thema}/eintraege/{eintrag}", status_code=204)
    async def austragen(thema: str, eintrag: str, konto: Konto = geruest.mensch) -> Response:
        if not await themen.austragen(konto.id, thema, eintrag):
            raise _fehlt("Diesen Eintrag gibt es nicht")
        return Response(status_code=204)

    @r.get("/{thema}/angebote", response_model=list[Angebot])
    async def angebote(thema: str, anzahl: int = Query(8, ge=1, le=30), konto: Konto = geruest.mensch) -> list[Angebot]:
        """Neue Treffer der gespeicherten Suche: nicht im Thema, nicht abgelehnt. Ohne Suche keine."""
        t = await themen.thema(konto.id, thema)
        if not t:
            raise _fehlt()
        if not t.regel:
            return []
        bekannt = await themen.bekannt(thema)
        ergebnis = await suche.suchen(t.regel, [t.regel_buch] if t.regel_buch else [], ANGEBOTE_AUS_TREFFERN)
        neu: list[Angebot] = []
        for tr in ergebnis.treffer:
            if (await name_von(tr.buch), tr.pfad) in bekannt or any(a.buch == tr.buch and a.pfad == tr.pfad for a in neu):
                continue
            neu.append(Angebot(buch=tr.buch, pfad=tr.pfad, titel=tr.titel, bild=tr.bild, auszug=tr.ausschnitt))
            if len(neu) == anzahl:
                break
        return neu

    @r.post("/{thema}/abgelehnt", status_code=204)
    async def ablehnen(thema: str, ablehnung: Ablehnung, konto: Konto = geruest.mensch) -> Response:
        """Ein Angebot passt nicht: es kommt nicht wieder."""
        if not await themen.ablehnen(konto.id, thema, ablehnung.buch, ablehnung.pfad):
            raise _fehlt()
        return Response(status_code=204)

    return r
