"""Bilder an Notizen (WIKI-51, Entscheidung 02.11.2026): eingefügt aus der Zwischenablage oder gewählt aus einer Datei,
am Rechner und am Telefon. Die Dateien liegen in der Kellerwolke unter <Zweig der App>/Notizen/<Notiz>/ (wie die
Ergebnisse der Sammlungen), die Notiz merkt sich ihre Liste. Nachschlag liefert sie aus, damit die Oberfläche nur mit
der eigenen Anmeldung auskommt. Erkannt wird die Art am Inhalt, nicht am Namen."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from appkern.kellerwolke import Kellerwolke, KellerwolkeFehler, NichtGefunden

from ..modell.meins import Notiz, Notizbild
from .speicher import Meins

#: so groß darf ein Bild sein (Bildschirmfotos und Fotos vom Telefon)
HOECHSTENS_BYTES = 25 * 1024 * 1024

#: Arten, die jeder Browser zeigt, mit ihrem Anfang und ihrer Endung
ARTEN: tuple[tuple[str, bytes, str], ...] = (
    ("image/png", b"\x89PNG\r\n\x1a\n", ".png"),
    ("image/jpeg", b"\xff\xd8\xff", ".jpg"),
    ("image/gif", b"GIF8", ".gif"),
)


class BildFehler(Exception):
    """Etwas am Bild oder an der Ablage stimmt nicht; die Meldung ist für Menschen."""

    def __init__(self, meldung: str, status: int = 422) -> None:
        super().__init__(meldung)
        self.meldung, self.status = meldung, status


def art_von(daten: bytes) -> tuple[str, str] | None:
    """Art und Endung eines Bilds aus seinem Anfang; WebP steckt in einem RIFF-Behälter."""
    if daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return next(((typ, endung) for typ, anfang, endung in ARTEN if daten.startswith(anfang)), None)


class Notizbilder:
    def __init__(self, meins: Meins, kellerwolke: Callable[[], Kellerwolke | None]) -> None:
        self._meins, self._kw = meins, kellerwolke

    def _wolke(self) -> Kellerwolke:
        kw = self._kw()
        if kw is None:
            raise BildFehler("Kellerwolke nicht eingerichtet (Einstellungen, Verbindungen)", 503)
        return kw

    async def anfuegen(self, konto: str, notiz_id: str, name: str, daten: bytes) -> Notiz:
        if len(daten) > HOECHSTENS_BYTES:
            raise BildFehler(f"Das Bild ist zu groß (höchstens {HOECHSTENS_BYTES // (1024 * 1024)} MB)", 413)
        art = art_von(daten)
        if art is None:
            raise BildFehler("Das ist kein Bild in PNG, JPEG, GIF oder WebP")
        if await self._meins.notiz(konto, notiz_id) is None:
            raise BildFehler("Diese Notiz gibt es nicht", 404)
        typ, endung = art
        bild_id = str(uuid.uuid4())
        kw = self._wolke()
        try:
            ordner = await self._ordner(kw, notiz_id)
            await kw.ordner(ordner)
            knoten = await kw.schreiben(f"{ordner}/{bild_id}{endung}", daten, nur_neu=True, inhaltstyp=typ)
        except KellerwolkeFehler as f:
            raise BildFehler(f"Die Kellerwolke nimmt das Bild nicht an: {f}", 503) from f
        bild = Notizbild(id=bild_id, knoten=str(knoten.id), name=(name or f"Bild{endung}")[:200], typ=typ, groesse=len(daten),
                         angelegt=datetime.now(UTC).isoformat(timespec="seconds"))
        notiz = await self._meins.bild_anfuegen(konto, notiz_id, bild)
        if notiz is None:                                   # die Notiz ist inzwischen weg: die Datei auch
            await self._weg(kw, bild.knoten)
            raise BildFehler("Diese Notiz gibt es nicht", 404)
        return notiz

    async def lesen(self, konto: str, notiz_id: str, bild_id: str) -> tuple[Notizbild, AsyncIterator[bytes]]:
        notiz = await self._meins.notiz(konto, notiz_id)
        bild = next((b for b in notiz.bilder if b.id == bild_id), None) if notiz else None
        if bild is None:
            raise BildFehler("Dieses Bild gibt es nicht", 404)
        kw = self._wolke()
        strom = kw.lesen(bild.knoten)
        try:
            erstes = await anext(strom)                     # Fehler der Kellerwolke vor der Antwort, nicht mitten darin
        except StopAsyncIteration:
            erstes = b""
        except NichtGefunden as f:
            raise BildFehler("Das Bild liegt nicht mehr in der Kellerwolke", 404) from f
        except KellerwolkeFehler as f:
            raise BildFehler(f"Die Kellerwolke ist gerade nicht erreichbar: {f}", 503) from f

        async def alles() -> AsyncIterator[bytes]:
            yield erstes
            async for teil in strom:
                yield teil
        return bild, alles()

    async def entfernen(self, konto: str, notiz_id: str, bild_id: str) -> None:
        bild = await self._meins.bild_entfernen(konto, notiz_id, bild_id)
        if bild is None:
            raise BildFehler("Dieses Bild gibt es nicht", 404)
        kw = self._kw()
        if kw is None:
            return
        await self._weg(kw, bild.knoten)
        notiz = await self._meins.notiz(konto, notiz_id)
        if notiz is not None and not notiz.bilder:          # das letzte Bild: kein leerer Ordner bleibt zurück
            await self._ordner_weg(kw, notiz_id)

    async def alle_entfernen(self, notiz: Notiz) -> None:
        """Beim Löschen einer Notiz: ihr Ordner mit den Bildern in den Papierkorb der Kellerwolke (als Ganzes
        wiederherstellbar); fehlt er, die Bilder einzeln."""
        kw = self._kw()
        if kw is None or not notiz.bilder:
            return
        if not await self._ordner_weg(kw, notiz.id):
            for b in notiz.bilder:
                await self._weg(kw, b.knoten)

    @staticmethod
    async def _ordner(kw: Kellerwolke, notiz_id: str) -> str:
        """Der Ordner der Bilder einer Notiz: <Zweig der App>/Notizen/<Notiz>."""
        return f"{(await kw.ich()).zweig}/Notizen/{notiz_id}"

    async def _ordner_weg(self, kw: Kellerwolke, notiz_id: str) -> bool:
        """Den Ordner einer Notiz samt Inhalt in den Papierkorb; False, wenn es ihn nicht gibt oder es nicht ging."""
        try:
            ordner = await kw.finden(await self._ordner(kw, notiz_id))
            if ordner is None:
                return False
            await kw.loeschen(ordner.id)
            return True
        except KellerwolkeFehler:
            return False

    @staticmethod
    async def _weg(kw: Kellerwolke, knoten: str) -> None:
        try:
            await kw.loeschen(knoten)                       # in den Papierkorb, wiederherstellbar
        except NichtGefunden:
            pass
        except KellerwolkeFehler:
            pass                                            # die Notiz zählt; eine liegengebliebene Datei schadet nicht
