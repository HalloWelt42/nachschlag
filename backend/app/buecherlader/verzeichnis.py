"""Das Verzeichnis der Bücher lesen (WIKI-57): eine Seite je Ordner, wie sie ein Webserver für ein Verzeichnis ausgibt.
Nur reine Funktionen, ohne Netz: Ordner und Dateien aus dem HTML, Name einer Datei in Stamm, Sprache und Stand zerlegen,
je Stamm die neueste Fassung.

Ein Stamm ist der Dateiname ohne Stand (`wikipedia_de_all_maxi`), also ein Buch in einer Auswahl und Ausgabe; der Stand
ist Jahr und Monat (`2026-10`). Die Sprache steht im Namen an zweiter Stelle (`stackoverflow.com_en_all`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import unquote

#: Verweis samt Größe in der Zeile einer Verzeichnisseite: `<a href="x.zim">x.zim</a>  2026-10-02 18:05   45G`
_ZEILE = re.compile(r'<a href="(?P<ziel>[^"?#]+)">[^<]*</a>\s+(?P<datum>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+(?P<groesse>[\d.]+[KMGT]?|-)')
_NAME = re.compile(r"^(?P<stamm>[^/]+)_(?P<stand>\d{4}-\d{2})\.zim$")
_EINHEIT = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
#: Ausgaben eines Buchs: mit Bildern, ohne Bilder, nur Einleitungen
AUSGABEN = ("maxi", "nopic", "mini")


@dataclass(frozen=True)
class Datei:
    ordner: str          # Unterordner im Verzeichnis, etwa wikipedia
    datei: str           # Dateiname, etwa wikipedia_de_all_maxi_2026-10.zim
    stamm: str           # wikipedia_de_all_maxi
    sprache: str         # de, en, mul ...
    stand: str           # 2026-10
    groesse: int         # laut Verzeichnisseite, gerundet; genau erst beim Laden

    @property
    def pfad(self) -> str:
        return f"{self.ordner}/{self.datei}"


@dataclass(frozen=True)
class Name:
    stamm: str
    sprache: str
    stand: str


def zerlegen(dateiname: str) -> Name | None:
    """Stamm, Sprache und Stand aus dem Namen einer ZIM-Datei; kein ZIM oder ohne Stand: None."""
    m = _NAME.match(dateiname)
    if not m:
        return None
    teile = m["stamm"].split("_")
    return Name(m["stamm"], teile[1] if len(teile) > 1 else "", m["stand"])


def basis_und_ausgabe(stamm: str) -> tuple[str, str]:
    """`wikipedia_de_all_maxi` -> (`wikipedia_de_all`, `maxi`); ohne Ausgabe im Namen: (Stamm, leer)."""
    vorne, _, letzte = stamm.rpartition("_")
    return (vorne, letzte) if vorne and letzte in AUSGABEN else (stamm, "")


def _bytes(angabe: str) -> int:
    if angabe == "-":
        return 0
    zahl, einheit = (angabe[:-1], angabe[-1]) if angabe[-1] in "KMGT" else (angabe, "")
    return int(float(zahl) * _EINHEIT[einheit])


def ordner_aus(html: str) -> list[str]:
    """Die Unterordner einer Verzeichnisseite (ohne den Weg nach oben)."""
    gefunden = []
    for m in _ZEILE.finditer(html):
        ziel = unquote(unescape(m["ziel"]))
        if ziel.endswith("/") and not ziel.startswith(("/", ".")) and "/" not in ziel[:-1]:
            gefunden.append(ziel[:-1])
    return gefunden


def dateien_aus(ordner: str, html: str) -> list[Datei]:
    """Die ZIM-Dateien einer Verzeichnisseite mit Stamm, Sprache, Stand und ungefährer Größe."""
    dateien = []
    for m in _ZEILE.finditer(html):
        name = unquote(unescape(m["ziel"]))
        teile = zerlegen(name)
        if teile:
            dateien.append(Datei(ordner, name, teile.stamm, teile.sprache, teile.stand, _bytes(m["groesse"])))
    return dateien


def neueste(dateien: list[Datei]) -> dict[str, Datei]:
    """Je Stamm die Datei mit dem jüngsten Stand."""
    aus: dict[str, Datei] = {}
    for d in dateien:
        if d.stamm not in aus or d.stand > aus[d.stamm].stand:
            aus[d.stamm] = d
    return aus
