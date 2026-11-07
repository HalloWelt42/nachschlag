"""Stapelarbeit je Sammlung (WIKI-44): Nachtfenster und Zurückstellen, Zusammenfassen mit Überblick, Lernfragen und
Vertonen mit Wiedergabeliste; Ergebnisse in der Kellerwolke unter Apps/<App>/Sammlungen/<Thema>/ und am Thema."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest

from appkern.auftraege import Auftraege
from appkern.datenbank import Datenbank

from app.einstellungen import TEXTMODELL
from app.modell.artikel import Artikel
from app.modell.buch import Buch, Faehigkeiten
from app.modell.themen import Thema, Themeneintrag
from app.sammlung.dienst import ZONE, Sammlungen, nachts, ordnername


def test_nachtfenster_ueber_mitternacht_und_ordnername():
    stunde = lambda h: datetime(2026, 11, 2, h, 0, tzinfo=ZONE)  # noqa: E731
    assert [nachts(stunde(h), 22, 7) for h in (21, 22, 3, 6, 7, 12)] == [False, True, True, True, False, False]
    assert [nachts(stunde(h), 1, 5) for h in (0, 1, 4, 5)] == [False, True, True, False]
    assert ordnername("Füchse / Wölfe:\\nNacht") == "Füchse Wölfe nNacht"


BUCH = Buch(kennung="probe_de_all_2026-01", name="probe_de_all", titel="Probe", sprache="deu", art="enzyklopaedie",
            eintraege=1, artikel=1, medien=0, groesse=1, faehigkeiten=Faehigkeiten(titelindex=True, volltext=True, bilder=False,
                                                                                    lesedesign=True))
THEMA = Thema(id="t1", titel="Füchse", angelegt="2026-11-02", eintraege=[
    Themeneintrag(id="e1", buch_name="probe_de_all", buch=BUCH.kennung, pfad="Rotfuchs", titel="Rotfuchs", platz=0),
    Themeneintrag(id="e2", buch_name="probe_de_all", buch=BUCH.kennung, pfad="Polarfuchs", titel="Polarfuchs", platz=1),
    Themeneintrag(id="e3", buch_name="weg", buch="", pfad="Fehlt", titel="Fehlt", platz=2)])


class Themen:
    async def thema(self, konto, kennung):
        return THEMA if kennung == "t1" else None


class Bib:
    async def buch(self, kennung):
        return BUCH


class Leser:
    async def lesen(self, buch, pfad):
        return Artikel(buch=buch, pfad=pfad, angefragt=pfad, titel=pfad, darstellung="lesedesign", baustein="enzyklopaedie",
                       original="/o", html=f"<h2>Merkmale</h2><p>Der {pfad} ist ein Fuchs.</p><pre>code()</pre>")


class Artikel_:
    async def abgelegt(self, buch, pfad):
        return None


@dataclass
class Antwort:
    text: str


class Leitstelle:
    def __init__(self) -> None:
        self.aufrufe: list = []

    async def chat(self, nachrichten, **optionen):
        self.aufrufe.append((nachrichten, optionen))
        name = optionen["response_format"]["json_schema"]["name"]
        if name == "karten":
            return Antwort(json.dumps({"karten": [{"frage": "Was ist er?", "antwort": "Ein Fuchs."}]}))
        return Antwort(json.dumps({"text": f"Kurz: {nachrichten[1].inhalt[:20]}"}))


@dataclass
class Knoten:
    etag: str


class Kellerwolke:
    def __init__(self) -> None:
        self.dateien: dict[str, bytes] = {}

    async def ich(self):
        return type("Ich", (), {"zweig": "Apps/Nachschlag"})()

    async def ordner(self, pfad):
        return None

    async def finden(self, pfad):
        return Knoten("e") if pfad in self.dateien else None

    async def schreiben(self, pfad, inhalt, *, stand=None, inhaltstyp=None):
        assert (pfad in self.dateien) == (stand is not None)          # Überschreiben nur mit Stand
        self.dateien[pfad] = inhalt


def wav() -> bytes:
    puffer = io.BytesIO()
    with wave.open(puffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(b"\0\0" * 2400)
    return puffer.getvalue()


class Sprecher:
    def __init__(self) -> None:
        self.texte: list[str] = []

    async def zeilen(self, text, sprache):
        self.texte.append(text)
        yield json.dumps({"art": "satz", "nr": 0, "text": text, "dauer_ms": 100, "ton": base64.b64encode(wav()).decode()}).encode()
        yield json.dumps({"art": "ende", "saetze": 1, "dauer_ms": 100}).encode()


@pytest.fixture
async def db(tmp_path: Path):
    d = await Datenbank(tmp_path / "s.sqlite").oeffnen()
    yield d
    await d.schliessen()


async def dienst(db, uhr=lambda: datetime(2026, 11, 2, 12, 0, tzinfo=ZONE)):
    auftraege = Auftraege(db, [], gleichzeitig=3)
    kw, ls, sprecher = Kellerwolke(), Leitstelle(), Sprecher()
    s = Sammlungen(db, auftraege, Themen(), Bib(), Leser(), Artikel_(), lambda stimme: sprecher, lambda: ls, lambda: TEXTMODELL,
                   lambda: kw, lambda: (22, 7), uhr=uhr)
    await s.starten()
    await auftraege.starten()
    return s, auftraege, kw, ls, sprecher


async def bis_fertig(s: Sammlungen, arbeiten: int):
    for _ in range(500):
        stand = await s.stand("k", "t1")
        if not stand.auftraege and len(stand.ergebnisse) >= arbeiten:
            return stand
        await asyncio.sleep(0.01)
    raise AssertionError(stand)


async def test_zusammenfassen_lernfragen_vertonen_in_die_kellerwolke(db):
    s, auftraege, kw, ls, sprecher = await dienst(db)
    try:
        await s.anstossen("k", "Probe", "t1", ["zusammenfassen", "lernfragen", "vertonen"], None, "jetzt", "", "opus")
        stand = await bis_fertig(s, 3)
        wurzel = "Apps/Nachschlag/Sammlungen/Füchse"
        assert set(kw.dateien) == {f"{wurzel}/Zusammenfassung.md", f"{wurzel}/Lernfragen.md", f"{wurzel}/Hören/01 Rotfuchs.opus",
                                   f"{wurzel}/Hören/02 Polarfuchs.opus", f"{wurzel}/Hören/Thema anhören.m3u"}
        zusammen = kw.dateien[f"{wurzel}/Zusammenfassung.md"].decode()
        assert zusammen.startswith("# Füchse: Zusammenfassung\n\n## Überblick") and "### Polarfuchs" in zusammen
        assert "**Frage:** Was ist er?" in kw.dateien[f"{wurzel}/Lernfragen.md"].decode()
        assert kw.dateien[f"{wurzel}/Hören/Thema anhören.m3u"].decode() == "#EXTM3U\n01 Rotfuchs.opus\n02 Polarfuchs.opus\n"
        assert kw.dateien[f"{wurzel}/Hören/01 Rotfuchs.opus"][:4] == b"OggS"
        assert sprecher.texte[0] == "Rotfuchs.\nMerkmale\nDer Rotfuchs ist ein Fuchs."      # Code bleibt draußen
        assert {e.arbeit for e in stand.ergebnisse} == {"zusammenfassen", "lernfragen", "vertonen"}
        assert all(o["prioritaet"] == "hintergrund" and o["modell"] == TEXTMODELL for _, o in ls.aufrufe)
        await s.anstossen("k", "Probe", "t1", ["zusammenfassen"], None, "jetzt", "", "opus")    # noch einmal: neue Fassung
        await bis_fertig(s, 3)
    finally:
        await s.stoppen()
        await auftraege.stoppen()


async def test_heute_nacht_wartet_bis_zum_fenster(db):
    uhr = {"jetzt": datetime(2026, 11, 2, 12, 0, tzinfo=ZONE)}
    s, auftraege, kw, *_ = await dienst(db, uhr=lambda: uhr["jetzt"])
    try:
        stand = await s.anstossen("k", "Probe", "t1", ["lernfragen"], None, "nachts", "", "opus")
        await asyncio.sleep(0.1)
        stand = await s.stand("k", "t1")
        assert stand.auftraege[0].zustand == "wartet" and stand.auftraege[0].zurueckgestellt == "wartet auf die Nacht (22 bis 7 Uhr)"
        uhr["jetzt"] = datetime(2026, 11, 2, 23, 0, tzinfo=ZONE)
        auftraege.wecken()
        await bis_fertig(s, 1)
        assert any(p.endswith("Lernfragen.md") for p in kw.dateien)
    finally:
        await s.stoppen()
        await auftraege.stoppen()
