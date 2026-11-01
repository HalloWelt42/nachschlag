"""Eigene Stimmen fürs Vorlesen (WIKI-43): sie liegen in der Kellerwolke und gehören der Vertonung; dort steht auch, wer
sie nutzen darf (Einstellung "Private Stimmen für": `nachschlag` gibt alle frei, `nachschlag:<Kennung>` genau eine).
Nachschlag fragt die Vertonung mit seinem App-Schlüssel nur nach Probe, Text und Sprache der Stimme; gesprochen wird
über den Klondienst der Leitstelle (sprechdienst.py). Muster wie die App Vorlesen.

Die Probe wird einmal geholt und eine Weile gemerkt, damit der erste Satz schnell kommt; danach fragt Nachschlag wieder,
so gilt eine zurückgenommene Freigabe bald auch hier."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from appkern.app import Geruest
from appkern.verbund import ABFRAGE, VerbundFehler

#: so lange gilt eine geholte Probe samt Freigabe
REFERENZ_GILT_S = 1800
#: so beginnt der Wert einer eigenen Stimme in der Einstellung (sonst ist es eine Stimme aus dem Katalog)
PRIVAT = "privat:"


class NichtFreigegeben(Exception):
    """Die Stimme gibt es nicht, oder die Vertonung gibt sie Nachschlag nicht frei; `meldung` in Worten."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


@dataclass(frozen=True)
class Eigene:
    id: str
    name: str


@dataclass(frozen=True)
class Referenz:
    id: str
    ton: bytes             # die Probe, wie die Vertonung sie hält (WAV)
    text: str              # was in der Probe gesprochen wird (leer: unbekannt)
    sprache: str           # Sprache der Probe, kurz (de, en ...)


class Stimmenquelle:
    def __init__(self, geruest: Geruest, adresse: Callable[[], str], uhr: Callable[[], float] = time.monotonic) -> None:
        self.g = geruest
        self._adresse = adresse
        self._uhr = uhr
        self._gemerkt: dict[str, tuple[float, Referenz]] = {}

    def adresse(self) -> str:
        return self._adresse().strip().rstrip("/")

    async def eigene(self) -> list[Eigene]:
        """Die eigenen Stimmen, die die Vertonung Nachschlag freigibt (leer, wenn keine oder keine Vertonung)."""
        if not self.adresse():
            return []
        try:
            antwort = await self.g.verbund.anfrage("GET", self.adresse(), "/api/v1/stimmen", timeout=ABFRAGE,
                                                   params={"bereich": "privat"})
        except VerbundFehler as f:
            if f.status in (401, 403):
                return []                       # Nachschlag steht nicht auf der Erlaubnisliste: keine eigenen Stimmen
            raise
        return [Eigene(id=str(s["id"]), name=str(s["name"])) for s in antwort.json() if s.get("bereich") == "privat"]

    async def referenz(self, stimme_id: str) -> Referenz:
        """Probe, Text und Sprache einer freigegebenen eigenen Stimme; einmal geholt, eine Weile gemerkt."""
        gemerkt = self._gemerkt.get(stimme_id)
        if gemerkt and self._uhr() - gemerkt[0] < REFERENZ_GILT_S:
            return gemerkt[1]
        if not self.adresse():
            raise NichtFreigegeben("Eigene Stimmen gibt es erst mit der Adresse der Vertonung (Einstellungen, Vorlesen)")
        try:
            s = (await self.g.verbund.anfrage("GET", self.adresse(), f"/api/v1/stimmen/{stimme_id}", timeout=ABFRAGE)).json()
            if s.get("bereich") != "privat":
                raise NichtFreigegeben("Das ist keine eigene Stimme")
            ton = (await self.g.verbund.anfrage("GET", self.adresse(), f"/api/v1/inhalt/stimmen/{stimme_id}/probe")).content
        except VerbundFehler as f:
            self._gemerkt.pop(stimme_id, None)
            if f.status in (401, 403, 404, 422):
                raise NichtFreigegeben("Diese Stimme gibt die Vertonung für Nachschlag nicht frei (Vertonung, Einstellungen, "
                                       "Stimmen, Private Stimmen für)") from f
            raise
        angaben = s.get("angaben") or {}
        r = Referenz(id=stimme_id, ton=ton, text=str(angaben.get("referenztext") or ""), sprache=str(angaben.get("sprache") or "de"))
        self._gemerkt[stimme_id] = (self._uhr(), r)
        return r
