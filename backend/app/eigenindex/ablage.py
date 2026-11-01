"""Wo die eigenen Indizes liegen und welcher gilt: je Buch eine Datei im Ordner aus den Einstellungen. Ein Index gilt
nur fertig gebaut und in der Fassung des Schemas; fehlt er oder gilt er nicht, sucht das Buch über den Index der
ZIM-Datei. Ausgetauscht wird ein Index in einem Schritt (neue Datei an seine Stelle); die Prüfung merkt sich je Datei
den Zeitstempel und sieht so einen Austausch von selbst."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import schema


class Eigenindizes:
    def __init__(self, ordner: Callable[[], str]) -> None:
        self._ordner = ordner
        self._geprueft: dict[Path, tuple[int, bool]] = {}

    def pfad(self, kennung: str) -> Path | None:
        """Wo der Index eines Buchs liegt oder hinkommt; ohne Ordner in den Einstellungen nirgends."""
        ordner = self._ordner()
        return Path(ordner) / schema.dateiname(kennung) if ordner else None

    def alle(self, kennungen: list[str] | None = None) -> list[Path]:
        """Die geltenden Indizes aller (oder der genannten) Quellen."""
        ordner = self._ordner()
        if not ordner or not Path(ordner).is_dir():
            return []
        namen = kennungen if kennungen else [p.name.removesuffix(".sqlite") for p in Path(ordner).glob("*.sqlite")]
        return [d for k in namen if (d := self.datei(k))]

    def datei(self, kennung: str) -> Path | None:
        """Der geltende Index eines Buchs, sonst None."""
        pfad = self.pfad(kennung)
        if pfad is None:
            return None
        try:
            zeit = pfad.stat().st_mtime_ns
        except OSError:
            return None
        alt = self._geprueft.get(pfad)
        if alt is None or alt[0] != zeit:
            alt = (zeit, schema.gueltig(pfad))
            self._geprueft[pfad] = alt
        return pfad if alt[1] else None
