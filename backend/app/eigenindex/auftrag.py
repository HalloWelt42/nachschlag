"""Eigene Indizes als Aufträge (WIKI-17, docs/SUCHE.md Punkte 3, 4, 12 und 15). Gerechnet wird auf dem Mac: der
Index-Dienst dort holt sich den laufenden Auftrag hier ab, meldet seinen Fortschritt, lädt die fertige Datei in Teilen
hoch (fortsetzbar) und meldet sie fertig. Der Pi ruft den Mac nie an, und am Mac lauscht nichts im Netz; ist der Mac
weg (Ruhezustand, unterwegs), steht der Auftrag auf "wartet auf den Index-Dienst" und läuft weiter, sobald er sich meldet.

Ausgetauscht wird erst nach geprüfter Prüfsumme und in einem Schritt; bis dahin gilt der alte Index oder der Index der
ZIM-Datei. Welche Bücher einen eigenen Index bekommen, sagen die Einstellungen; der Begleiter reiht fehlende ein, kleine
Bücher zuerst, und prüft das stündlich erneut (neue Bücher, neue Fassungen)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from appkern.app.begleiter import Begleiter
from appkern.app.geruest import Verbindung
from appkern.auftraege import Art, AuftragFehler, Auftraege, Herkunft, Kontext
from appkern.auftraege.modelle import Phase

from ..bibliothek import Bibliothek
from ..modell.buch import Buch
from .ablage import Eigenindizes

logger = logging.getLogger("nachschlag.eigenindex")

ART = "eigenindex"
PHASEN = (Phase(schluessel="bauen", titel="Beim Index-Dienst bauen", symbol="gears"),
          Phase(schluessel="holen", titel="Übertragen", symbol="download"),
          Phase(schluessel="tauschen", titel="Prüfen und austauschen", symbol="check"))
#: So lange ohne Meldung des Mac, bis der Auftrag "wartet auf den Index-Dienst" zeigt
STILL_S = 90.0
PRUEFEN_S = 3600
STUECK = 1 << 20


class Macstand(BaseModel):
    """Was der Index-Dienst über den Bau meldet."""
    zustand: Literal["laeuft", "wartet_auf_netz"]
    erledigt: int = Field(0, ge=0)
    gesamt: int = Field(0, ge=0)
    seiten: int = Field(0, ge=0)
    uebernommen: int = Field(0, ge=0, description="davon unverändert aus dem Index der vorigen Fassung (WIKI-58)")
    meldung: str = Field("", max_length=300)


class Fertigmeldung(BaseModel):
    pruefsumme: str = Field(pattern=r"^[0-9a-f]{64}$")
    groesse: int = Field(ge=0)
    seiten: int = Field(ge=0)


class Abholung(BaseModel):
    """Der laufende Auftrag für den Index-Dienst."""
    auftrag: str
    buch: str
    sorte: Literal["volltext", "kategorien"] = Field("volltext", description="was der Mac bauen soll: den eigenen Index "
                                                                             "oder die Kategorien aus den Datenabzügen (WIKI-75)")
    da: int = Field(description="Bytes der Indexdatei, die schon hier sind (Übertragung setzt dort fort)")
    vorlage: str = Field("", description="Kennung des Index der vorigen Fassung desselben Buchs (WIKI-58): Unverändertes "
                                         "wird daraus übernommen; leer: keiner")


class IndexEingabe(BaseModel):
    buch: str


@dataclass
class _Kanal:
    """Was der Mac zu einem laufenden Auftrag gemeldet hat (lebt nur, solange die Arbeit des Auftrags läuft)."""
    buch: str
    zuletzt: float = 0.0
    stand: Macstand | None = None
    uebertragen: tuple[int, int] | None = None     # (da, gesamt)
    fertig: Fertigmeldung | None = None
    fehler: str = ""


def _zahl(wert: float, stellen: int = 0) -> str:
    """Zahl wie im Deutschen: Punkt zwischen den Tausendern, Komma vor den Stellen (12.345,6)."""
    return f"{wert:,.{stellen}f}".translate(str.maketrans(",.", ".,"))


def _dauer(sekunden: float) -> str:
    minuten = int(sekunden // 60)
    if minuten < 60:
        return "1 Minute" if minuten == 1 else f"{max(minuten, 1)} Minuten"
    stunden = minuten // 60
    return "1 Stunde" if stunden == 1 else f"{_zahl(stunden)} Stunden"


def _pruefsumme(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for stueck in iter(lambda: f.read(STUECK), b""):
            h.update(stueck)
    return h.hexdigest()


class AuftragWeg(LookupError):
    """Der Auftrag läuft hier nicht (mehr): abgebrochen, fertig oder nie da."""


class FalscheStelle(ValueError):
    """Ein Stück setzt nicht dort an, wo die Datei hier endet; `da` sagt, wo es weitergeht."""

    def __init__(self, da: int) -> None:
        super().__init__(f"Hier sind {da} Bytes; weiter ab dort")
        self.da = da


class Indexauftraege(Begleiter):
    def __init__(self, ablage: Eigenindizes, bibliothek: Bibliothek, auftraege: Auftraege, schluessel: Callable[[], str],
                 arten: Callable[[], list[str]], hoechstens_gb: Callable[[], float] = lambda: float("inf"), *,
                 takt_s: float = 2.0, still_s: float = STILL_S, nutzbare: Callable[[], Awaitable[list[Buch]]] | None = None,
                 sorte: Literal["volltext", "kategorien"] = "volltext", art: str = ART, titel: str = "Eigener Index",
                 passt: Callable[[Buch], bool] = lambda _b: True) -> None:
        """`nutzbare`: die Quellen, die einen eigenen Index bekommen dürfen (ohne archivierte, WIKI-46); sonst alle.
        `sorte`, `art` und `titel`: was gebaut wird (eigener Index oder Kategorien, WIKI-75), als welche Auftragsart und
        unter welchem Namen; `passt`: welche Bücher diese Sorte bekommen."""
        self._ablage, self._bib, self._auftraege = ablage, bibliothek, auftraege
        self._nutzbare, self._sorte, self._art, self._titel, self._passt = nutzbare, sorte, art, titel, passt
        self._schluessel, self._arten, self._takt, self._still = schluessel, arten, takt_s, still_s
        self._hoechstens_gb = hoechstens_gb
        self._kanaele: dict[str, _Kanal] = {}
        self._pruefung: asyncio.Task | None = None
        self._kontakt = 0.0                         # wann sich der Index-Dienst zuletzt gemeldet hat (monotonic)
        auftraege.anmelden(Art(name=art, titel=titel, arbeit=self._arbeit, eingabe=IndexEingabe, phasen=PHASEN,
                               fortsetzbar=True, nach_neustart="fortsetzen", hoechstens=1,   # der Mac baut einen nach dem anderen
                               herkunft=lambda e: Herkunft(titel="Zum Buch", ziel=f"lesen/{e['buch']}")))   # WIKI-50

    def schluessel_passt(self, kopf: str) -> bool | None:
        """Ob der Kopf Authorization den Schlüssel des Index-Dienstes trägt; None, wenn keiner eingestellt ist."""
        schluessel = self._schluessel()
        if not schluessel:
            return None
        return hmac.compare_digest(kopf.encode(), f"Bearer {schluessel}".encode())

    def gemeldet(self) -> None:
        """Der Index-Dienst hat sich mit gültigem Schlüssel gemeldet (jede Anfrage, auch ohne Auftrag)."""
        self._kontakt = time.monotonic()

    async def verbindung(self) -> Verbindung:
        """Für die Fußleiste: ob sich der Index-Dienst meldet. Er ruft an (im Leerlauf alle halbe Minute), der Pi nie."""
        name = "Index-Dienst"
        if not self._schluessel():
            return Verbindung(name=name, ok=False, meldung="nicht eingerichtet")
        if not self._kontakt:
            return Verbindung(name=name, ok=False, meldung="hat sich seit dem Start nicht gemeldet")
        vor = time.monotonic() - self._kontakt
        if vor > 2 * self._still:
            return Verbindung(name=name, ok=False, meldung=f"zuletzt vor {_dauer(vor)} (Rechner aus oder unterwegs)")
        return Verbindung(name=name, ok=True, meldung="meldet sich")

    def teil(self, buch: str) -> Path:
        ziel = self._ablage.pfad(buch)
        assert ziel is not None
        return ziel.with_name(ziel.name + ".teil")

    # ----- Begleiter: fehlende Indizes einreihen ---------------------------------------------------------------------

    async def starten(self) -> None:
        self._pruefung = asyncio.create_task(self._regelmaessig())

    async def stoppen(self) -> None:
        if self._pruefung:
            self._pruefung.cancel()

    async def _regelmaessig(self) -> None:
        while True:
            try:
                await self.fehlende_einreihen()
            except Exception:  # noqa: BLE001 - die Prüfung versucht es zur nächsten Stunde wieder
                logger.exception("Eigene Indizes: Prüfung gescheitert")
            await asyncio.sleep(PRUEFEN_S)

    async def fehlende_einreihen(self) -> list[str]:
        """Reiht je Buch der eingestellten Arten einen Auftrag ein, wenn es keinen geltenden Index hat und kein Auftrag
        dafür offen oder gescheitert ist (Gescheitertes wiederholt man auf der Seite Aufträge). Kleine Bücher zuerst,
        nur bis zur eingestellten Größe. Ohne Ordner oder Schlüssel nichts: dann könnte kein Index-Dienst die Aufträge
        abholen."""
        if not (self._schluessel() and self._ablage.pfad("-")):
            return []
        arten, grenze = set(self._arten()), self._hoechstens_gb() * 1e9
        quellen = await self._nutzbare() if self._nutzbare else (await self._bib.stand()).buecher
        buecher = sorted((b for b in quellen if b.art in arten and b.groesse <= grenze and self._passt(b)),
                         key=lambda b: b.groesse)
        eingereiht = []
        for b in buecher:
            hat = self._ablage.datei(b.kennung) and not (self._sorte == "volltext" and self._ablage.veraltet(b.kennung))
            if hat or await self._hat_auftrag(b.kennung):
                continue
            await self._auftraege.einreihen(self._art, IndexEingabe(buch=b.kennung), titel=f"{self._titel}: {b.titel}",
                                            stapel=b.kennung, von="Nachschlag")
            eingereiht.append(b.kennung)
        return eingereiht

    async def _hat_auftrag(self, kennung: str) -> bool:
        seite = await self._auftraege.liste(art=self._art, stapel=kennung, grenze=20)
        return any(a.zustand != "fertig" for a in seite.eintraege)

    # ----- Meldungen des Mac (Schnittstelle in api.py) ---------------------------------------------------------------

    def abholen(self) -> Abholung | None:
        for auftrag_id, kanal in self._kanaele.items():
            if kanal.fertig is None and not kanal.fehler:
                kanal.zuletzt = time.monotonic()
                teil = self.teil(kanal.buch)
                return Abholung(auftrag=auftrag_id, buch=kanal.buch, sorte=self._sorte,
                                da=teil.stat().st_size if teil.exists() else 0,
                                vorlage=self._vorlage_fuer(kanal.buch) if self._sorte == "volltext" else "")
        return None

    def kennt(self, auftrag_id: str) -> bool:
        """Ob der Auftrag zu diesen Aufträgen gehört und gerade läuft."""
        return auftrag_id in self._kanaele

    def _vorlage_fuer(self, buch: str) -> str:
        """Vorlage des Baus: der geltende Index des Buchs selbst, wenn er nur Ergänzungen braucht (WIKI-21, der Mac zieht
        sie darin nach), sonst der Index der vorigen Fassung (WIKI-58)."""
        return buch if self._ablage.veraltet(buch) else self._ablage.vorgaenger(buch)

    def vorlage(self, auftrag_id: str) -> Path | None:
        """Die Datei der Vorlage zum Buch eines laufenden Auftrags (für den Mac, der sie nicht hat)."""
        kennung = self._vorlage_fuer(self._kanal(auftrag_id).buch)
        return self._ablage.datei(kennung) if kennung else None

    def _kanal(self, auftrag_id: str) -> _Kanal:
        kanal = self._kanaele.get(auftrag_id)
        if kanal is None:
            raise AuftragWeg(auftrag_id)
        kanal.zuletzt = time.monotonic()
        return kanal

    def melden(self, auftrag_id: str, stand: Macstand) -> None:
        self._kanal(auftrag_id).stand = stand

    def scheitern(self, auftrag_id: str, meldung: str) -> None:
        self._kanal(auftrag_id).fehler = meldung or "ohne Angabe"

    def da(self, auftrag_id: str) -> int:
        teil = self.teil(self._kanal(auftrag_id).buch)
        return teil.stat().st_size if teil.exists() else 0

    async def anhaengen(self, auftrag_id: str, ab: int, gesamt: int, daten: bytes) -> int:
        """Hängt ein Stück an die Teildatei, wenn es genau dort ansetzt, wo sie endet (sonst `FalscheStelle`); gibt zurück,
        wie viel nun da ist. `ab` 0 beginnt von vorn (etwa nach einem neuen Bau auf dem Mac)."""
        kanal = self._kanal(auftrag_id)
        teil = self.teil(kanal.buch)
        da = teil.stat().st_size if teil.exists() else 0
        if ab not in (0, da):
            raise FalscheStelle(da)

        def schreiben() -> int:
            with open(teil, "r+b" if ab and teil.exists() else "wb") as f:
                f.seek(ab)
                f.truncate()
                f.write(daten)
                return f.tell()

        da = await asyncio.to_thread(schreiben)
        kanal.uebertragen = (da, gesamt)
        return da

    def fertig(self, auftrag_id: str, meldung: Fertigmeldung) -> None:
        self._kanal(auftrag_id).fertig = meldung

    # ----- Auftrag ---------------------------------------------------------------------------------------------------

    async def _arbeit(self, k: Kontext) -> dict[str, Any]:
        buch = k.eingabe.buch
        ziel = self._ablage.pfad(buch)
        if ziel is None:
            raise AuftragFehler("Kein Ordner für eigene Indizes eingestellt")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        kanal = self._kanaele.setdefault(k.auftrag_id, _Kanal(buch=buch))
        try:
            while kanal.fertig is None:
                if kanal.fehler:
                    raise AuftragFehler(f"Der Index-Dienst konnte den Index nicht bauen: {kanal.fehler}")
                await k.pruefen()
                await self._zeigen(k, kanal)
                await asyncio.sleep(self._takt)
            await k.fortschritt(None, "Prüfsumme wird verglichen", phase="tauschen")
            teil, soll = self.teil(buch), kanal.fertig
            passt = (teil.exists() and teil.stat().st_size == soll.groesse
                     and await asyncio.to_thread(_pruefsumme, teil) == soll.pruefsumme)
            if not passt:
                teil.unlink(missing_ok=True)
                raise AuftragFehler("Die übertragene Datei passt nicht zur Prüfsumme; Wiederholen überträgt sie neu")
            os.replace(teil, ziel)                          # in einem Schritt: Suchen sehen den alten oder den neuen
            await k.fortschritt(1.0, f"ausgetauscht, {_zahl(soll.seiten)} Seiten")
            return {"seiten": soll.seiten, "groesse": soll.groesse}
        finally:
            self._kanaele.pop(k.auftrag_id, None)

    async def _zeigen(self, k: Kontext, kanal: _Kanal) -> None:
        if not kanal.zuletzt or time.monotonic() - kanal.zuletzt > self._still:
            await k.fortschritt(None, "wartet auf den Index-Dienst", phase="holen" if kanal.uebertragen else "bauen")
        elif kanal.uebertragen:
            da, gesamt = kanal.uebertragen
            await k.fortschritt(da / gesamt if gesamt else None, f"{_zahl(da / 1e6, 1)} von {_zahl(gesamt / 1e6, 1)} MB",
                                phase="holen")
        elif kanal.stand:
            s = kanal.stand
            schritt = s.meldung or (f"{_zahl(s.erledigt)} von {_zahl(s.gesamt)} Einträgen, {_zahl(s.seiten)} Seiten"
                                    + (f", davon {_zahl(s.uebernommen)} aus der vorigen Fassung" if s.uebernommen else ""))
            await k.fortschritt(s.erledigt / s.gesamt if s.gesamt else None, schritt, phase="bauen")
        else:
            await k.fortschritt(None, "der Index-Dienst beginnt", phase="bauen")
