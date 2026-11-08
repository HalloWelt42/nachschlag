"""Bilder an Notizen (WIKI-51): eingefügt aus der Zwischenablage oder gewählt aus einer Datei, am Rechner und am
Telefon. Die Dateien liegen in der Ablage der App unter Notizen/<Notiz>/ (Kellerwolke oder Datenordner, WIKI-11), die
Notiz merkt sich ihre Liste mit der Kennung je Datei. Nachschlag liefert sie aus, damit die Oberfläche nur mit der
eigenen Anmeldung auskommt. Erkannt wird die Art am Inhalt, nicht am Namen."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

from appkern.ablage import Ablage, AblageFehler, NichtDa

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
    def __init__(self, meins: Meins, ablage: Callable[[], Ablage]) -> None:
        self._meins, self._ablage = meins, ablage

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
        ablage = self._ablage()
        try:
            datei = await ablage.schreiben(f"{_ordner(notiz_id)}/{bild_id}{endung}", daten, nur_neu=True, inhaltstyp=typ)
        except AblageFehler as f:
            raise BildFehler(f"Das Bild ließ sich nicht ablegen: {f.meldung}", 503) from f
        bild = Notizbild(id=bild_id, knoten=datei.kennung, name=(name or f"Bild{endung}")[:200], typ=typ, groesse=len(daten),
                         angelegt=datetime.now(UTC).isoformat(timespec="seconds"))
        notiz = await self._meins.bild_anfuegen(konto, notiz_id, bild)
        if notiz is None:                                   # die Notiz ist inzwischen weg: die Datei auch
            await _weg(ablage, bild.knoten)
            raise BildFehler("Diese Notiz gibt es nicht", 404)
        return notiz

    async def lesen(self, konto: str, notiz_id: str, bild_id: str) -> tuple[Notizbild, AsyncIterator[bytes]]:
        notiz = await self._meins.notiz(konto, notiz_id)
        bild = next((b for b in notiz.bilder if b.id == bild_id), None) if notiz else None
        if bild is None:
            raise BildFehler("Dieses Bild gibt es nicht", 404)
        strom = self._ablage().lesen(bild.knoten)
        try:
            erstes = await anext(strom)                     # Fehler der Ablage vor der Antwort, nicht mitten darin
        except StopAsyncIteration:
            erstes = b""
        except NichtDa as f:
            raise BildFehler(f"Das Bild liegt nicht mehr in der Ablage: {f.meldung}", 404) from f
        except AblageFehler as f:
            raise BildFehler(f.meldung, 503) from f

        async def alles() -> AsyncIterator[bytes]:
            yield erstes
            async for teil in strom:
                yield teil
        return bild, alles()

    async def entfernen(self, konto: str, notiz_id: str, bild_id: str) -> None:
        bild = await self._meins.bild_entfernen(konto, notiz_id, bild_id)
        if bild is None:
            raise BildFehler("Dieses Bild gibt es nicht", 404)
        ablage = self._ablage()
        await _weg(ablage, bild.knoten)
        notiz = await self._meins.notiz(konto, notiz_id)
        if notiz is not None and not notiz.bilder:          # das letzte Bild: kein leerer Ordner bleibt zurück
            await _ordner_weg(ablage, notiz_id)

    async def alle_entfernen(self, notiz: Notiz) -> None:
        """Beim Löschen einer Notiz: ihr Ordner mit den Bildern (in der Kellerwolke in den Papierkorb, als Ganzes
        wiederherstellbar); fehlt er, die Bilder einzeln."""
        if not notiz.bilder:
            return
        ablage = self._ablage()
        if not await _ordner_weg(ablage, notiz.id):
            for b in notiz.bilder:
                await _weg(ablage, b.knoten)


def _ordner(notiz_id: str) -> str:
    """Der Ordner der Bilder einer Notiz in der Ablage: Notizen/<Notiz>."""
    return f"Notizen/{notiz_id}"


async def _ordner_weg(ablage: Ablage, notiz_id: str) -> bool:
    """Den Ordner einer Notiz samt Inhalt löschen; False, wenn es ihn nicht gibt oder es nicht ging."""
    try:
        return await ablage.weg(_ordner(notiz_id))
    except AblageFehler:
        return False


async def _weg(ablage: Ablage, kennung: str) -> None:
    try:
        await ablage.loeschen(kennung)                      # in der Kellerwolke: in den Papierkorb, wiederherstellbar
    except AblageFehler:
        pass                                                # die Notiz zählt; eine liegengebliebene Datei schadet nicht
