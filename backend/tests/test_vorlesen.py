"""Vorlesen über den Sprechdienst der Leitstelle (WIKI-43): Satz für Satz als Strom mit Ton, Sprache des Texts und
Stimme gehen mit; ohne Leitstelle, ohne Freigabe oder bei Fehlern vor dem ersten Satz ein Grund statt eines Stroms."""

from __future__ import annotations

import base64
import io
import json
import wave
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest

from appkern.leitstelle import NichtErreichbar

from app.vorlesen import NichtBereit, Sprechdienst
from app.vorlesen.sprechdienst import dauer_ms
from app.vorlesen.stimmen import NichtFreigegeben, Referenz


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
        if weg == "/tts/clone":
            self.ls.aufrufe.append((methode, weg, optionen))
            return {"filename": "satz.wav"}
        return {"speakers": ["serena", "aiden"], "languages": ["german", "english"]}

    @asynccontextmanager
    async def gebunden(self):
        self.ls.gebunden += 1
        yield None


class Leitstelle:
    """Nachgestellt: gibt die Dienste frei, die in `frei` stehen; `fehler_ab`: ab so vielen Aufrufen scheitert es."""

    def __init__(self, frei=("klangwerk-sprechen",), fehler_ab: int | None = None) -> None:
        self.frei, self.fehler_ab = frei, fehler_ab
        self.aufrufe: list = []
        self.dienstname = ""
        self.gebunden = 0

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


class Stimmen:
    """Nachgestellte Vertonung: gibt die Stimme "s1" frei, alle anderen nicht."""

    async def referenz(self, stimme_id: str) -> Referenz:
        if stimme_id != "s1":
            raise NichtFreigegeben("Diese Stimme gibt die Vertonung für Nachschlag nicht frei")
        return Referenz(id="s1", ton=wav(500), text="Probe der Hausstimme.", sprache="de")


async def test_eigene_stimme_spricht_der_klondienst_mit_der_probe():
    ls = Leitstelle(frei=("klangwerk-sprechen", "klangwerk-klonen"))
    s = Sprechdienst(lambda: ls, lambda: "klangwerk-sprechen", lambda: "privat:s1", lambda: "klangwerk-klonen", Stimmen())
    await s.pruefen()
    zeilen = await alle(s, "Der Rotfuchs jagt.", "de")
    assert [z["art"] for z in zeilen] == ["satz", "ende"]
    clone, audio = ls.aufrufe[0], ls.aufrufe[1]
    assert (clone[1], ls.dienstname, ls.gebunden) == ("/tts/clone", "klangwerk-klonen", 1)
    assert clone[2]["data"] == {"text": "Der Rotfuchs jagt.", "ref_text": "Probe der Hausstimme.", "language": "german", "modus": "icl"}
    assert clone[2]["files"]["ref_audio"][1] == wav(500)
    assert audio[:2] == ("GET", "/tts/audio/satz.wav")
    assert (await alle(s, "It hunts.", "en"))[0]["art"] == "satz"
    assert ls.aufrufe[2][2]["data"]["modus"] == "abdruck"          # andere Sprache als die Probe: nur der Stimmabdruck


async def test_eigene_stimme_ohne_freigabe_oder_klondienst_ein_grund():
    ls = Leitstelle(frei=("klangwerk-sprechen",))
    s = Sprechdienst(lambda: ls, lambda: "klangwerk-sprechen", lambda: "privat:s1", lambda: "klangwerk-klonen", Stimmen())
    with pytest.raises(NichtBereit, match="Klondienst"):
        await s.pruefen()
    fremd = Sprechdienst(lambda: Leitstelle(frei=("klangwerk-sprechen", "klangwerk-klonen")), lambda: "klangwerk-sprechen",
                         lambda: "privat:fremd", lambda: "klangwerk-klonen", Stimmen())
    with pytest.raises(NichtBereit, match="nicht frei") as f:
        await alle(fremd, "Satz.")
    assert f.value.status == 403
