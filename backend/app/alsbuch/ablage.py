"""Ablage der fertigen Bücher (WIKI-45): je Thema ein Ordner unter Bücher in der Ablage der App (Kellerwolke oder
Datenordner, WIKI-11, `appkern.ablage`), darin EPUB und PDF je Vorlage. Eine vorhandene Datei bekommt einen neuen
Stand; Löschen geht in der Kellerwolke in den Papierkorb. Gemerkt wird je Datei ihr Pfad in der Ablage."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from appkern.ablage import Ablage, AblageFehler, Eintrag

from ..sammlung.dienst import ordnername

ORDNER = "Bücher"
#: so begannen Pfade vor WIKI-11 (voller Pfad in der Kellerwolke, Apps/<App>/...); sie gelten weiter
_FRUEHER = "Apps/"

__all__ = ["AblageFehler", "Buchablage", "ORDNER"]


class Buchablage:
    def __init__(self, ablage: Callable[[], Ablage]) -> None:
        self._ablage = ablage

    async def ordner(self, thema: str = "") -> str:
        """Der Ordner der Bücher (mit Thema: der des Themas), wie Menschen ihn finden."""
        return await self._ablage().ort(f"{ORDNER}/{ordnername(thema)}" if thema else ORDNER)

    @staticmethod
    def dateiname(titel: str, vorlage: str, endung: str) -> str:
        return f"{ordnername(titel)} - {ordnername(vorlage)}.{endung}"

    async def ablegen(self, thema: str, name: str, daten: bytes, art: str) -> str:
        """Schreibt die Datei und gibt ihren Pfad in der Ablage zurück (zum Merken am Buch)."""
        e = await self._ablage().schreiben(f"{ORDNER}/{ordnername(thema)}/{name}", daten, inhaltstyp=art)
        return e.pfad

    @staticmethod
    async def _finden(ablage: Ablage, pfad: str) -> Eintrag | None:
        e = await ablage.finden(pfad)
        if e is None and pfad.startswith(_FRUEHER) and pfad.count("/") >= 2:
            e = await ablage.finden(pfad.split("/", 2)[2])        # früher gemerkter voller Pfad der Kellerwolke
        return e

    async def oeffnen(self, pfad: str) -> AsyncIterator[bytes]:
        """Den Inhalt einer Datei zum Lesen in Stücken; fehlt sie, gleich AblageFehler (nicht erst beim Lesen)."""
        ablage = self._ablage()
        e = await self._finden(ablage, pfad)
        if e is None:
            raise AblageFehler(f"Die Datei liegt nicht mehr in der Ablage ({ablage.name})")
        return ablage.lesen(e.kennung)

    async def loeschen(self, pfad: str) -> None:
        """Löscht die Datei (in der Kellerwolke: in den Papierkorb); fehlt sie schon, ist nichts zu tun."""
        ablage = self._ablage()
        e = await self._finden(ablage, pfad)
        if e is not None:
            await ablage.loeschen(e.kennung)
