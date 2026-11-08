"""Wo die eigenen Indizes liegen und welcher gilt: je Buch eine Datei im Ordner aus den Einstellungen. Ein Index gilt
nur fertig gebaut und in der Fassung des Schemas; fehlt er oder gilt er nicht, sucht das Buch über den Index der
ZIM-Datei. Ausgetauscht wird ein Index in einem Schritt (neue Datei an seine Stelle); die Prüfung merkt sich je Datei
den Zeitstempel und sieht so einen Austausch von selbst."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from . import schema


_STAND = re.compile(r"^(?P<stamm>.+)_(?P<stand>\d{4}-\d{2})$")


class Eigenindizes:
    def __init__(self, ordner: Callable[[], str], gueltig: Callable[[Path], bool] = schema.gueltig) -> None:
        """`gueltig`: ob eine Datei gilt (fertig und im eigenen Schema); andere Dateiarten (Kategorien) bringen ihre mit."""
        self._ordner, self._gueltig = ordner, gueltig
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
            alt = (zeit, self._gueltig(pfad))
            self._geprueft[pfad] = alt
        return pfad if alt[1] else None

    def entfernen(self, kennung: str) -> bool:
        """Den Index eines Buchs löschen (samt Prüfsumme und Nebendateien der Datenbank); war keiner da: False."""
        pfad = self.pfad(kennung)
        if pfad is None:
            return False
        weg = False
        for p in (pfad, pfad.with_suffix(".sha256"), Path(f"{pfad}-wal"), Path(f"{pfad}-shm")):
            if p.is_file():
                p.unlink()
                weg = True
        self._geprueft.pop(pfad, None)
        return weg

    def veraltet(self, kennung: str) -> bool:
        """Gilt, aber ohne die Ergänzungen dieses Stands (WIKI-21): der Index-Dienst zieht sie nach."""
        pfad = self.datei(kennung)
        return pfad is not None and not schema.aktuell(pfad)

    def vorgaenger(self, kennung: str) -> str:
        """Kennung des jüngsten geltenden Index einer früheren Fassung desselben Buchs (gleicher Name, älterer Stand),
        als Vorlage für den Bau (WIKI-58); keiner: leer. Die Datei des Buchs selbst muss dafür nicht mehr da sein."""
        m, ordner = _STAND.match(kennung), self._ordner()
        if not m or not ordner or not Path(ordner).is_dir():
            return ""
        frueher = sorted((n["stand"], p.stem) for p in Path(ordner).glob(f"{m['stamm']}_*.sqlite")
                         if (n := _STAND.match(p.stem)) and n["stamm"] == m["stamm"] and n["stand"] < m["stand"])
        return next((k for _, k in reversed(frueher) if self.datei(k)), "")

