"""Die Ablage der großen Bilder: feste Pfade, aus denen Nachschlag ohne Rückfrage liest (nur lesend eingehängt).

    <ablage>/<quelle>/<zwei Zeichen>/<Dateiname>          das Bild
    <ablage>/<quelle>/<zwei Zeichen>/<Dateiname>.json     Urheber, Lizenz, Breite, Herkunft

Die zwei Zeichen sind der Anfang der SHA-1 des Dateinamens (verteilt die Bilder auf 256 Ordner je Wiki). Ein Bild gilt erst,
wenn seine Angaben daneben liegen: geschrieben wird erst das Bild, dann die Angaben, beides über eine Teildatei."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pydantic import BaseModel

#: Zeichen, die in Dateinamen der Ablage nicht vorkommen dürfen (Wiki-Namen enthalten keine Schrägstriche, aber sicher ist sicher)
_VERBOTEN = str.maketrans({"/": "_", "\\": "_", "\x00": "_"})


class Angaben(BaseModel):
    quelle: str
    name: str
    breite: int
    hoehe: int
    original: int
    bytes: int
    mime: str
    urheber: str = ""
    lizenz: str = ""
    lizenz_url: str = ""
    seite_url: str = ""
    am: str


def dateiname(name: str) -> str:
    return name.translate(_VERBOTEN)[:240]


def pfad(ablage: Path, quelle: str, name: str) -> Path:
    """Wo das große Bild zu einem Dateinamen liegt (oder hinkommt)."""
    return ablage / quelle / hashlib.sha1(name.encode()).hexdigest()[:2] / dateiname(name)


def angaben_pfad(bild: Path) -> Path:
    return bild.with_name(bild.name + ".json")


def da(ablage: Path, quelle: str, name: str) -> bool:
    return angaben_pfad(pfad(ablage, quelle, name)).is_file()


def lesen(ablage: Path, quelle: str, name: str) -> tuple[Path, Angaben] | None:
    """Bild und Angaben, wenn das große Bild da ist."""
    bild = pfad(ablage, quelle, name)
    try:
        return bild, Angaben.model_validate_json(angaben_pfad(bild).read_text())
    except (OSError, ValueError):
        return None


def _schreiben(ziel: Path, daten: bytes) -> None:
    teil = ziel.with_name(ziel.name + ".teil")
    teil.write_bytes(daten)
    os.replace(teil, ziel)


def ablegen(ablage: Path, inhalt: bytes, angaben: Angaben) -> Path:
    bild = pfad(ablage, angaben.quelle, angaben.name)
    bild.parent.mkdir(parents=True, exist_ok=True)
    _schreiben(bild, inhalt)
    _schreiben(angaben_pfad(bild), json.dumps(angaben.model_dump(), ensure_ascii=False).encode())
    return bild
