"""Wo die Originalseiten laufen und mit welchem Schein (WIKI-85)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from starlette.datastructures import URL

#: Weg der Originalseiten: PRAEFIX/<schein>/<buch>/<pfad>, dazu PRAEFIX/bruecke.js
PRAEFIX = "/api/v1/original"
#: so lange gilt ein Schein; alle Scheine eines Tages sind gleich, so bleibt der Zwischenspeicher des Browsers nutzbar
GUELTIG_TAGE = 7
#: das Geheimnis der Scheine im Datenordner: einmal erzeugt, so gelten Scheine auch nach einem Neustart
GEHEIM_DATEI = "originalansicht.geheim"
_TAG_S = 86400


def _geheimnis(daten: Path) -> bytes:
    datei = daten / GEHEIM_DATEI
    try:
        return datei.read_bytes()
    except FileNotFoundError:
        pass
    daten.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(datei, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:                   # gleichzeitig angelegt: das andere gilt
        return datei.read_bytes()
    with os.fdopen(fd, "wb") as f:
        f.write(secrets.token_bytes(32))
    return datei.read_bytes()


class Originalherkunft:
    """Port der Originalansicht und die Scheine für ihre Adressen. `uhr` nur für Tests."""

    def __init__(self, port: int, geheim: bytes, uhr: Callable[[], float] = time.time) -> None:
        self.port = port
        self._geheim = geheim
        self._uhr = uhr

    @classmethod
    def im_ordner(cls, port: int, daten: Path) -> Originalherkunft:
        return cls(port, _geheimnis(daten))

    def _heute(self) -> int:
        return int(self._uhr() // _TAG_S)

    def _signatur(self, buch: str, ablauf: int) -> str:
        roh = hmac.new(self._geheim, f"{ablauf}\n{buch}".encode(), hashlib.sha256).digest()
        return base64.urlsafe_b64encode(roh[:16]).decode().rstrip("=")

    def schein(self, buch: str) -> str:
        """Schein für ein Buch: Ablauftag und Signatur. Er gilt GUELTIG_TAGE ab heute."""
        ablauf = self._heute() + GUELTIG_TAGE
        return f"{ablauf}.{self._signatur(buch, ablauf)}"

    def gilt(self, schein: str, buch: str) -> bool:
        ablauf, _, signatur = schein.partition(".")
        if not ablauf.isdigit():
            return False
        heute = self._heute()
        return heute <= int(ablauf) <= heute + GUELTIG_TAGE and hmac.compare_digest(signatur, self._signatur(buch, int(ablauf)))

    def weg(self, buch: str, rest: str) -> str:
        """Weg einer Originalseite; `rest` ist Buch und Pfad, schon für die Adresse kodiert."""
        return f"{PRAEFIX}/{self.schein(buch)}/{rest}"

    def adresse(self, anfrage: URL, weg: str) -> str:
        """Die volle Adresse eines Wegs: Schema und Rechner wie die Anfrage an die App, der Port der Originalansicht."""
        return str(anfrage.replace(port=self.port, path=weg, query="", fragment=""))

    def ist_original(self, anfrage: URL) -> bool:
        """Kam die Anfrage über den Port der Originalansicht? Der Vorschaltdienst reicht den Rechner mit Port durch."""
        return anfrage.port == self.port
