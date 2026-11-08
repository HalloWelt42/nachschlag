"""Ablage für Proben, nur im Speicher (WIKI-11): wie `appkern.ablage`, Kennung ist der Pfad; der Ort für Menschen wie
in der Kellerwolke (Apps/Nachschlag/...). `dateien` und `geloescht` zeigen, was geschah."""

from __future__ import annotations

from collections.abc import AsyncIterator

from appkern.ablage import Ablage, AblageArt, AblageFehler, Eintrag, NichtDa, teile


class Speicher(Ablage):
    art: AblageArt = "kellerwolke"
    name = "Kellerwolke"

    def __init__(self) -> None:
        self.dateien: dict[str, bytes] = {}
        self.geloescht: list[str] = []
        self.weg_ist_sie = False                     # wie eine Kellerwolke, die gerade nicht antwortet

    def _pruefen(self) -> None:
        if self.weg_ist_sie:
            raise AblageFehler("Die Kellerwolke antwortet nicht")

    @staticmethod
    def _eintrag(pfad: str, daten: bytes | None) -> Eintrag:
        return Eintrag(kennung=pfad, pfad=pfad, name=pfad.rsplit("/", 1)[-1], ordner=daten is None,
                       groesse=len(daten or b""), stand=str(len(daten or b"")))

    async def ort(self, pfad: str = "") -> str:
        return "/".join(["Apps/Nachschlag", *teile(pfad)])

    async def schreiben(self, pfad: str, daten: bytes, *, inhaltstyp: str, nur_neu: bool = False) -> Eintrag:
        self._pruefen()
        pfad = "/".join(teile(pfad))
        if nur_neu and pfad in self.dateien:
            raise AblageFehler(f"{pfad} gibt es schon")
        self.dateien[pfad] = daten
        return self._eintrag(pfad, daten)

    async def finden(self, pfad: str) -> Eintrag | None:
        self._pruefen()
        pfad = "/".join(teile(pfad))
        if pfad in self.dateien:
            return self._eintrag(pfad, self.dateien[pfad])
        return self._eintrag(pfad, None) if any(p.startswith(f"{pfad}/") for p in self.dateien) else None

    async def lesen(self, kennung: str) -> AsyncIterator[bytes]:
        self._pruefen()
        if kennung not in self.dateien:
            raise NichtDa("Die Datei liegt nicht mehr in der Kellerwolke")
        yield self.dateien[kennung]

    async def liste(self, ordner: str) -> list[Eintrag]:
        self._pruefen()
        vorn = "/".join(teile(ordner))
        namen = {p[len(vorn) + 1:].split("/", 1)[0] for p in self.dateien if p.startswith(f"{vorn}/")}
        return sorted((self._eintrag(f"{vorn}/{n}", self.dateien.get(f"{vorn}/{n}")) for n in namen),
                      key=lambda e: (not e.ordner, e.name.casefold()))

    async def loeschen(self, kennung: str) -> bool:
        self._pruefen()
        weg = [p for p in self.dateien if p == kennung or p.startswith(f"{kennung}/")]
        for p in weg:
            del self.dateien[p]
        self.geloescht += weg
        return bool(weg)
