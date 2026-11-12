"""Laufende Anfragen an die Bedeutungssuche (WIKI-98).

Die Suche wartet nur kurz auf die Bedeutungssuche (Einstellung `bedeutung_warten_s`), damit der Index nicht hinter ihr
steht. Antwortet sie nicht rechtzeitig, wird sie nicht abgebrochen: die Anfrage läuft weiter und bleibt eine Weile
hier liegen. Fragt die Seite mit `nachliefern` nach, wartet sie auf dieselbe Anfrage (nicht auf eine zweite) und
bekommt die Treffer, sobald sie da sind. Gemessen wird ab dem Start der Anfrage, so steht die echte Dauer in der
Antwort, auch wenn die Treffer erst mit der Nachfrage kommen."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from .bedeutung import Fundstelle

#: so lange bleibt eine Anfrage (laufend oder fertig) für die Nachfrage liegen
AUFBEWAHREN_S = 120.0


@dataclass
class Lauf:
    aufgabe: asyncio.Task[list[Fundstelle]]
    start: float = field(default_factory=time.perf_counter)
    ende: float | None = None

    @property
    def dauer_ms(self) -> int | None:
        return None if self.ende is None else int((self.ende - self.start) * 1000)


class Ausstehend(Exception):
    """Die Bedeutungssuche läuft noch; die Treffer lassen sich mit einer Nachfrage holen."""


class LaufendeBedeutung:
    def __init__(self, suchen: Callable[[str, int], Awaitable[list[Fundstelle]]],
                 aufbewahren_s: float = AUFBEWAHREN_S) -> None:
        self._suchen, self._aufbewahren_s = suchen, aufbewahren_s
        self._laeufe: dict[tuple[str, int], Lauf] = {}

    def _aufraeumen(self) -> None:
        jetzt = time.perf_counter()
        for schluessel, lauf in list(self._laeufe.items()):
            if jetzt - lauf.start > self._aufbewahren_s:
                if not lauf.aufgabe.done():
                    lauf.aufgabe.cancel()
                del self._laeufe[schluessel]

    def _lauf(self, frage: str, anzahl: int) -> Lauf:
        """Die laufende oder eben fertige Anfrage zu dieser Frage, sonst eine neue. Eine gescheiterte zählt nicht: die
        nächste Suche fragt neu."""
        self._aufraeumen()
        schluessel = (frage.strip().casefold(), anzahl)
        lauf = self._laeufe.get(schluessel)
        if lauf is not None and lauf.aufgabe.done() and (lauf.aufgabe.cancelled() or lauf.aufgabe.exception()):
            lauf = None
        if lauf is None:
            lauf = Lauf(asyncio.create_task(self._suchen(frage, anzahl), name="bedeutungssuche"))
            fertig = lauf

            def beenden(aufgabe: asyncio.Task[list[Fundstelle]]) -> None:
                fertig.ende = time.perf_counter()
                if not aufgabe.cancelled():
                    aufgabe.exception()           # abgeholt: sonst meldet asyncio eine nie gelesene Ausnahme

            lauf.aufgabe.add_done_callback(beenden)
            self._laeufe[schluessel] = lauf
        return lauf

    async def suchen(self, frage: str, anzahl: int, warten_s: float) -> tuple[list[Fundstelle], int | None]:
        """Treffer und Dauer der Anfrage in ms. Läuft sie nach `warten_s` noch: `Ausstehend`, sie läuft weiter.
        Ausnahmen der Bedeutungssuche (etwa `BedeutungFehlt`) kommen unverändert durch."""
        lauf = self._lauf(frage, anzahl)
        try:
            stellen = await asyncio.wait_for(asyncio.shield(lauf.aufgabe), timeout=warten_s)
        except TimeoutError as f:
            raise Ausstehend from f
        return stellen, lauf.dauer_ms
