"""Übersetzte Suche (WIKI-40, docs/SUCHE.md Punkt 5): eine Frage für englische Quellen ins Englische, über die Leitstelle
(gerechnet wird auf dem Mac). Fachbegriffe, Code, Bezeichner, Namen und Zahlen bleiben, wie sie sind. Einmal übersetzte
Fragen werden gemerkt (für alle Konten gleich); korrigiert der Nutzer eine Übersetzung, gilt seine."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from appkern.app.begleiter import Begleiter
from appkern.datenbank import Datenbank
from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, antwortform, gerade, json_lesen

STUFEN = ["""
CREATE TABLE uebersetzungen (
    frage TEXT NOT NULL,
    ziel  TEXT NOT NULL,
    text  TEXT NOT NULL,
    von   TEXT NOT NULL CHECK (von IN ('modell', 'nutzer')),
    wann  TEXT NOT NULL,
    PRIMARY KEY (frage, ziel)
)
"""]

ANWEISUNG = """Du übersetzt Suchanfragen für die Suche in englischen Nachschlagewerken (Handbücher zu Programmiersprachen,
Frage-und-Antwort-Seiten wie Stack Overflow, Enzyklopädien). Übersetze die Anfrage ins Englische, so wie jemand sie dort
eintippen würde: knapp, mit den üblichen englischen Fachbegriffen, ohne Erklärung.
Unverändert bleiben: Code und Ausdrücke (array_map, :substitute, $var, git rebase -i), Namen von Funktionen, Klassen,
Befehlen, Dateien und Optionen, Namen von Personen, Produkten und Projekten, Zahlen und Versionen.
Ist die Anfrage schon englisch, gib sie unverändert zurück.
Antworte nur mit dem JSON-Objekt {"text": "..."}."""

FORM = antwortform("uebersetzung", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
                                    "additionalProperties": False})


class Uebersetzung(BaseModel):
    frage: str
    ziel: str = "en"
    text: str = ""
    von: Literal["modell", "nutzer", "keine"] = Field(description="keine: gerade nicht übersetzbar, der Grund steht in grund")
    grund: str = ""


class UebersetzungFehlt(Exception):
    """Ohne Leitstelle oder wenn sie nicht antwortet: die Suche läuft dann ohne Übersetzung, mit diesem Grund."""


def _frage(roh: str) -> str:
    return re.sub(r"\s+", " ", roh).strip()


class Uebersetzer(Begleiter):
    def __init__(self, db: Datenbank, leitstelle: Callable[[], Leitstelle | None], modell: Callable[[], str]) -> None:
        self._db, self._leitstelle, self._modell = db, leitstelle, modell

    async def starten(self) -> None:
        await self._db.einrichten("nachschlag_uebersetzung", STUFEN)

    async def _gemerkt(self, frage: str, ziel: str) -> Uebersetzung | None:
        z = await self._db.zeile("SELECT text, von FROM uebersetzungen WHERE frage = ? AND ziel = ?", (frage, ziel))
        return Uebersetzung(frage=frage, ziel=ziel, text=z["text"], von=z["von"]) if z else None

    async def _merken(self, u: Uebersetzung) -> Uebersetzung:
        await self._db.ausfuehren(
            "INSERT INTO uebersetzungen (frage, ziel, text, von, wann) VALUES (?,?,?,?,?) "
            "ON CONFLICT(frage, ziel) DO UPDATE SET text = excluded.text, von = excluded.von, wann = excluded.wann",
            (u.frage, u.ziel, u.text, u.von, datetime.now(timezone.utc).isoformat()))
        return u

    async def uebersetzen(self, roh: str, ziel: str = "en") -> Uebersetzung:
        frage = _frage(roh)
        if gemerkt := await self._gemerkt(frage, ziel):
            return gemerkt
        leitstelle = self._leitstelle()
        if leitstelle is None:
            raise UebersetzungFehlt("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        try:
            antwort = await leitstelle.chat([Nachricht.system(ANWEISUNG), Nachricht.nutzer(frage)], modell=self._modell() or None,
                                            titel="Suche übersetzen", prioritaet="hoch", response_format=FORM, temperature=0)
            text = _frage(gerade(str(json_lesen(antwort.text).get("text", ""))))
        except LeitstellenFehler as f:
            raise UebersetzungFehlt(f"Übersetzung gerade nicht möglich: {f}") from f
        except (ValueError, AttributeError) as f:
            raise UebersetzungFehlt("Die Übersetzung kam unlesbar zurück") from f
        return await self._merken(Uebersetzung(frage=frage, ziel=ziel, text=text or frage, von="modell"))

    async def korrigieren(self, roh: str, text: str, ziel: str = "en") -> Uebersetzung:
        """Die Übersetzung des Nutzers gilt ab jetzt für diese Frage (auch für andere Konten)."""
        return await self._merken(Uebersetzung(frage=_frage(roh), ziel=ziel, text=_frage(text), von="nutzer"))
