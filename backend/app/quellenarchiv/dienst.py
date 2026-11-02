"""Archiv der Quellen (WIKI-46, geklärt im Gespräch 02.11.2026). Ältere Fassungen derselben Quelle (gleicher Name,
früherer Stand) liegen von selbst im Archiv; dazu lässt sich jede Quelle von Hand archivieren. Archiviert ist nur ein
Kennzeichen, die Datei bleibt, wo sie liegt. Ohne "mitnutzen" fehlt eine archivierte Quelle in Suche, Vorschlägen,
Stöbern, Startseite und beim Bau eigener Indizes; über Verweise, Merkzettel und Notizen bleibt sie lesbar.

Gespeichert wird nur, was von Hand entschieden ist (archiviert, wieder aktiv, mitnutzen); dass eine Fassung ersetzt ist,
ergibt sich jedes Mal neu aus der Bibliothek. Eine Wahrheit für alle Konten (die Bibliothek ist gemeinsam)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from appkern.app.begleiter import Begleiter
from appkern.datenbank import Datenbank

from ..bibliothek import Bibliothek
from ..modell.buch import Archivstand, Bibliotheksstand, Buch

STUFEN = ["""
CREATE TABLE quellenarchiv (
    kennung   TEXT PRIMARY KEY,
    zustand   TEXT CHECK (zustand IN ('archiv', 'aktiv')),
    mitnutzen INTEGER NOT NULL DEFAULT 0,
    geaendert TEXT NOT NULL
)
"""]

Zustand = Literal["archiv", "aktiv"]


def einordnen(buecher: list[Buch], entscheidungen: dict[str, tuple[str | None, bool]]) -> list[Buch]:
    """Jede Quelle mit ihrem Archivstand. Die neueste Fassung je Name ersetzt die älteren; "aktiv" von Hand hebt das
    auf, "archiv" von Hand archiviert auch die neueste."""
    neueste: dict[str, Buch] = {}
    for b in buecher:
        if b.name not in neueste or (b.stand, b.kennung) > (neueste[b.name].stand, neueste[b.name].kennung):
            neueste[b.name] = b
    aus = []
    for b in buecher:
        zustand, mitnutzen = entscheidungen.get(b.kennung, (None, False))
        stand = None
        if zustand == "archiv":
            stand = Archivstand(grund="von_hand", mitnutzen=mitnutzen)
        elif zustand != "aktiv" and neueste[b.name].kennung != b.kennung:
            stand = Archivstand(grund="ersetzt", ersetzt_durch=neueste[b.name].kennung, mitnutzen=mitnutzen)
        aus.append(b.model_copy(update={"archiv": stand}))
    return aus


def nutzbar(b: Buch) -> bool:
    """Zählt in Suche, Stöbern und Startseite mit: aktiv oder im Archiv mit "mitnutzen"."""
    return b.archiv is None or b.archiv.mitnutzen


class Quellenarchiv(Begleiter):
    def __init__(self, db: Datenbank, bibliothek: Bibliothek) -> None:
        self._db, self._bib = db, bibliothek

    async def starten(self) -> None:
        await self._db.einrichten("nachschlag_quellenarchiv", STUFEN)

    async def _entscheidungen(self) -> dict[str, tuple[str | None, bool]]:
        return {z["kennung"]: (z["zustand"], bool(z["mitnutzen"]))
                for z in await self._db.zeilen("SELECT kennung, zustand, mitnutzen FROM quellenarchiv")}

    async def stand(self) -> Bibliotheksstand:
        """Die Bibliothek mit dem Archivstand jeder Quelle."""
        s = await self._bib.stand()
        return s.model_copy(update={"buecher": einordnen(s.buecher, await self._entscheidungen())})

    async def buch(self, kennung: str) -> Buch:
        """Eine Quelle mit ihrem Archivstand; `BuchFehlt`, wenn es sie nicht gibt."""
        await self._bib.buch(kennung)
        return next(b for b in (await self.stand()).buecher if b.kennung == kennung)

    async def nutzbare(self) -> list[Buch]:
        """Die Quellen für Suche und Vorschläge: aktive zuerst, mitgenutzte aus dem Archiv dahinter."""
        buecher = [b for b in (await self.stand()).buecher if nutzbar(b)]
        return sorted(buecher, key=lambda b: b.archiv is not None)

    async def setzen(self, kennung: str, zustand: Zustand | None, mitnutzen: bool | None) -> Buch:
        """`zustand`: archiv, aktiv oder None (wie von selbst); `mitnutzen` None lässt es, wie es ist."""
        await self._bib.buch(kennung)                           # BuchFehlt, wenn es die Quelle nicht gibt
        alt = (await self._entscheidungen()).get(kennung, (None, False))
        neu = (zustand, alt[1] if mitnutzen is None else mitnutzen)
        await self._db.ausfuehren(
            "INSERT INTO quellenarchiv (kennung, zustand, mitnutzen, geaendert) VALUES (?,?,?,?) "
            "ON CONFLICT(kennung) DO UPDATE SET zustand = excluded.zustand, mitnutzen = excluded.mitnutzen, "
            "geaendert = excluded.geaendert", (kennung, neu[0], int(neu[1]), datetime.now(timezone.utc).isoformat()))
        return await self.buch(kennung)
