"""Bausteine je Grundstruktur der Bücher. Ein neuer Baustein kommt in BAUSTEINE; sonst ändert sich nichts."""

from __future__ import annotations

from ..modell.buch import Buch
from .basis import Aufbereitet, Baustein, Wege
from .enzyklopaedie import Enzyklopaedie
from .original import Originalansicht

BAUSTEINE: tuple[Baustein, ...] = (Enzyklopaedie(),)
RUECKFALL: Baustein = Originalansicht()


def baustein_fuer(buch: Buch) -> Baustein:
    """Der Baustein für die Art des Buchs; ohne passenden die Originalansicht."""
    return next((b for b in BAUSTEINE if buch.art in b.arten), RUECKFALL)


__all__ = ["Aufbereitet", "Baustein", "Wege", "baustein_fuer", "BAUSTEINE", "RUECKFALL"]
