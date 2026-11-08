"""Themen mit KI ordnen (WIKI-25): über die Leitstelle schlägt das Sprachmodell aus Titeln und Einleitungen der Artikel
Bereiche vor ("Bereiche vorschlagen") oder ordnet Artikel ohne Bereich den vorhandenen Bereichen zu ("Einsortieren
lassen"). Das Ergebnis des Auftrags ist immer ein Vorschlag; erst "Übernehmen" ändert das Thema. Kennungen, die es im
Thema nicht gibt, fallen aus der Antwort weg, jeder Artikel steht höchstens einmal darin."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from appkern.auftraege import Art, AuftragFehler, Auftraege, Herkunft, Kontext
from appkern.auftraege.modelle import Auftrag
from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, antwortform, gerade, json_lesen

from ..artikel import Artikelleser
from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.themen import Thema, Verschieben
from .speicher import Themen

ART = "themen_ordnen"
#: So viele Artikel gehen höchstens in eine Anfrage (Titel und Anfang der Einleitung)
HOECHSTENS_ARTIKEL = 80
EINLEITUNG_ZEICHEN = 220
HOECHSTENS_BEREICHE = 8

Was = Literal["bereiche", "einsortieren"]


class OrdnenEingabe(BaseModel):
    konto: str
    thema: str
    was: Was


class Vorschlagsbereich(BaseModel):
    titel: str
    bereich: str = Field("", description="Kennung eines vorhandenen Bereichs; leer: ein neuer Bereich")
    eintraege: list[str] = Field(description="Kennungen der Einträge, die dorthin gehören")


class Ordnungsvorschlag(BaseModel):
    was: Was
    begruendung: str = ""
    bereiche: list[Vorschlagsbereich]


def _schema(was: Was) -> dict[str, Any]:
    bereich = {"type": "object", "additionalProperties": False, "required": ["titel", "artikel"],
               "properties": {"titel": {"type": "string"}, "artikel": {"type": "array", "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False, "required": ["begruendung", "bereiche"],
            "properties": {"begruendung": {"type": "string"},
                           "bereiche": {"type": "array", "items": bereich, "maxItems": HOECHSTENS_BEREICHE}}}


ANWEISUNG = {
    "bereiche": ("Du ordnest eine Sammlung von Artikeln zu einem Thema. Bilde aus Titeln und Einleitungen 2 bis "
                 f"{HOECHSTENS_BEREICHE} Bereiche mit kurzen deutschen Überschriften (höchstens vier Wörter), die zusammen "
                 "alle Artikel abdecken. Jeder Artikel kommt in genau einen Bereich; nenne ihn mit seiner Kennung aus der "
                 "Liste. Antworte nur mit JSON: begruendung (ein Satz zur Gliederung, zuerst), bereiche (titel, artikel)."),
    "einsortieren": ("Du sortierst Artikel ohne Bereich in die vorhandenen Bereiche eines Themas ein. Verwende als titel "
                     "genau die Überschrift eines vorhandenen Bereichs. Einen Artikel, der in keinen Bereich passt, lässt "
                     "du weg. Nenne Artikel mit ihrer Kennung aus der Liste. Antworte nur mit JSON: begruendung (ein Satz, "
                     "zuerst), bereiche (titel, artikel)."),
}


def lesen(roh: dict[str, Any], was: Was, t: Thema, kandidaten: set[str]) -> Ordnungsvorschlag:
    """Die Antwort nachsichtig: unbekannte Kennungen und doppelte Artikel fallen weg, leere Bereiche auch; beim
    Einsortieren gelten nur vorhandene Bereiche (über die Überschrift)."""
    vorhanden = {b.titel.casefold(): b.id for b in t.bereiche}
    gesehen: set[str] = set()
    bereiche: list[Vorschlagsbereich] = []
    for b in roh.get("bereiche") or []:
        if not isinstance(b, dict):
            continue
        titel = gerade(str(b.get("titel", ""))).strip()[:120]
        kennung = vorhanden.get(titel.casefold(), "")
        if not titel or (was == "einsortieren" and not kennung):
            continue
        eintraege = [e for e in (str(x) for x in b.get("artikel") or []) if e in kandidaten and e not in gesehen]
        gesehen.update(eintraege)
        if eintraege:
            bereiche.append(Vorschlagsbereich(titel=titel, bereich=kennung, eintraege=eintraege))
    return Ordnungsvorschlag(was=was, begruendung=gerade(str(roh.get("begruendung", ""))).strip(), bereiche=bereiche)


class ThemenOrdner:
    def __init__(self, auftraege: Auftraege, themen: Themen, leser: Artikelleser, leitstelle: Callable[[], Leitstelle | None],
                 modell: Callable[[], str]) -> None:
        self._auftraege, self._themen, self._leser, self._ls, self._modell = auftraege, themen, leser, leitstelle, modell
        auftraege.anmelden(Art(name=ART, titel="Thema ordnen", arbeit=self._arbeit, eingabe=OrdnenEingabe, hoechstens=1,
                               herkunft=lambda e: Herkunft(titel="Zum Thema", ziel=f"themen/{e['thema']}")))

    async def starten(self, konto: str, thema: str, was: Was) -> Auftrag:
        t = await self._themen.thema(konto, thema)
        if t is None:
            raise LookupError("Dieses Thema gibt es nicht")
        titel = {"bereiche": "Bereiche vorschlagen", "einsortieren": "Einsortieren lassen"}[was]
        return await self._auftraege.einreihen(ART, OrdnenEingabe(konto=konto, thema=thema, was=was), titel=f"{titel}: {t.titel}")

    async def _zeile(self, e) -> str:
        try:
            einleitung = " ".join((await self._leser.lesen(e.buch, e.pfad)).einleitung.split())[:EINLEITUNG_ZEICHEN]
        except (BuchFehlt, EintragFehlt):
            einleitung = ""
        return f"{e.id} | {e.titel} | {einleitung}"

    async def _arbeit(self, k: Kontext) -> dict[str, Any]:
        e: OrdnenEingabe = k.eingabe
        t = await self._themen.thema(e.konto, e.thema)
        if t is None:
            raise AuftragFehler("Dieses Thema gibt es nicht mehr")
        kandidaten = [x for x in t.eintraege if e.was == "bereiche" or not x.bereich][:HOECHSTENS_ARTIKEL]
        if not kandidaten or (e.was == "einsortieren" and not t.bereiche):
            raise AuftragFehler("Nichts zu ordnen: " + ("keine Artikel ohne Bereich" if t.bereiche else "erst Bereiche anlegen"))
        ls = self._ls()
        if ls is None:
            raise AuftragFehler("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        await k.fortschritt(None, "Liest Titel und Einleitungen")
        zeilen = await asyncio.gather(*(self._zeile(x) for x in kandidaten))
        nutzer = (f"Thema: {t.titel}\n{t.beschreibung}\n"
                  + (f"Vorhandene Bereiche: {', '.join(b.titel for b in t.bereiche)}\n" if t.bereiche else "")
                  + "Artikel (Kennung | Titel | Einleitung):\n" + "\n".join(zeilen))
        await k.fortschritt(None, "Das Sprachmodell ordnet")
        try:
            antwort = await ls.chat([Nachricht.system(ANWEISUNG[e.was]), Nachricht.nutzer(nutzer)], modell=self._modell(),
                                    titel="Thema ordnen", response_format=antwortform("ordnung", _schema(e.was)), temperature=0.2)
            roh = json_lesen(antwort.text)
        except LeitstellenFehler as f:
            raise AuftragFehler(f"Die Leitstelle antwortet gerade nicht: {f}") from f
        except ValueError as f:
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück") from f
        if not isinstance(roh, dict):
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück")
        vorschlag = lesen(roh, e.was, t, {x.id for x in kandidaten})
        if not vorschlag.bereiche:
            raise AuftragFehler("Das Modell hat keinen brauchbaren Vorschlag gemacht; nochmal versuchen")
        return {"vorschlag": vorschlag.model_dump()}

    async def uebernehmen(self, konto: str, thema: str, v: Ordnungsvorschlag) -> Thema | None:
        """Den Vorschlag ins Thema: neue Bereiche anlegen, Artikel dorthin verschieben (ans Ende des Bereichs)."""
        t = await self._themen.thema(konto, thema)
        if t is None:
            return None
        vorhanden = {b.id for b in t.bereiche}
        for b in v.bereiche:
            ziel = b.bereich if b.bereich in vorhanden else ""
            if not ziel:
                neu = await self._themen.bereich_anlegen(konto, thema, b.titel)
                if neu is None:
                    continue
                ziel = neu.id
            for eintrag in b.eintraege:
                await self._themen.verschieben(konto, thema, eintrag, Verschieben(bereich=ziel, platz=100_000))
        return await self._themen.thema(konto, thema)
