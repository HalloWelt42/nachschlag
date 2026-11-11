"""Das Verzeichnis der Bücher lesen (WIKI-57): eine Seite je Ordner, wie sie ein Webserver für ein Verzeichnis ausgibt.
Nur reine Funktionen, ohne Netz: Ordner und Dateien aus dem HTML, Name einer Datei in Stamm, Sprache und Stand zerlegen,
je Stamm die neueste Fassung.

Die Spiegel geben ihre Verzeichnisse verschieden aus (WIKI-62): Apache als Text oder Tabelle, lighttpd mit `span href`,
nginx als Text; die Größe steht mal als "45G", mal als "1.2 GiB". Gelesen wird darum je Zeile (Tabellenzeile oder
Textzeile): ihre Verweise und eine Größe mit Einheit; ohne Größe ist sie unbekannt (0), genau kommt sie beim Laden.

Ein Stamm ist der Dateiname ohne Stand (`wikipedia_de_all_maxi`), also ein Buch in einer Auswahl und Ausgabe; der Stand
ist Jahr und Monat (`2026-10`). Die Sprache steht im Namen an zweiter Stelle (`stackoverflow.com_en_all`)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import unquote

from ..modell.buch import STAND_MUSTER

#: Eine Zeile einer Verzeichnisseite: eine Tabellenzeile oder eine Textzeile
_ZEILEN = re.compile(r"<tr\b|\n", re.I)
#: Verweis auf eine Datei oder einen Unterordner (auch `span href` wie bei lighttpd)
_VERWEIS = re.compile(r'href="([^"?#]+)"', re.I)
_TAG = re.compile(r"<[^>]+>")
#: Größe mit Einheit: 45G, 1.2 GiB, 512K, 3,5 MB
_GROESSE = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*([KMGT])(?:i?B)?(?![\w])")
_NAME = re.compile(rf"^(?P<stamm>[^/]+)_(?P<stand>{STAND_MUSTER})\.zim$")
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


def _bytes(zeile: str) -> int:
    """Die Größe in einer Zeile (die letzte Angabe mit Einheit, hinter Name und Datum); keine: 0 (unbekannt)."""
    treffer = _GROESSE.findall(unescape(_TAG.sub(" ", zeile)))
    if not treffer:
        return 0
    zahl, einheit = treffer[-1]
    return int(float(zahl.replace(",", ".")) * _EINHEIT[einheit])


def _zeilen(html: str) -> list[tuple[list[str], str]]:
    """Je Zeile die Verweise (entschlüsselt, ohne Doppel) und die Zeile selbst."""
    aus = []
    for zeile in _ZEILEN.split(html):
        verweise = list(dict.fromkeys(unquote(unescape(v)) for v in _VERWEIS.findall(zeile)))
        if verweise:
            aus.append((verweise, zeile))
    return aus


def ordner_aus(html: str) -> list[str]:
    """Die Unterordner einer Verzeichnisseite (ohne den Weg nach oben, Sortierverweise und fremde Adressen)."""
    gefunden: list[str] = []
    for verweise, _ in _zeilen(html):
        for ziel in verweise:
            if ziel.endswith("/") and not ziel.startswith(("/", ".", "http:", "https:")) and "/" not in ziel[:-1] \
                    and ziel[:-1] not in gefunden:
                gefunden.append(ziel[:-1])
    return gefunden


def dateien_aus(ordner: str, html: str) -> list[Datei]:
    """Die ZIM-Dateien einer Verzeichnisseite mit Stamm, Sprache, Stand und ungefährer Größe."""
    dateien, gesehen = [], set()
    for verweise, zeile in _zeilen(html):
        for name in verweise:
            name = name.rsplit("/", 1)[-1]
            teile = zerlegen(name)
            if teile and name not in gesehen:
                gesehen.add(name)
                dateien.append(Datei(ordner, name, teile.stamm, teile.sprache, teile.stand, _bytes(zeile)))
    return dateien


def neueste(dateien: list[Datei]) -> dict[str, Datei]:
    """Je Stamm die Datei mit dem jüngsten Stand."""
    aus: dict[str, Datei] = {}
    for d in dateien:
        if d.stamm not in aus or d.stand > aus[d.stamm].stand:
            aus[d.stamm] = d
    return aus
