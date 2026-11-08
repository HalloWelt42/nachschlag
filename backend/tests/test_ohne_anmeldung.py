"""Nachschlag wie frisch aus dem öffentlichen Repo gestartet (WIKI-11): ohne Anmeldung und ohne Kellerwolke. Lesen,
Merkzettel, Notizen mit Bildern, Themen und Verlauf gehören dem festen Nutzer; was sonst in der Kellerwolke läge (Notizen
als Markdown, eigene Vorlagen, Bilder an Notizen), liegt im Ordner ablage des Datenordners."""

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_app import buecher  # noqa: E402,F401

from app.main import app_bauen  # noqa: E402

pytestmark = pytest.mark.ohne_anmeldung


def nichts_im_netz(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"ohne Anbindungen geht nichts ins Netz: {request.url}")


@pytest.fixture
async def frisch(tmp_path: Path, buecher: Path):  # noqa: F811
    app = app_bauen(tmp_path / "daten", transport=httpx.MockTransport(nichts_im_netz))
    geruest = app.state.geruest
    await geruest.starten()
    await geruest.einstellungen.aendern({"buecher_ordner": str(buecher)})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.168.1.57", 5)), base_url="http://t") as c:
        yield c, geruest, tmp_path / "daten" / "ablage"
    await geruest.stoppen()


async def test_frisch_ohne_anmeldung_und_ohne_kellerwolke(frisch):
    c, geruest, _ = frisch
    info = (await c.get("/api/v1/app")).json()
    assert info["anmeldung"] == "ohne" and info["ablage"] == "ordner" and not info["einrichtung_noetig"]
    assert geruest.einstellungen.herkunft("anmeldung") == "gespeichert"       # beim ersten Start festgehalten
    assert (await c.get("/api/v1/ich")).json()["id"] == "nutzer"
    assert len((await c.get("/api/v1/buecher")).json()["buecher"]) == 4
    assert (await c.get("/api/v1/artikel/probe_de_all_2026-01/Rotfuchs")).json()["titel"] == "Rotfuchs"
    assert (await c.get("/api/v1/einstellungen")).status_code == 200
    assert (await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).status_code == 409
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen")).json()}
    assert all(not v["ok"] and v["meldung"] == "nicht eingerichtet" for v in verbindungen.values()), verbindungen
    assert all(v["wahlweise"] for v in verbindungen.values())                  # alle Anbindungen sind wahlweise


async def test_meins_gehoert_dem_festen_nutzer(frisch):
    c, _, ablage = frisch
    merk = await c.post("/api/v1/meins/merkzettel", json={"buch": "probe_de_all_2026-01", "pfad": "Rotfuchs", "titel": "Rotfuchs"})
    assert merk.status_code == 200, merk.text
    t = (await c.post("/api/v1/meins/themen", json={"titel": "Füchse"})).json()
    assert (await c.post(f"/api/v1/meins/themen/{t['id']}/eintraege",
                         json={"buch": "probe_de_all_2026-01", "pfad": "Rotfuchs", "titel": "Rotfuchs"})).status_code == 200
    n = (await c.post("/api/v1/meins/notizen", json={"buch": "probe_de_all_2026-01", "pfad": "Rotfuchs", "titel": "Rotfuchs",
                                                     "text": "rot und schlau"})).json()
    # ein anderes Gerät ist derselbe Nutzer
    async with httpx.AsyncClient(transport=c._transport, base_url="http://t",
                                 headers={"X-Kellerwolke-Sitzung": "altes-token"}) as anderes:
        assert [m["titel"] for m in (await anderes.get("/api/v1/meins/merkzettel")).json()] == ["Rotfuchs"]
        assert [x["titel"] for x in (await anderes.get("/api/v1/meins/themen")).json()] == ["Füchse"]
        assert (await anderes.get("/api/v1/meins/notizen")).json()[0]["id"] == n["id"]

    # Notizen als Markdown und Bilder an Notizen im Datenordner
    stand = (await c.post("/api/v1/meins/notizen/markdown")).json()
    assert stand == {"dateien": 1, "ordner": "ablage/Notizen"}
    md = ablage / "Notizen" / "probe_de_all" / "Rotfuchs.md"
    assert "rot und schlau" in md.read_text(encoding="utf-8")
    assert (await c.post(f"/api/v1/meins/themen/{t['id']}/markdown")).json()["pfad"] == "ablage/Themen/Füchse.md"
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    bild = (await c.post(f"/api/v1/meins/notizen/{n['id']}/bilder", files={"datei": ("a.png", png, "image/png")})).json()["bilder"][0]
    assert (ablage / "Notizen" / n["id"] / f"{bild['id']}.png").read_bytes() == png
    geholt = await c.get(f"/api/v1/inhalt/notizbilder/{n['id']}/{bild['id']}")        # wie <img>: ohne Kopf und Cookie
    assert geholt.status_code == 200 and geholt.content == png
    assert (await c.delete(f"/api/v1/meins/notizen/{n['id']}")).status_code == 204
    assert not (ablage / "Notizen" / n["id"]).exists()
    assert not md.exists()                                                      # keine Notizen mehr: die Datei geht


async def test_eigene_vorlagen_im_datenordner(frisch):
    c, _, ablage = frisch
    liste = (await c.get("/api/v1/buchvorlagen")).json()
    assert liste["ordner"] == "ablage/Vorlagen" and liste["hinweis"] == ""
    kopie = (await c.post("/api/v1/buchvorlagen/lernheft/kopie", json={"titel": "Beobachtungsheft"})).json()
    assert (ablage / "Vorlagen" / f"{kopie['kennung']}.toml").is_file()
    assert [v["titel"] for v in (await c.get("/api/v1/buchvorlagen")).json()["vorlagen"]][-1] == "Beobachtungsheft"
    assert (await c.get(f"/api/v1/inhalt/buchvorlagen/{kopie['kennung']}")).status_code == 200
    assert (await c.delete(f"/api/v1/buchvorlagen/{kopie['kennung']}")).status_code == 204
    assert not (ablage / "Vorlagen" / f"{kopie['kennung']}.toml").exists()
