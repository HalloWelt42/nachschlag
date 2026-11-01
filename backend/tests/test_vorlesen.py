"""Vorlesen über den Sprechdienst der Leitstelle (WIKI-43): Satz für Satz als Strom mit Ton, Sprache des Texts und
Stimme gehen mit; ohne Leitstelle, ohne Freigabe oder bei Fehlern vor dem ersten Satz ein Grund statt eines Stroms."""

from __future__ import annotations

import base64
import io
import json
import wave
from dataclasses import dataclass

import pytest

from appkern.leitstelle import NichtErreichbar

from app.vorlesen import NichtBereit, Sprechdienst
from app.vorlesen.sprechdienst import dauer_ms


def wav(ms: int = 250) -> bytes:
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * (24 * ms))
    return puffer.getvalue()


@dataclass
class Antwort:
    content: bytes


@dataclass
class Eintrag:
    kennung: str


class Dienst:
    def __init__(self, leitstelle: "Leitstelle") -> None:
        self.ls = leitstelle

    async def anfrage(self, methode, weg, **optionen):
        self.ls.aufrufe.append((methode, weg, optionen))
        if self.ls.fehler_ab is not None and len(self.ls.aufrufe) > self.ls.fehler_ab:
            raise NichtErreichbar("Sprechdienst schläft")
        return Antwort(wav())

    async def json(self, methode, weg, **optionen):
        return {"speakers": ["serena", "aiden"], "languages": ["german", "english"]}


class Leitstelle:
    """Nachgestellt: gibt die Dienste frei, die in `frei` stehen; `fehler_ab`: ab so vielen Aufrufen scheitert es."""

    def __init__(self, frei=("klangwerk-sprechen",), fehler_ab: int | None = None) -> None:
        self.frei, self.fehler_ab = frei, fehler_ab
        self.aufrufe: list = []
        self.dienstname = ""

    async def dienste(self):
        return [Eintrag(k) for k in self.frei]

    def dienst(self, name: str) -> Dienst:
        self.dienstname = name
        return Dienst(self)


async def alle(sprechdienst: Sprechdienst, text: str, sprache: str = "de") -> list[dict]:
    return [json.loads(z) async for z in sprechdienst.zeilen(text, sprache)]


async def test_satz_fuer_satz_mit_ton_sprache_und_stimme():
    ls = Leitstelle()
    s = Sprechdienst(lambda: ls, lambda: "klangwerk-sprechen", lambda: "serena")
    await s.pruefen()
    zeilen = await alle(s, "Der Rotfuchs jagt. Er frisst Mäuse!\n\nNeuer Absatz.", "de")
    assert [z["art"] for z in zeilen] == ["satz", "satz", "satz", "ende"]
    assert [z["text"] for z in zeilen[:3]] == ["Der Rotfuchs jagt.", "Er frisst Mäuse!", "Neuer Absatz."]
    assert [z["nr"] for z in zeilen[:3]] == [0, 1, 2]
    assert dauer_ms(base64.b64decode(zeilen[0]["ton"])) == 250 and zeilen[-1]["dauer_ms"] == 750
    methode, weg, optionen = ls.aufrufe[0]
    assert (methode, weg, ls.dienstname) == ("POST", "/v1/audio/speech", "klangwerk-sprechen")
    assert optionen["json"] == {"input": "Der Rotfuchs jagt.", "response_format": "wav", "voice": "serena", "language": "german"}
    assert await s.katalog() == ["aiden", "serena"]


async def test_englischer_text_ohne_stimme_nimmt_die_vorgabe():
    ls = Leitstelle()
    s = Sprechdienst(lambda: ls, lambda: "klangwerk-sprechen", lambda: "")
    await alle(s, "Applies the callback.", "en")
    assert ls.aufrufe[0][2]["json"] == {"input": "Applies the callback.", "response_format": "wav", "language": "english"}


@pytest.mark.parametrize("leitstelle, dienst, grund, status", [
    (None, "klangwerk-sprechen", "Leitstelle nicht eingerichtet", 503),
    (Leitstelle(), "", "Kein Sprechdienst", 503),
    (Leitstelle(frei=("klangwerk-hoeren",)), "klangwerk-sprechen", "nicht frei", 403),
])
async def test_nicht_bereit_mit_grund(leitstelle, dienst, grund, status):
    s = Sprechdienst(lambda: leitstelle, lambda: dienst, lambda: "")
    with pytest.raises(NichtBereit, match=grund) as f:
        await s.pruefen()
    assert f.value.status == status


async def test_fehler_vor_dem_ersten_satz_ist_ein_grund_danach_eine_zeile():
    s = Sprechdienst(lambda: Leitstelle(fehler_ab=0), lambda: "klangwerk-sprechen", lambda: "")
    with pytest.raises(NichtBereit, match="nicht möglich"):
        await alle(s, "Eins. Zwei.")
    s = Sprechdienst(lambda: Leitstelle(fehler_ab=1), lambda: "klangwerk-sprechen", lambda: "")
    zeilen = await alle(s, "Eins. Zwei.")
    assert [z["art"] for z in zeilen] == ["satz", "fehler"] and "brach ab" in zeilen[1]["meldung"]
