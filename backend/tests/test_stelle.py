"""Markierte Stelle übersetzen (WIKI-47): Ziel und Anweisung gehen mit, Code-Zeilen bleiben, ohne Leitstelle ein Grund."""

from __future__ import annotations

from dataclasses import dataclass

from appkern.leitstelle import NichtErreichbar

from app.uebersetzung import Stellenuebersetzer


@dataclass
class Antwort:
    text: str
    modell: str = "qwen/qwen3-next-80b"


class Leitstelle:
    def __init__(self, text: str = "", fehler: Exception | None = None) -> None:
        self.text, self.fehler, self.aufrufe = text, fehler, []

    async def chat(self, nachrichten, **optionen):
        self.aufrufe.append((nachrichten, optionen))
        if self.fehler:
            raise self.fehler
        return Antwort(self.text)


async def test_stelle_ins_deutsche_mit_zeilen():
    ls = Leitstelle('{"text": "// Prüfen, ob ein Tiername länger als 5 Buchstaben ist.\\nif (x) {}"}')
    u = Stellenuebersetzer(lambda: ls, lambda: "")
    assert u.stand().bereit
    e = await u.uebersetzen("// Check, if any animal name is longer than 5 letters.\nif (x) {}", "de")
    assert e.text == "// Prüfen, ob ein Tiername länger als 5 Buchstaben ist.\nif (x) {}" and e.ziel == "de" and not e.grund
    nachrichten, optionen = ls.aufrufe[0]
    assert "ins Deutsche" in nachrichten[0].inhalt and optionen["prioritaet"] == "hoch"


async def test_ins_englische_und_ohne_leitstelle_ein_grund():
    ls = Leitstelle('{"text": "fox"}')
    assert (await Stellenuebersetzer(lambda: ls, lambda: "").uebersetzen("Fuchs", "en")).text == "fox"
    assert "ins Englische" in ls.aufrufe[0][0][0].inhalt
    ohne = Stellenuebersetzer(lambda: None, lambda: "")
    assert not ohne.stand().bereit and "Leitstelle" in (await ohne.uebersetzen("Fuchs", "de")).grund
    weg = Stellenuebersetzer(lambda: Leitstelle(fehler=NichtErreichbar("schläft")), lambda: "")
    assert "nicht möglich" in (await weg.uebersetzen("Fuchs", "de")).grund
