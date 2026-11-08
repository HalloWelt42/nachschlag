"""Das Nachtfenster aus den Einstellungen (Über Nacht): Arbeiten, die für heute Nacht bestellt sind (Sammlungen, Bücher),
und der Bücherlader mit "nur nachts" warten bis dahin. Eine Stelle für die Regel (`nachts`), die Uhr dazu
(`Nachtfenster`) und das Wecken der Aufträge, wenn die Nacht beginnt (`Nachtwecker`, einer für alle Dienste)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from appkern.app.begleiter import Begleiter
from appkern.auftraege import Auftraege

ZONE = ZoneInfo("Europe/Berlin")
#: so oft sieht der Nachtwecker auf die Uhr
WECKER_S = 60


def nachts(jetzt: datetime, von: int, bis: int) -> bool:
    """Liegt die Stunde im Nachtfenster (über Mitternacht: 22 bis 7)?"""
    h = jetzt.hour
    return (von <= h or h < bis) if von > bis else (von <= h < bis)


class Nachtfenster:
    """Das Fenster aus den Einstellungen mit der Uhr: ist jetzt Nacht, warum wartet ein Auftrag, wann beginnt und endet
    die Nacht, in der etwas jetzt Bestelltes läuft."""

    def __init__(self, fenster: Callable[[], tuple[int, int]], uhr: Callable[[], datetime] = lambda: datetime.now(ZONE)) -> None:
        self._fenster, self._uhr = fenster, uhr

    @property
    def von_bis(self) -> tuple[int, int]:
        return self._fenster()

    def jetzt(self) -> datetime:
        return self._uhr().astimezone(ZONE)

    def ist_nacht(self) -> bool:
        return nachts(self.jetzt(), *self._fenster())

    def warten(self) -> str:
        """Grund zum Warten in Worten, solange keine Nacht ist; sonst leer."""
        von, bis = self._fenster()
        return "" if self.ist_nacht() else f"wartet auf die Nacht ({von} bis {bis} Uhr)"

    def naechste(self) -> tuple[datetime, datetime]:
        """Beginn und Ende der Nacht, in der etwas jetzt Bestelltes läuft: die laufende (Beginn jetzt) oder die nächste."""
        von, bis = self._fenster()
        jetzt = self.jetzt().replace(second=0, microsecond=0)
        if self.ist_nacht():
            beginn = jetzt
        else:
            beginn = jetzt.replace(hour=von, minute=0)
            if beginn <= jetzt:
                beginn += timedelta(days=1)
        ende = beginn.replace(hour=bis, minute=0)
        while ende <= beginn:
            ende += timedelta(days=1)
        return beginn, ende


class Nachtwecker(Begleiter):
    """Beginnt die Nacht, sehen die Aufträge nach, ob Zurückgestelltes jetzt darf (für alle Dienste mit "nachts")."""

    def __init__(self, auftraege: Auftraege, fenster: Nachtfenster, takt_s: float = WECKER_S) -> None:
        self._auftraege, self._fenster, self._takt = auftraege, fenster, takt_s
        self._aufgabe: asyncio.Task | None = None

    async def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._wecken(), name="nachtwecker")

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()

    async def _wecken(self) -> None:
        war = None
        while True:
            jetzt = self._fenster.ist_nacht()
            if jetzt and war is False:
                self._auftraege.wecken()
            war = jetzt
            await asyncio.sleep(self._takt)
