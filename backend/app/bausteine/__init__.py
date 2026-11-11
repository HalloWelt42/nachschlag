"""Bausteine je Grundstruktur der Bücher. Ein neuer Baustein kommt in BAUSTEINE; sonst ändert sich nichts."""

from __future__ import annotations

from ..bibliothek import Eintrag
from ..modell.buch import Buch
from .anleitung import Anleitung, Anleitungsstart, Geraet
from .dateiformat import Dateiformat
from .basis import Aufbereitet, Baustein, Wege
from .dokumentation import Dokumentation
from .enzyklopaedie import Enzyklopaedie
from .kategorie import Kategorie
from .frage_antwort import FrageAntwort
from .original import Originalansicht
from .uebersicht import Uebersicht
from .uebung import Uebung, Uebungsstart

BAUSTEINE: tuple[Baustein, ...] = (Uebersicht(), Kategorie(), Enzyklopaedie(), Dokumentation(), FrageAntwort(), Anleitung(), Geraet(),
                                   Anleitungsstart(), Uebung(), Uebungsstart(), Dateiformat())
RUECKFALL: Baustein = Originalansicht()


def baustein_fuer(buch: Buch, eintrag: Eintrag) -> Baustein:
    """Der Baustein für die Art des Buchs, wenn er die Seite lesen kann; sonst die Originalansicht."""
    return next((b for b in BAUSTEINE if buch.art in b.arten and b.passt(eintrag)), RUECKFALL)


__all__ = ["Aufbereitet", "Baustein", "Wege", "baustein_fuer", "BAUSTEINE", "RUECKFALL"]
