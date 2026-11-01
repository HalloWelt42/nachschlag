"""Übersetzte Suche (WIKI-40): Übersetzung über die Leitstelle, gemerkt; Korrektur des Nutzers gilt; ohne Leitstelle ein
Grund statt eines Fehlers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from appkern.datenbank import Datenbank
from appkern.leitstelle import NichtErreichbar

from app.uebersetzung import Uebersetzer, UebersetzungFehlt


@dataclass
class Antwort:
    text: str


class Leitstelle:
    """Nachgestellt: zählt die Aufrufe und antwortet wie ein Modell mit fester Antwortform."""

    def __init__(self, text: str = '{"text": "copy text to the clipboard"}', fehler: Exception | None = None) -> None:
        self.aufrufe: list[dict] = []
        self._text, self._fehler = text, fehler

    async def chat(self, nachrichten, **optionen) -> Antwort:
        self.aufrufe.append({"nachrichten": nachrichten, **optionen})
        if self._fehler:
            raise self._fehler
        return Antwort(self._text)


@pytest.fixture
async def db(tmp_path: Path):
    d = await Datenbank(tmp_path / "u.sqlite").oeffnen()
    yield d
    await d.schliessen()


async def test_uebersetzt_einmal_und_merkt(db):
    leitstelle = Leitstelle()
    u = Uebersetzer(db, lambda: leitstelle, lambda: "")
    await u.starten()
    erste = await u.uebersetzen("  Text in die   Zwischenablage kopieren ")
    assert (erste.frage, erste.text, erste.von) == ("Text in die Zwischenablage kopieren", "copy text to the clipboard", "modell")
    assert leitstelle.aufrufe[0]["prioritaet"] == "hoch" and leitstelle.aufrufe[0]["modell"] is None
    assert (await u.uebersetzen("Text in die Zwischenablage kopieren")).text == "copy text to the clipboard"
    assert len(leitstelle.aufrufe) == 1                                        # gemerkt, kein zweiter Aufruf

    korrigiert = await u.korrigieren("Text in die Zwischenablage kopieren", "yank to system clipboard")
    assert korrigiert.von == "nutzer"
    assert (await u.uebersetzen("Text in die Zwischenablage kopieren")).text == "yank to system clipboard"


async def test_ohne_leitstelle_ein_grund(db):
    u = Uebersetzer(db, lambda: None, lambda: "")
    await u.starten()
    with pytest.raises(UebersetzungFehlt, match="Leitstelle nicht eingerichtet"):
        await u.uebersetzen("Fuchs")
    weg = Uebersetzer(db, lambda: Leitstelle(fehler=NichtErreichbar("Leitstelle antwortet nicht")), lambda: "")
    with pytest.raises(UebersetzungFehlt, match="nicht möglich"):
        await weg.uebersetzen("Fuchs")
    unlesbar = Uebersetzer(db, lambda: Leitstelle(text="kein json"), lambda: "")
    with pytest.raises(UebersetzungFehlt, match="unlesbar"):
        await unlesbar.uebersetzen("Dachs")


async def test_typografie_wird_gerade(db):
    u = Uebersetzer(db, lambda: Leitstelle(text='{"text": "fox ' + chr(0x2013) + ' red"}'), lambda: "qwen")
    await u.starten()
    assert chr(0x2013) not in (await u.uebersetzen("Rotfuchs")).text
