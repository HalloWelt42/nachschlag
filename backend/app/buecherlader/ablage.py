"""Die Dateien des Bücherladers im Ordner der Bücher. Im Ordner selbst liegen die Bücher der Bibliothek (`*.zim`, nur
diese liest Nachschlag); daneben zwei verborgene Ordner auf demselben Datenträger, damit Verschieben nie kopiert:

- `.laden/`  angefangene Dateien; Laden setzt dort fort
- `.neu/`    geladene und geprüfte neue Fassungen, die auf das Umschalten warten

Alles hier ist schnelle Arbeit an Verzeichnissen (Lesen eines Ordners, Umbenennen), ohne Netz."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .verzeichnis import zerlegen

LADEN = ".laden"
NEU = ".neu"


@dataclass(frozen=True)
class Lokal:
    kennung: str      # Dateiname ohne .zim
    stamm: str
    stand: str
    pfad: Path


def _buecher(ordner: Path) -> list[Lokal]:
    if not ordner.is_dir():
        return []
    aus = []
    for p in sorted(ordner.glob("*.zim")):
        if p.is_file() and (n := zerlegen(p.name)):
            aus.append(Lokal(p.stem, n.stamm, n.stand, p))
    return aus


def _neueste(buecher: list[Lokal]) -> dict[str, Lokal]:
    aus: dict[str, Lokal] = {}
    for b in buecher:
        if b.stamm not in aus or b.stand > aus[b.stamm].stand:
            aus[b.stamm] = b
    return aus


class Ablage:
    def __init__(self, ordner: Path) -> None:
        self.ordner = ordner

    @property
    def laden(self) -> Path:
        return self.ordner / LADEN

    @property
    def neu(self) -> Path:
        return self.ordner / NEU

    def beschreibbar(self) -> bool:
        return self.ordner.is_dir() and os.access(self.ordner, os.W_OK)

    # ----- was da ist ---------------------------------------------------------------------------------------------

    def alle(self) -> list[Lokal]:
        """Alle Bücher der Bibliothek (auch ältere Fassungen)."""
        return _buecher(self.ordner)

    def aktive(self) -> dict[str, Lokal]:
        """Je Stamm die jüngste Fassung in der Bibliothek (die Nachschlag als aktiv führt)."""
        return _neueste(self.alle())

    def wartende(self) -> dict[str, Lokal]:
        """Je Stamm die jüngste geprüfte Fassung, die aufs Umschalten wartet."""
        return _neueste(_buecher(self.neu))

    def liegt(self, datei: str) -> str:
        """Wo eine Datei schon fertig liegt: "Bibliothek", "wartet aufs Umschalten" oder leer (noch nicht da)."""
        if (self.ordner / datei).is_file():
            return "Bibliothek"
        if (self.neu / datei).is_file():
            return "wartet aufs Umschalten"
        return ""

    def teil(self, datei: str) -> Path:
        """Die angefangene Datei beim Laden."""
        return self.laden / datei

    def belegt(self) -> tuple[int, int]:
        """Bytes der Bücher (Bibliothek und wartende) und der angefangenen Dateien."""
        buecher = sum(b.pfad.stat().st_size for b in self.alle() + _buecher(self.neu))
        laden = sum(p.stat().st_size for p in self.laden.glob("*.zim")) if self.laden.is_dir() else 0
        return buecher, laden

    def platz(self) -> tuple[int, int]:
        """Frei und gesamt auf dem Datenträger der Bücher, Bytes."""
        stand = shutil.disk_usage(self.ordner)
        return stand.free, stand.total

    # ----- verschieben ----------------------------------------------------------------------------------------------

    def ablegen(self, teil: Path, wartend: bool) -> Path:
        """Eine fertig geprüfte Datei in die Bibliothek legen oder, als neue Fassung eines vorhandenen Buchs, zu den
        wartenden. Eine ältere wartende Fassung desselben Buchs war nie aktiv und weicht."""
        n = zerlegen(teil.name)
        ziel_ordner = self.neu if wartend else self.ordner
        ziel_ordner.mkdir(exist_ok=True)
        if wartend and n:
            for alt in _buecher(self.neu):
                if alt.stamm == n.stamm and alt.stand < n.stand:
                    alt.pfad.unlink()
        ziel = ziel_ordner / teil.name
        os.replace(teil, ziel)
        return ziel

    def umschalten(self, stamm: str) -> Lokal:
        """Die wartende Fassung eines Buchs in die Bibliothek legen; KeyError, wenn keine wartet."""
        wartend = self.wartende()[stamm]
        ziel = self.ordner / wartend.pfad.name
        os.replace(wartend.pfad, ziel)
        return Lokal(wartend.kennung, wartend.stamm, wartend.stand, ziel)

    def zuruecklegen(self, kennung: str) -> None:
        """Eine Fassung aus der Bibliothek wieder zu den wartenden legen (Zurück auf die vorige)."""
        self.neu.mkdir(exist_ok=True)
        os.replace(self.ordner / f"{kennung}.zim", self.neu / f"{kennung}.zim")

    def entfernen(self, kennung: str) -> bool:
        """Eine Fassung aus der Bibliothek löschen; war sie schon weg: False."""
        pfad = self.ordner / f"{kennung}.zim"
        if not pfad.is_file():
            return False
        pfad.unlink()
        return True
