"""Bedeutungssuche als Anbindung (Port): Nachschlag rechnet keine Einbettungen selbst. Heute angebunden: Fundus, der die
Artikel eines Buchs nach Abschnitten eingebettet hält. Ohne Anbindung oder wenn sie nicht rechtzeitig antwortet, sucht
Nachschlag nur im Index."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote

from appkern.verbund import Verbund, VerbundFehler


class BedeutungFehlt(Exception):
    """Keine Bedeutungssuche: nicht angebunden, nicht erreichbar oder Fehler; `meldung` in Worten."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


@dataclass(frozen=True)
class Fundstelle:
    pfad: str            # Pfad im Buch
    titel: str
    abschnitt: str
    text: str
    passung: float       # 0 bis 1, größer passt besser


class Bedeutung(Protocol):
    def angebunden(self) -> bool: ...

    async def suchen(self, frage: str, anzahl: int) -> list[Fundstelle]: ...


class FundusBedeutung:
    """Fundus: POST /api/v1/suche mit der Sammlung des Buchs, nur nach Bedeutung. Treffer tragen ihre Herkunft als
    `<vorsilbe><Pfad im Buch>` (bei der deutschen Enzyklopädie `wikipedia:de/`), daraus der Pfad."""

    def __init__(self, verbund: Callable[[], Verbund], adresse: Callable[[], str], sammlung: Callable[[], str],
                 vorsilbe: Callable[[], str]) -> None:
        self._verbund, self._adresse, self._sammlung, self._vorsilbe = verbund, adresse, sammlung, vorsilbe

    def angebunden(self) -> bool:
        return bool(self._adresse().strip() and self._sammlung().strip())

    async def suchen(self, frage: str, anzahl: int) -> list[Fundstelle]:
        if not self.angebunden():
            raise BedeutungFehlt("keine Bedeutungssuche angebunden (Einstellungen, Suche)")
        try:
            antwort = await self._verbund().anfrage("POST", self._adresse(), "/api/v1/suche", json={
                "frage": frage, "sammlungen": [self._sammlung()], "anzahl": anzahl, "art": "bedeutung", "hybrid": False})
        except VerbundFehler as f:
            raise BedeutungFehlt(f"Bedeutungssuche antwortet nicht: {f.meldung}") from f
        daten = antwort.json()
        if daten.get("nur_woertlich") or daten.get("volltext"):
            raise BedeutungFehlt("Bedeutungssuche gerade nur wörtlich (Einbettung nicht erreichbar)")
        vorsilbe = self._vorsilbe()
        stellen: list[Fundstelle] = []
        for t in daten.get("treffer", []):
            herkunft = t.get("herkunft", "")
            if not herkunft.startswith(vorsilbe):
                continue
            teile = (t.get("titel") or "").split(" > ")
            stellen.append(Fundstelle(pfad=unquote(herkunft[len(vorsilbe):]), titel=teile[1] if len(teile) > 1 else teile[0],
                                      abschnitt=t.get("ueberschrift") or "", text=t.get("text") or "",
                                      passung=float(t.get("dicht") or t.get("rrf") or 0)))
        return stellen
