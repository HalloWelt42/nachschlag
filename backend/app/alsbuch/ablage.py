"""Ablage der fertigen Bücher in der Kellerwolke (WIKI-45): je Thema ein Ordner unter Bücher im Zweig der App, darin
EPUB und PDF je Vorlage. Eine vorhandene Datei bekommt eine neue Fassung; Löschen geht in den Papierkorb."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from appkern.kellerwolke import Kellerwolke, KellerwolkeFehler

from ..sammlung.dienst import ordnername

ORDNER = "Bücher"


class AblageFehler(Exception):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class Buchablage:
    def __init__(self, kellerwolke: Callable[[], Kellerwolke | None]) -> None:
        self._kw = kellerwolke

    def _wolke(self) -> Kellerwolke:
        kw = self._kw()
        if kw is None:
            raise AblageFehler("Kellerwolke nicht eingerichtet (Einstellungen, Verbindungen): dort liegen die Bücher")
        return kw

    async def ordner(self, thema: str = "") -> str:
        """Der Ordner der Bücher (mit Thema: der des Themas) als Pfad in der Kellerwolke."""
        try:
            zweig = (await self._wolke().ich()).zweig
        except (AblageFehler, KellerwolkeFehler):
            zweig = "Apps/Nachschlag"
        return f"{zweig}/{ORDNER}" + (f"/{ordnername(thema)}" if thema else "")

    @staticmethod
    def dateiname(titel: str, vorlage: str, endung: str) -> str:
        return f"{ordnername(titel)} - {ordnername(vorlage)}.{endung}"

    async def ablegen(self, thema: str, name: str, daten: bytes, art: str) -> str:
        kw = self._wolke()
        ordner = await self.ordner(thema)
        pfad = f"{ordner}/{name}"
        try:
            await kw.ordner(ordner)
            alt = await kw.finden(pfad)
            await kw.schreiben(pfad, daten, stand=alt.etag if alt else None, inhaltstyp=art)
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Das Buch ließ sich nicht in der Kellerwolke ablegen: {f}") from f
        return pfad

    async def oeffnen(self, pfad: str) -> AsyncIterator[bytes]:
        """Den Inhalt einer Datei zum Lesen in Stücken; fehlt sie, gleich AblageFehler (nicht erst beim Lesen)."""
        kw = self._wolke()
        try:
            knoten = await kw.finden(pfad)
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke antwortet nicht: {f}") from f
        if knoten is None:
            raise AblageFehler("Die Datei liegt nicht mehr in der Kellerwolke")
        return kw.lesen(knoten.id)

    async def loeschen(self, pfad: str) -> None:
        """In den Papierkorb der Kellerwolke; fehlt die Datei schon, ist nichts zu tun."""
        kw = self._wolke()
        knoten = await kw.finden(pfad)
        if knoten is not None:
            await kw.loeschen(knoten.id)
