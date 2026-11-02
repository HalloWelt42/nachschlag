"""Stapelarbeit je Sammlung (WIKI-44, geklärt im Gespräch 02.11.2026). Eine Sammlung ist ein Thema, ganz oder ein
Bereich daraus; nie ganze Quellen (Nutzer: "niemals die gesamten bestände aller daten, weil das niemals fertig würde").
Arbeiten: Übersetzen (die fremdsprachigen Artikel, über den Auftrag je Artikel), Vertonen (je Artikel eine Hördatei mit
Wiedergabeliste; Stimme und Format je Sammlung), Zusammenfassen (je Artikel und ein Überblick), Lernfragen (Karteikarten).
Ein Auftrag je Arbeit, jetzt oder nachts (Fenster in den Einstellungen; bis dahin zurückgestellt, sichtbar auf der Seite
Aufträge). Ergebnisse liegen in der Kellerwolke (Apps/Nachschlag/Sammlungen/<Thema>/) und am Thema in Nachschlag.

Gerechnet wird über die Leitstelle mit Priorität "hintergrund"; was andere gerade brauchen, geht vor."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from appkern.app.begleiter import Begleiter
from appkern.auftraege import Art, AuftragFehler, Auftraege, Kontext
from appkern.auftraege.modelle import Auftrag
from appkern.datenbank import Datenbank
from appkern.kellerwolke import Kellerwolke
from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, gerade, json_lesen

from ..artikel import Artikelleser
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..modell.themen import Thema, Themeneintrag
from ..themen import Themen
from ..uebersetzung.anweisungen import html_sprache
from ..uebersetzung.artikel import Artikeluebersetzer, braucht_uebersetzung
from ..vorlesen import NichtBereit, Sprechdienst
from .texte import HOECHSTENS_ZEICHEN, KARTENFORM, LERNFRAGEN, TEXTFORM, UEBERBLICK, ZUSAMMENFASSUNG, lesetext
from .ton import FORMATE, Format, zusammenfuegen

logger = logging.getLogger("nachschlag.sammlung")

ART = "sammlungsarbeit"
Arbeit = Literal["uebersetzen", "vertonen", "zusammenfassen", "lernfragen"]
TITEL: dict[str, str] = {"uebersetzen": "Übersetzen", "vertonen": "Vertonen", "zusammenfassen": "Zusammenfassen",
                         "lernfragen": "Lernfragen"}
ZONE = ZoneInfo("Europe/Berlin")
WECKER_S = 60
NACHSEHEN_S = 3.0

STUFEN = ["""
CREATE TABLE sammlungsergebnisse (
    konto   TEXT NOT NULL,
    thema   TEXT NOT NULL,
    arbeit  TEXT NOT NULL,
    inhalt  TEXT NOT NULL,
    ablage  TEXT NOT NULL,
    wann    TEXT NOT NULL,
    PRIMARY KEY (konto, thema, arbeit)
)
"""]


class SammlungsEingabe(BaseModel):
    konto: str
    thema: str
    arbeit: Arbeit
    bereich: str | None = Field(None, description="nur dieser Bereich des Themas; leer: das ganze Thema")
    wann: Literal["jetzt", "nachts"] = "jetzt"
    stimme: str = Field("", description="Vertonen: Stimme; leer: wie beim Vorlesen eingestellt")
    format: Format = "opus"


class Ergebnis(BaseModel):
    arbeit: Arbeit
    inhalt: str = Field(description="Markdown (Zusammenfassung, Lernfragen) oder die Liste der Hördateien")
    ablage: str = Field(description="wo es in der Kellerwolke liegt")
    wann: str


class Arbeitsstand(BaseModel):
    auftrag: str
    arbeit: Arbeit
    zustand: str
    anteil: float | None = None
    schritt: str = ""
    zurueckgestellt: str = ""


class Sammlungsstand(BaseModel):
    auftraege: list[Arbeitsstand]
    ergebnisse: list[Ergebnis]


def ordnername(titel: str) -> str:
    """Ein Thema als Ordnername: ohne Schrägstriche und Steuerzeichen, Leerraum zusammengefasst."""
    return re.sub(r"\s+", " ", re.sub(r"[/\\:\x00-\x1f]", " ", titel)).strip() or "Sammlung"


def nachts(jetzt: datetime, von: int, bis: int) -> bool:
    """Liegt die Stunde im Nachtfenster (über Mitternacht: 22 bis 7)?"""
    h = jetzt.hour
    return (von <= h or h < bis) if von > bis else (von <= h < bis)


class Sammlungen(Begleiter):
    def __init__(self, db: Datenbank, auftraege: Auftraege, themen: Themen, bibliothek: Bibliothek, leser: Artikelleser,
                 artikel: Artikeluebersetzer, sprechdienst_fuer: Callable[[str], Sprechdienst],
                 leitstelle: Callable[[], Leitstelle | None], modell: Callable[[], str],
                 kellerwolke: Callable[[], Kellerwolke | None], fenster: Callable[[], tuple[int, int]],
                 uhr: Callable[[], datetime] = lambda: datetime.now(ZONE)) -> None:
        self._db, self._auftraege, self._themen, self._bib, self._leser = db, auftraege, themen, bibliothek, leser
        self._artikel, self._sprechdienst_fuer, self._ls, self._modell = artikel, sprechdienst_fuer, leitstelle, modell
        self._kw, self._fenster, self._uhr = kellerwolke, fenster, uhr
        self._wecker: asyncio.Task | None = None
        auftraege.anmelden(Art(name=ART, titel="Sammlung bearbeiten", arbeit=self._arbeit, eingabe=SammlungsEingabe,
                               fortsetzbar=True, nach_neustart="fortsetzen", hoechstens=1))
        auftraege.zurueckstellen_wenn(self.zurueckstellen)

    async def starten(self) -> None:
        await self._db.einrichten("nachschlag_sammlungen", STUFEN)
        self._wecker = asyncio.create_task(self._wecken(), name="sammlungen-nacht")

    async def stoppen(self) -> None:
        if self._wecker:
            self._wecker.cancel()

    async def _wecken(self) -> None:
        """Beginnt die Nacht, sehen die Aufträge nach, ob Zurückgestelltes jetzt darf."""
        war = None
        while True:
            jetzt = nachts(self._uhr(), *self._fenster())
            if jetzt and war is False:
                self._auftraege.wecken()
            war = jetzt
            await asyncio.sleep(WECKER_S)

    def zurueckstellen(self, a: Auftrag) -> str:
        if a.art == ART and a.eingabe.get("wann") == "nachts":
            von, bis = self._fenster()
            if not nachts(self._uhr(), von, bis):
                return f"wartet auf die Nacht ({von} bis {bis} Uhr)"
        return ""

    # ----- Anstoßen und Stand ----------------------------------------------------------------------------------------

    @staticmethod
    def _stapel(konto: str, thema: str) -> str:
        return f"sammlung:{konto}:{thema}"

    async def anstossen(self, konto: str, wer: str, thema: str, arbeiten: list[Arbeit], bereich: str | None,
                        wann: Literal["jetzt", "nachts"], stimme: str, format: Format) -> Sammlungsstand:
        t = await self._themen.thema(konto, thema)
        if t is None:
            raise KeyError(thema)
        for arbeit in dict.fromkeys(arbeiten):
            eingabe = SammlungsEingabe(konto=konto, thema=thema, arbeit=arbeit, bereich=bereich or None, wann=wann,
                                       stimme=stimme, format=format)
            await self._auftraege.einreihen(ART, eingabe, titel=f"{TITEL[arbeit]}: {t.titel}" + (" (heute Nacht)" if wann == "nachts" else ""),
                                            stapel=self._stapel(konto, thema), von=wer)
        return await self.stand(konto, thema)

    async def stand(self, konto: str, thema: str) -> Sammlungsstand:
        seite = await self._auftraege.liste(stapel=self._stapel(konto, thema), zustand=("wartet", "laeuft", "fehler"), grenze=20)
        auftraege = [Arbeitsstand(auftrag=a.id, arbeit=a.eingabe.get("arbeit", "zusammenfassen"), zustand=a.zustand,
                                  anteil=a.fortschritt, schritt=a.fehler or a.schritt or "", zurueckgestellt=a.zurueckgestellt or "")
                     for a in seite.eintraege]
        zeilen = await self._db.zeilen("SELECT arbeit, inhalt, ablage, wann FROM sammlungsergebnisse WHERE konto = ? AND thema = ? "
                                       "ORDER BY arbeit", (konto, thema))
        return Sammlungsstand(auftraege=auftraege, ergebnisse=[Ergebnis(**dict(z)) for z in zeilen])

    # ----- Die Arbeit ------------------------------------------------------------------------------------------------

    async def _arbeit(self, k: Kontext) -> dict[str, Any]:
        e: SammlungsEingabe = k.eingabe
        t = await self._themen.thema(e.konto, e.thema)
        if t is None:
            raise AuftragFehler("Das Thema gibt es nicht mehr")
        eintraege = [x for x in sorted(t.eintraege, key=lambda x: (x.bereich, x.platz))
                     if x.buch and (e.bereich is None or x.bereich == e.bereich)]
        if not eintraege:
            raise AuftragFehler("In der Sammlung stehen keine Artikel aus vorhandenen Quellen")
        return await {"uebersetzen": self._uebersetzen, "vertonen": self._vertonen, "zusammenfassen": self._zusammenfassen,
                      "lernfragen": self._lernfragen}[e.arbeit](k, t, eintraege)

    async def _uebersetzen(self, k: Kontext, t: Thema, eintraege: list[Themeneintrag]) -> dict[str, Any]:
        """Die Artikel aus Quellen in anderer Sprache, je über den Auftrag des Artikels (abgelegt für alle)."""
        uebersetzt, gescheitert = 0, []
        for i, x in enumerate(eintraege):
            await k.pruefen()
            await k.fortschritt(i / len(eintraege), x.titel)
            try:
                buch = await self._bib.buch(x.buch)
                a = await self._leser.lesen(x.buch, x.pfad)
            except (BuchFehlt, EintragFehlt):
                continue
            if not braucht_uebersetzung(buch) or await self._artikel.abgelegt(x.buch, a.pfad):
                continue
            stand = await self._artikel.anstossen(x.buch, a.pfad, "Über Nacht")
            while stand.zustand == "laeuft":
                await asyncio.sleep(NACHSEHEN_S)
                await k.pruefen()
                stand = await self._artikel.stand(x.buch, a.pfad)
            if stand.zustand == "fertig":
                uebersetzt += 1
            else:
                gescheitert.append(f"{x.titel}: {stand.grund}")
        return {"uebersetzt": uebersetzt, "gescheitert": gescheitert}

    async def _text(self, x: Themeneintrag) -> tuple[str, str, str]:
        """Titel, Lesetext und dessen Sprache (de, en ...): die Übersetzung, wenn eine abgelegt ist."""
        buch = await self._bib.buch(x.buch)
        a = await self._leser.lesen(x.buch, x.pfad)
        ue = await self._artikel.abgelegt(x.buch, a.pfad)
        if ue is not None:
            return ue.titel, lesetext(ue.html), "de"
        return a.titel, lesetext(a.html), html_sprache(buch.sprache) or "de"

    async def _chat(self, system: str, nutzer: str, form: dict) -> dict[str, Any]:
        ls = self._ls()
        if ls is None:
            raise AuftragFehler("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        try:
            antwort = await ls.chat([Nachricht.system(system), Nachricht.nutzer(nutzer)], modell=self._modell() or None,
                                    titel="Sammlung bearbeiten", prioritaet="hintergrund", response_format=form, temperature=0.2)
            daten = json_lesen(antwort.text)
        except LeitstellenFehler as f:
            raise AuftragFehler(f"Die Leitstelle antwortet gerade nicht: {f}") from f
        except ValueError as f:
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück") from f
        if not isinstance(daten, dict):
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück")
        return daten

    async def _je_artikel(self, k: Kontext, eintraege: list[Themeneintrag], name: str,
                          machen: Callable[[Themeneintrag, str, str], Any]) -> dict[str, Any]:
        """Je Artikel ein Ergebnis (fortsetzbar: Fertiges steht im Zwischenstand)."""
        fertig: dict[str, Any] = dict(k.zwischenstand.get(name) or {})
        for i, x in enumerate(eintraege):
            await k.pruefen()
            if x.id in fertig:
                continue
            await k.fortschritt(i / len(eintraege), x.titel)
            try:
                titel, text, _ = await self._text(x)
            except (BuchFehlt, EintragFehlt):
                continue
            fertig[x.id] = {"titel": titel, "inhalt": await machen(x, titel, text[:HOECHSTENS_ZEICHEN])}
            await k.merken(**{name: fertig})
        return fertig

    async def _zusammenfassen(self, k: Kontext, t: Thema, eintraege: list[Themeneintrag]) -> dict[str, Any]:
        async def machen(x: Themeneintrag, titel: str, text: str) -> str:
            return gerade(str((await self._chat(ZUSAMMENFASSUNG.format(titel=titel), text, TEXTFORM)).get("text", ""))).strip()

        fertig = await self._je_artikel(k, eintraege, "zusammenfassungen", machen)
        await k.fortschritt(0.95, "Überblick")
        teile = [fertig[x.id] for x in eintraege if x.id in fertig]
        ueberblick = gerade(str((await self._chat(UEBERBLICK.format(thema=t.titel),
                                                  "\n\n".join(f"{p['titel']}: {p['inhalt']}" for p in teile), TEXTFORM)).get("text", ""))).strip()
        md = f"# {t.titel}: Zusammenfassung\n\n## Überblick\n\n{ueberblick}\n\n## Artikel\n\n"
        md += "".join(f"### {p['titel']}\n\n{p['inhalt']}\n\n" for p in teile)
        ablage = await self._ablegen(k, t, "Zusammenfassung.md", md.encode(), "text/markdown")
        await self._ergebnis(k, "zusammenfassen", md, ablage)
        return {"artikel": len(teile), "ablage": ablage}

    async def _lernfragen(self, k: Kontext, t: Thema, eintraege: list[Themeneintrag]) -> dict[str, Any]:
        async def machen(x: Themeneintrag, titel: str, text: str) -> list[dict[str, str]]:
            karten = (await self._chat(LERNFRAGEN.format(titel=titel), text, KARTENFORM)).get("karten") or []
            return [{"frage": gerade(str(c.get("frage", ""))).strip(), "antwort": gerade(str(c.get("antwort", ""))).strip()}
                    for c in karten if isinstance(c, dict) and c.get("frage") and c.get("antwort")]

        fertig = await self._je_artikel(k, eintraege, "karten", machen)
        teile = [fertig[x.id] for x in eintraege if x.id in fertig]
        md = f"# {t.titel}: Lernfragen\n\n" + "".join(
            f"## {p['titel']}\n\n" + "".join(f"**Frage:** {c['frage']}\n\n**Antwort:** {c['antwort']}\n\n" for c in p["inhalt"])
            for p in teile)
        ablage = await self._ablegen(k, t, "Lernfragen.md", md.encode(), "text/markdown")
        await self._ergebnis(k, "lernfragen", md, ablage)
        return {"karten": sum(len(p["inhalt"]) for p in teile), "ablage": ablage}

    async def _vertonen(self, k: Kontext, t: Thema, eintraege: list[Themeneintrag]) -> dict[str, Any]:
        """Je Artikel eine Hördatei (Titel, dann der Lesetext; Übersetzung, wenn abgelegt) und eine Wiedergabeliste."""
        e: SammlungsEingabe = k.eingabe
        endung, *_ = FORMATE[e.format]
        sprecher = self._sprechdienst_fuer(e.stimme)
        dateien: dict[str, str] = dict(k.zwischenstand.get("dateien") or {})
        for i, x in enumerate(eintraege):
            await k.pruefen()
            if x.id in dateien:
                continue
            try:
                titel, text, sprache = await self._text(x)
            except (BuchFehlt, EintragFehlt):
                continue
            await k.fortschritt(i / len(eintraege), f"{titel} wird gesprochen")
            saetze: list[bytes] = []
            try:
                async for zeile in sprecher.zeilen(f"{titel}.\n{text}", sprache):
                    z = json.loads(zeile)
                    if z["art"] == "satz":
                        saetze.append(base64.b64decode(z["ton"]))
                    elif z["art"] == "fehler":
                        raise AuftragFehler(z.get("meldung") or "Vorlesen brach ab")
                    if len(saetze) % 20 == 0:
                        await k.pruefen()
            except NichtBereit as f:
                raise AuftragFehler(f.meldung) from f
            name = f"{i + 1:02d} {ordnername(titel)}.{endung}"
            await self._ablegen(k, t, f"Hören/{name}", zusammenfuegen(saetze, e.format), f"audio/{'ogg' if e.format == 'opus' else 'mpeg'}")
            dateien[x.id] = name
            await k.merken(dateien=dateien)
        namen = [dateien[x.id] for x in eintraege if x.id in dateien]
        liste = "#EXTM3U\n" + "".join(f"{n}\n" for n in namen)
        ablage = await self._ablegen(k, t, "Hören/Thema anhören.m3u", liste.encode(), "audio/x-mpegurl")
        md = "\n".join(f"- {n}" for n in namen)
        await self._ergebnis(k, "vertonen", md, ablage.rsplit("/", 1)[0])
        return {"dateien": len(namen), "ablage": ablage}

    # ----- Ablage ------------------------------------------------------------------------------------------------------

    async def _ablegen(self, k: Kontext, t: Thema, name: str, inhalt: bytes, typ: str) -> str:
        """In die Kellerwolke unter Apps/<App>/Sammlungen/<Thema>/; eine vorhandene Datei bekommt eine neue Fassung."""
        kw = self._kw()
        if kw is None:
            raise AuftragFehler("Kellerwolke nicht eingerichtet (Einstellungen, Verbindungen)")
        pfad = f"{(await kw.ich()).zweig}/Sammlungen/{ordnername(t.titel)}/{name}"
        await kw.ordner(pfad.rsplit("/", 1)[0])
        alt = await kw.finden(pfad)
        await kw.schreiben(pfad, inhalt, stand=alt.etag if alt else None, inhaltstyp=typ)
        return pfad

    async def _ergebnis(self, k: Kontext, arbeit: str, inhalt: str, ablage: str) -> None:
        e: SammlungsEingabe = k.eingabe
        await self._db.ausfuehren(
            "INSERT INTO sammlungsergebnisse (konto, thema, arbeit, inhalt, ablage, wann) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(konto, thema, arbeit) DO UPDATE SET inhalt = excluded.inhalt, ablage = excluded.ablage, wann = excluded.wann",
            (e.konto, e.thema, arbeit, inhalt, ablage, datetime.now(timezone.utc).isoformat(timespec="seconds")))

