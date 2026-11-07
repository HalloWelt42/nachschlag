"""Das Nachtfenster aus den Einstellungen (Über Nacht): Sammlungen, die für heute Nacht bestellt sind, und der
Bücherlader mit "nur nachts" warten bis dahin."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

ZONE = ZoneInfo("Europe/Berlin")


def nachts(jetzt: datetime, von: int, bis: int) -> bool:
    """Liegt die Stunde im Nachtfenster (über Mitternacht: 22 bis 7)?"""
    h = jetzt.hour
    return (von <= h or h < bis) if von > bis else (von <= h < bis)
