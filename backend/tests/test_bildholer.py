"""Bildholer (WIKI-80): vormerken mit Vorrang (geöffnet springt nach vorn), Angaben bei der Bildquelle in einem Stapel,
Bild und Angaben in die Ablage, Fehlendes nicht wieder vormerken, Drosselung macht langsamer oder hält an, Nachtregel,
Platzgrenze."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import httpx
import pytest

from bildholer import ablage
from bildholer.api import app_bauen
from bildholer.arbeiter import Arbeiter, in_der_nacht
from bildholer.modelle import Regeln
from bildholer.quelle import Bildquelle
from bildholer.schlange import Schlange

QUELLE = "de.wikipedia.org"


def _api(anfrage: httpx.Request) -> dict:
    titel = anfrage.url.params["titles"].split("|")
    seiten = []
    for t in titel:
        name = t.removeprefix("File:")
        if name == "Fehlt.jpg":
            seiten.append({"title": "Datei:" + name.replace("_", " "), "missing": True})
            continue
        seiten.append({"title": "Datei:" + name.replace("_", " "), "imageinfo": [{
            "width": 4000, "height": 2000, "thumburl": f"https://upload.example/thumb/{name}", "thumbwidth": 1280,
            "thumbheight": 640, "url": f"https://upload.example/{name}", "mime": "image/jpeg",
            "descriptionurl": f"https://commons.example/File:{name}",
            "extmetadata": {"Artist": {"value": "<a href='x'>NASA</a>"}, "LicenseShortName": {"value": "Public domain"}}}]})
    return {"query": {"normalized": [{"from": t, "to": "Datei:" + t.removeprefix("File:").replace("_", " ")} for t in titel],
                      "pages": seiten}}


class Quelle:
    def __init__(self) -> None:
        self.anfragen: list[str] = []
        self.drosseln = False
        self.ablehnen = False

    def __call__(self, anfrage: httpx.Request) -> httpx.Response:
        self.anfragen.append(str(anfrage.url))
        if self.drosseln:
            return httpx.Response(429, headers={"retry-after": "7"})
        if self.ablehnen and "Kontakt" not in anfrage.headers["user-agent"]:
            return httpx.Response(403, text="Please respect our robot policy https://w.wiki/4wJS")
        if anfrage.url.path.endswith("/w/api.php"):
            return httpx.Response(200, json=_api(anfrage))
        return httpx.Response(200, content=b"JPEG" + anfrage.url.path.encode())


@pytest.fixture
def umgebung(tmp_path: Path):
    quelle = Quelle()
    schlange = Schlange(tmp_path / "daten" / "bildholer.sqlite")
    geschlafen: list[float] = []

    async def schlafen(s: float) -> None:
        geschlafen.append(s)

    arbeiter = Arbeiter(schlange, Bildquelle(httpx.AsyncClient(transport=httpx.MockTransport(quelle))), tmp_path / "bilder",
                        schlafen=schlafen, uhr=lambda: datetime(2026, 11, 8, 14, 0))
    return schlange, arbeiter, quelle, geschlafen, tmp_path / "bilder"


async def test_holt_in_der_folge_mit_angaben_und_pause(umgebung):
    schlange, arbeiter, quelle, geschlafen, bilder = umgebung
    assert schlange.vormerken(QUELLE, ["Alt.jpg", "Fehlt.jpg"], 1) == 2
    assert schlange.vormerken(QUELLE, ["Neu_offen.jpg"], 0) == 1
    assert schlange.naechste(10) == (QUELLE, ["Neu_offen.jpg", "Alt.jpg", "Fehlt.jpg"])     # geöffnet springt nach vorn
    assert await arbeiter.runde()
    assert sum("/w/api.php" in a for a in quelle.anfragen) == 1                              # ein Stapel, eine Abfrage
    gefunden = ablage.lesen(bilder, QUELLE, "Neu_offen.jpg")
    assert gefunden and gefunden[0].read_bytes().startswith(b"JPEG/thumb/")
    assert gefunden[1].breite == 1280 and gefunden[1].original == 4000 and gefunden[1].urheber == "NASA"
    assert gefunden[1].lizenz == "Public domain"
    assert not ablage.da(bilder, QUELLE, "Fehlt.jpg") and geschlafen == [3.0, 3.0]
    assert schlange.vormerken(QUELLE, ["Fehlt.jpg", "Alt.jpg"], 0) == 0                      # fehlt und schon geholt
    s = arbeiter.stand()
    assert s.zustand == "wartet" and s.geladen == 2 and s.fehlgeschlagen == 1 and [z.name for z in s.zuletzt][0] in ("Alt.jpg", "Neu_offen.jpg")


async def test_drosselung_langsamer_oder_anhalten(umgebung):
    schlange, arbeiter, quelle, geschlafen, _ = umgebung
    schlange.vormerken(QUELLE, ["A.jpg"], 1)
    quelle.drosseln = True
    await arbeiter.runde()
    assert geschlafen == [7.0] and arbeiter.stand().abstand_s == 6.0 and schlange.offen() == {"1": 1}
    schlange.regeln_setzen(Regeln(bei_drosselung="anhalten"))
    await arbeiter.runde()
    s = arbeiter.stand()
    assert s.zustand == "angehalten" and "drosselt" in s.grund
    arbeiter.fortsetzen()
    quelle.drosseln = False
    assert arbeiter.stand().zustand == "laeuft" and arbeiter.stand().abstand_s == 3.0
    await arbeiter.runde()
    assert schlange.offen() == {}


async def test_nacht_aus_und_platzgrenze(umgebung):
    schlange, arbeiter, _, _, _ = umgebung
    schlange.vormerken(QUELLE, ["A.jpg"], 1)
    schlange.regeln_setzen(Regeln(wann="nachts"))
    assert not await arbeiter.runde() and arbeiter.stand().zustand == "ruht"
    assert in_der_nacht(Regeln(nacht_von=22, nacht_bis=6), 23) and in_der_nacht(Regeln(nacht_von=22, nacht_bis=6), 3)
    assert not in_der_nacht(Regeln(nacht_von=1, nacht_bis=6), 14)
    schlange.regeln_setzen(Regeln(an=False))
    assert arbeiter.stand().zustand == "aus"
    schlange.regeln_setzen(Regeln(platz_gb=1))
    schlange.geholt(QUELLE, "Riesig.jpg", 1280, 4000, 2_000_000_000)
    assert arbeiter.stand().zustand == "voll"


async def test_schnittstelle(tmp_path):
    app = app_bauen(tmp_path / "daten", tmp_path / "bilder", httpx.AsyncClient(transport=httpx.MockTransport(Quelle())),
                    arbeiten=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://bildholer") as c:
        assert (await c.put("/api/v1/regeln", json={"abstand_s": 5, "breite": 1920})).json()["abstand_s"] == 5
        assert (await c.get("/api/v1/regeln")).json()["breite"] == 1920
        assert (await c.post("/api/v1/vormerken", json={"quelle": QUELLE, "namen": ["A.jpg", "B.png"], "vorrang": 0})).json() == {"vorgemerkt": 2}
        assert (await c.post("/api/v1/vormerken", json={"quelle": "boese.example.com", "namen": ["A.jpg"]})).status_code == 422
        assert (await c.post("/api/v1/anhalten")).json()["zustand"] == "angehalten"
        assert (await c.get("/api/v1/stand")).json()["offen"] == {"0": 2}


def test_ablage_pfade(tmp_path):
    p = ablage.pfad(tmp_path, QUELLE, "Saturn_(Planet).jpg")
    assert p.parent.parent == tmp_path / QUELLE and len(p.parent.name) == 2 and p.name == "Saturn_(Planet).jpg"
    assert ablage.pfad(tmp_path, QUELLE, "a/../../b.jpg").name == "a_.._.._b.jpg"


async def test_abgelehnter_absender_haelt_an_bis_neue_regeln(umgebung):
    schlange, arbeiter, quelle, _, _ = umgebung
    schlange.vormerken(QUELLE, ["A.jpg"], 1)
    quelle.ablehnen = True
    schlange.regeln_setzen(Regeln(absender="Ohne-Angabe/1.0"))
    await arbeiter.runde()
    s = arbeiter.stand()
    assert s.zustand == "angehalten" and "Kontakt" in s.grund and len(quelle.anfragen) == 1
    assert not await arbeiter.runde() and len(quelle.anfragen) == 1                    # kein weiteres Anklopfen
    schlange.regeln_setzen(Regeln(absender="Bildholer/1.0 (Kontakt: https://example.org)"))
    arbeiter.regeln_geaendert()
    assert await arbeiter.runde() and schlange.offen() == {}
