"""Nachschlag gegen eine nachgestellte Kellerwolke und einen nachgestellten Fundus, mit einem kleinen Buch aus dem
Schreiber von libzim (tests/buch.py): Bücher, Artikel im Lesedesign, Weiterleitung auf einen Abschnitt, Medien,
Vorschläge, Suche nur im Index und mit Bedeutung."""

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.main import app_bauen  # noqa: E402

FUNDUS = "http://fundus.test"
TYPOGRAFISCH = {chr(c) for c in (0x201E, 0x201C, 0x201D, 0x2013, 0x2014)}


class Fundus:
    """Antwortet wie der Fundus; `schlaeft` lässt ihn zu spät antworten."""
    schlaeft = 0.0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(self.schlaeft)
        frage = json.loads(request.content)
        assert frage["art"] == "bedeutung" and frage["sammlungen"] == ["probe"]
        return httpx.Response(200, json={"nur_woertlich": False, "volltext": False, "treffer": [
            {"herkunft": "wikipedia:de/Kreuzfuchs", "titel": "Probe > Kreuzfuchs > Kreuzfuchs", "ueberschrift": "Kreuzfuchs",
             "text": "Der Kreuzfuchs ist eine Farbform des Rotfuchses.", "dicht": 0.81},
            {"herkunft": "anderswo:Seite", "titel": "Fremd", "dicht": 0.9}]})


def kellerwolke(request: httpx.Request) -> httpx.Response:
    pfad = request.url.path
    if pfad == "/api/v1/ablage/ich":
        return httpx.Response(200, json={"app": "Nachschlag", "konto": "probe", "rechte": []})
    if pfad == "/api/v1/auth/login":
        return httpx.Response(200, json={"token": "t1", "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True}})
    if pfad == "/api/v1/auth/status":
        ok = request.headers.get("x-kellerwolke-sitzung") == "t1"
        return httpx.Response(200, json={"angemeldet": ok, "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True} if ok else None})
    return httpx.Response(404, json={"detail": "nicht da"})


@pytest.fixture(scope="session")
def buecher(tmp_path_factory) -> Path:
    ordner = tmp_path_factory.mktemp("buecher")
    probebuch.bauen(ordner)
    return ordner


@pytest.fixture
async def nachschlag(tmp_path: Path, buecher: Path):
    fundus = Fundus()

    async def netz(request: httpx.Request) -> httpx.Response:
        return await fundus(request) if request.url.host == "fundus.test" else kellerwolke(request)

    app = app_bauen(tmp_path / "daten", transport=httpx.MockTransport(netz))
    geruest = app.state.geruest
    await geruest.starten()
    await geruest.einstellungen.aendern({"buecher_ordner": str(buecher)})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
        token = (await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).json()["token"]
        c.headers["X-Kellerwolke-Sitzung"] = token
        yield c, geruest, fundus
    await geruest.stoppen()


async def test_buecher(nachschlag):
    c, _, _ = nachschlag
    stand = (await c.get("/api/v1/buecher")).json()
    assert stand["fehler"] == [] and len(stand["buecher"]) == 1
    b = stand["buecher"][0]
    assert b["kennung"] == "probe_de_all_2026-01" and b["art"] == "enzyklopaedie" and b["startseite"] == "Rotfuchs"
    assert b["faehigkeiten"] == {"titelindex": True, "volltext": True, "bilder": True, "lesedesign": True}
    assert (await c.get("/api/v1/buecher/gibt_es_nicht")).status_code == 404


async def test_ohne_anmeldung_nichts(nachschlag):
    c, _, _ = nachschlag
    assert (await c.get("/api/v1/buecher", headers={"X-Kellerwolke-Sitzung": "falsch"})).status_code == 401


async def test_artikel_im_lesedesign(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Rotfuchs")).json()
    assert a["darstellung"] == "lesedesign" and a["baustein"] == "enzyklopaedie" and a["titel"] == "Rotfuchs"
    assert [s["titel"] for s in a["abschnitte"]] == ["Merkmale", "Lebensraum"]          # Belege und Weblinks weg
    assert a["steckbrief"]["titel"] == "Rotfuchs" and "Raubtiere" in a["steckbrief"]["html"]
    assert a["bild"].startswith("/api/v1/medien/probe_de_all_2026-01/_assets_/a/fuchs.png")
    html = a["html"]
    assert 'href="/lesen/probe_de_all_2026-01/Kreuzfuchs"' in html
    assert "Gibt_es_nicht" not in html and "dies" in html                              # Verweis ohne Ziel: Text
    assert 'data-geo="52.5,13.4"' in html and "Berlin" in html
    assert "<script" not in html and "bearbeiten" not in html and "ext-phonos" not in html
    assert not TYPOGRAFISCH & set(html + a["einleitung"]), "Anführungszeichen gerade"
    assert "https://example.org/weblink" in a["online"] and not any(".invalid" in o for o in a["online"])
    assert a["verweise"]["ohne_ziel"] == 1 and a["verweise"]["koordinaten"] == 1
    assert a["original"] == "/api/v1/original/probe_de_all_2026-01/Rotfuchs"


async def test_weiterleitung_auf_abschnitt(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Stadtfuchs")).json()
    assert (a["pfad"], a["angefragt"], a["anker"]) == ("Rotfuchs", "Stadtfuchs", "Lebensraum")
    assert (await c.get("/api/v1/artikel/probe_de_all_2026-01/Gibt_es_nicht")).status_code == 404


async def test_medien_und_original(nachschlag):
    c, _, _ = nachschlag
    r = await c.get("/api/v1/medien/probe_de_all_2026-01/_assets_/a/fuchs.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == probebuch.PNG
    assert "immutable" in r.headers["cache-control"]
    r = await c.get("/api/v1/original/probe_de_all_2026-01/Rotfuchs")
    assert r.status_code == 200 and "sandbox" in r.headers["content-security-policy"]


async def test_vorschlaege_zeigen_weiterleitungen(nachschlag):
    c, _, _ = nachschlag
    v = (await c.get("/api/v1/vorschlaege", params={"anfang": "Stadt"})).json()
    assert v[0]["titel"] == "Stadtfuchs" and v[0]["weiterleitung"]


async def test_suche_nur_im_index(nachschlag):
    c, _, _ = nachschlag
    s = (await c.get("/api/v1/suche", params={"frage": "Städte"})).json()
    assert s["nur_index"] and s["hinweis"]
    assert s["treffer"][0]["pfad"] == "Rotfuchs" and s["treffer"][0]["wege"] == ["index"]
    assert "<em>" in s["treffer"][0]["ausschnitt"]


async def test_suche_mit_bedeutung(nachschlag):
    c, geruest, _ = nachschlag
    await geruest.einstellungen.aendern({"fundus_adresse": FUNDUS, "fundus_sammlung": "probe",
                                         "bedeutung_buch": "probe_de_all_2026-01"})
    s = (await c.get("/api/v1/suche", params={"frage": "Farbform"})).json()
    assert not s["nur_index"], s["hinweis"]
    kreuz = next(t for t in s["treffer"] if t["pfad"] == "Kreuzfuchs")
    assert set(kreuz["wege"]) == {"bedeutung", "index"}
    assert s["beste_stelle"]["pfad"] == "Kreuzfuchs"
    assert all(t["pfad"] != "Seite" for t in s["treffer"])                             # fremde Herkunft bleibt draußen


async def test_suche_wartet_nicht_auf_langsame_bedeutung(nachschlag):
    c, geruest, fundus = nachschlag
    await geruest.einstellungen.aendern({"fundus_adresse": FUNDUS, "fundus_sammlung": "probe",
                                         "bedeutung_buch": "probe_de_all_2026-01", "bedeutung_warten_s": 0.2})
    fundus.schlaeft = 2
    s = (await c.get("/api/v1/suche", params={"frage": "Städte"})).json()
    assert s["nur_index"] and s["treffer"] and s["zeiten"]["bedeutung_ms"] is None
