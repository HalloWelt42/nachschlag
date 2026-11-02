"""Ausprobieren (WIKI-48, Bauplan docs/AUSPROBIEREN.md): Nachschlag rechnet nichts selbst. Es schickt Code und Sprache
über den Verbund an die Codeschmiede, mit seinem App-Schlüssel der Kellerwolke; die Codeschmiede nimmt nur Apps auf
ihrer Erlaubnisliste an und lässt den Code in ihrer Sandbox laufen (ohne Netz, nur lesend, Grenzen). Was sie kann,
sagt sie selbst (Sprachen, bei PHP die Fassungen, ob aufgezeichnet wird). Zurück kommt die Aufzeichnung ihres Debuggers
(Ausgabe, Fehler und je Schritt Zeile, Aufrufstapel und Speicher), bei PHP in der gewählten Fassung; Sprachen ohne
Aufzeichnung laufen nur und bringen Ausgabe, Hinweise und Fehler mit Zeile. Für den Editor nennt sie je PHP-Fassung die eingebauten Funktionen
(WIKI-52). Geht es gerade nicht, ist das ein Zustand mit Grund, kein Fehler."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel

from appkern.verbund import ABFRAGE, Verbund, VerbundFehler

Sprache = Literal["python", "javascript", "php"]

#: so lange gilt das Angebot der Codeschmiede (es ändert sich nur, wenn sie ausgerollt wird)
ANGEBOT_GILT_S = 600


class Sprachangebot(BaseModel):
    sprache: str
    fassungen: list[str] = []          # neueste zuerst; leer: eine Fassung
    aufzeichnen: bool = False          # ob der Debugger den Lauf aufzeichnet (sonst nur ausführen)


class Ausprobierstand(BaseModel):
    bereit: bool
    sprachen: list[Sprachangebot] = []
    grund: str = ""


class Probelauf(BaseModel):
    """Die Aufzeichnung der Codeschmiede, wie sie kommt (ausgabe, fehler, fehlerzeile, schritte, gekuerzt; ohne
    Aufzeichnung leere Schritte und dazu hinweise), oder der Grund, warum es gerade nicht ging."""
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


KEINE_ADRESSE = "Keine Codeschmiede eingetragen (Einstellungen, Verbindungen)"


class Ausprobieren:
    def __init__(self, verbund: Callable[[], Verbund], adresse: Callable[[], str]) -> None:
        self._verbund, self._adresse = verbund, adresse
        self._angebot: tuple[float, str, list[Sprachangebot]] | None = None     # (geholt, Adresse, Angebot)
        self._funktionen: dict[str, list[str]] = {}

    def _ziel(self) -> str:
        return self._adresse().strip().rstrip("/")

    async def stand(self) -> Ausprobierstand:
        adresse = self._ziel()
        if not adresse:
            return Ausprobierstand(bereit=False, grund=KEINE_ADRESSE)
        try:
            return Ausprobierstand(bereit=True, sprachen=await self._sprachen(adresse))
        except VerbundFehler as f:
            return Ausprobierstand(bereit=False, grund=_grund(f))

    async def _sprachen(self, adresse: str) -> list[Sprachangebot]:
        if self._angebot and self._angebot[1] == adresse and time.monotonic() - self._angebot[0] < ANGEBOT_GILT_S:
            return self._angebot[2]
        antwort = await self._verbund().anfrage("GET", adresse, "/api/v1/sandbox/sprachen", timeout=ABFRAGE)
        angebot = [Sprachangebot.model_validate(s) for s in antwort.json()]
        self._angebot = (time.monotonic(), adresse, angebot)
        return angebot

    async def laufen(self, code: str, sprache: Sprache, fassung: str, eingabe: list[str]) -> Probelauf:
        adresse = self._ziel()
        if not adresse:
            return Probelauf(grund=KEINE_ADRESSE)
        try:
            angebot = {s.sprache: s for s in await self._sprachen(adresse)}
            if sprache not in angebot:
                return Probelauf(grund=f"Die Sandbox der Codeschmiede kann {sprache} nicht ausführen")
            if angebot[sprache].aufzeichnen:
                antwort = await self._verbund().anfrage("POST", adresse, "/api/v1/sandbox/aufzeichnen",
                                                        json={"code": code, "sprache": sprache, "eingabe": eingabe,
                                                              **({"fassung": fassung} if fassung else {})})
                return Probelauf(aufzeichnung=antwort.json())
            antwort = await self._verbund().anfrage("POST", adresse, "/api/v1/sandbox/ausfuehren",
                                                    json={"code": code, "sprache": sprache, "fassung": fassung})
            return Probelauf(aufzeichnung={**antwort.json(), "schritte": []})
        except VerbundFehler as f:
            return Probelauf(grund=_grund(f))

    async def funktionen(self) -> dict[str, list[str]]:
        """Je PHP-Fassung die eingebauten Funktionen; gemerkt, sobald alle Fassungen geantwortet haben."""
        adresse = self._ziel()
        if not adresse:
            return {}
        try:
            angebot = {s.sprache: s for s in await self._sprachen(adresse)}
            fassungen = angebot["php"].fassungen if "php" in angebot else []
            if fassungen and all(f in self._funktionen for f in fassungen):
                return {f: self._funktionen[f] for f in fassungen}
            antwort = await self._verbund().anfrage("GET", adresse, "/api/v1/sandbox/funktionen/php")
            self._funktionen.update(antwort.json())
            return {f: self._funktionen[f] for f in fassungen if f in self._funktionen}
        except VerbundFehler:
            return {}                       # ohne Bestand prüft der Editor nur die Schreibweise
