"""Schnittstelle der Bausteine: je Grundstruktur eines Buchs ein Baustein mit eigenen Methoden (Nutzer 01.11.2026:
"jede ZIM-Quelle mit anderer Grundstruktur muss erneut implementiert werden, mit eigenen Methoden und Layouts").

Ein Baustein bekommt den rohen Eintrag und die Wege der App (wohin Verweise und Bilder zeigen, ob ein Pfad im Buch
steht) und liefert den aufbereiteten Artikel. Er kennt weder die Schnittstelle noch die Oberfläche."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from ..bibliothek import Eintrag
from ..modell.artikel import Abschnitt, Darstellung, Kachel, Steckbrief, Verweiszahlen
from ..modell.buch import Art, Buch


@dataclass(frozen=True)
class Wege:
    """Wohin Verweise zeigen; eine Stelle für alle Bausteine (die Pfade der Oberfläche und der Schnittstelle)."""
    artikel: Callable[[str, str], str]           # (buch, pfad) -> Adresse der Leseseite
    medien: Callable[[str, str], str]            # (buch, pfad) -> Adresse des Mediums
    original: Callable[[str, str], str]          # (buch, pfad) -> Adresse der unveränderten Seite
    gibt_es: Callable[[str, str], bool]          # (buch, pfad) -> steht der Pfad im Buch?


@dataclass
class Aufbereitet:
    titel: str
    html: str = ""
    einleitung: str = ""
    abschnitte: list[Abschnitt] = field(default_factory=list)
    steckbrief: Steckbrief | None = None
    bild: str = ""
    verweise: Verweiszahlen = field(default_factory=Verweiszahlen)
    online: list[str] = field(default_factory=list)
    kacheln: list[Kachel] = field(default_factory=list)


class Baustein(Protocol):
    kennung: str
    arten: frozenset[Art]
    darstellung: Darstellung

    def passt(self, eintrag: Eintrag) -> bool:
        """Kann der Baustein diese Seite lesen? Auch ein Buch seiner Art hat Seiten anderer Bauart (etwa die
        Startseite aus Kacheln); die zeigt dann die Originalansicht."""
        ...

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet: ...
