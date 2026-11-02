"""Ausprobieren (WIKI-48, Bauplan docs/AUSPROBIEREN.md): Nachschlag rechnet nichts selbst. Es schickt Code und Sprache
über den Verbund an die Codeschmiede, mit seinem App-Schlüssel der Kellerwolke; die Codeschmiede nimmt nur Apps auf
ihrer Erlaubnisliste an und lässt den Code in ihrer Sandbox laufen (ohne Netz, nur lesend, Grenzen). Zurück kommt die
Aufzeichnung ihres Debuggers: Ausgabe, Fehler und je Schritt Zeile, Aufrufstapel und Speicher. Geht es gerade nicht,
ist das ein Zustand mit Grund, kein Fehler."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from appkern.verbund import ABFRAGE, Verbund, VerbundFehler

#: was die Sandbox der Codeschmiede heute aufzeichnen kann (PHP folgt mit eigenem Abbild)
SPRACHEN = ("python", "javascript")
Sprache = Literal["python", "javascript"]


class Ausprobierstand(BaseModel):
    bereit: bool
    sprachen: list[str] = []
    grund: str = ""


class Probelauf(BaseModel):
    """Die Aufzeichnung der Codeschmiede, wie sie kommt (ausgabe, fehler, fehlerzeile, schritte, gekuerzt), oder der
    Grund, warum es gerade nicht ging."""
    aufzeichnung: dict[str, Any] | None = None
    grund: str = ""


def _grund(f: VerbundFehler) -> str:
    if f.status is None:
        return f"Die Codeschmiede ist gerade nicht erreichbar ({f.meldung})"
    if f.status in (401, 403):
        return f"Die Codeschmiede lässt Nachschlag nicht zu: {f.meldung}"
    if f.status == 429:
        return "Es läuft schon ein Probelauf; gleich noch einmal"
    return f"Die Codeschmiede meldet: {f.meldung}"


class Ausprobieren:
    def __init__(self, verbund: Callable[[], Verbund], adresse: Callable[[], str]) -> None:
        self._verbund, self._adresse = verbund, adresse

    def stand(self) -> Ausprobierstand:
        if not self._adresse().strip():
            return Ausprobierstand(bereit=False, grund="Keine Codeschmiede eingetragen (Einstellungen, Verbindungen)")
        return Ausprobierstand(bereit=True, sprachen=list(SPRACHEN))

    async def laufen(self, code: str, sprache: Sprache, eingabe: list[str]) -> Probelauf:
        adresse = self._adresse().strip().rstrip("/")
        if not adresse:
            return Probelauf(grund="Keine Codeschmiede eingetragen (Einstellungen, Verbindungen)")
        try:
            antwort = await self._verbund().anfrage("POST", adresse, "/api/v1/sandbox/aufzeichnen",
                                                    json={"code": code, "sprache": sprache, "eingabe": eingabe})
        except VerbundFehler as f:
            return Probelauf(grund=_grund(f))
        return Probelauf(aufzeichnung=antwort.json())
