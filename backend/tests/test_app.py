"""Nachschlag gegen eine nachgestellte Kellerwolke und einen nachgestellten Fundus, mit einem kleinen Buch aus dem
Schreiber von libzim (tests/buch.py): Bücher, Artikel im Lesedesign, Weiterleitung auf einen Abschnitt, Medien,
Vorschläge, Suche nur im Index und mit Bedeutung."""

import asyncio
import json
import re
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
    probebuch.bauen_doku(ordner)
    probebuch.bauen_spiegel(ordner)
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
    assert stand["fehler"] == [] and len(stand["buecher"]) == 3
    b = next(b for b in stand["buecher"] if b["kennung"] == "probe_de_all_2026-01")
    assert b["kennung"] == "probe_de_all_2026-01" and b["art"] == "enzyklopaedie" and b["startseite"] == "index"
    assert b["faehigkeiten"] == {"titelindex": True, "volltext": True, "bilder": True, "lesedesign": True}
    assert b["artikel"] == 8             # Seiten laut Zähler der Datei (index, sechs Artikel, eine Sprungseite), ohne Bilder
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
    assert a["bild"].startswith("/api/v1/inhalt/medien/probe_de_all_2026-01/_assets_/a/fuchs.png")
    html = a["html"]
    assert 'href="/lesen/probe_de_all_2026-01/Kreuzfuchs"' in html
    assert "Gibt_es_nicht" not in html and "dies" in html                              # Verweis ohne Ziel: Text
    assert 'data-geo="52.5,13.4"' in html and "Berlin" in html
    assert "<script" not in html and "bearbeiten" not in html and "ext-phonos" not in html
    assert not TYPOGRAFISCH & set(html + a["einleitung"]), "Anführungszeichen gerade"
    assert "https://example.org/weblink" in a["online"] and not any(".invalid" in o for o in a["online"])
    assert a["verweise"]["ohne_ziel"] == 1 and a["verweise"]["koordinaten"] == 1
    assert a["original"] == "/api/v1/inhalt/original/probe_de_all_2026-01/Rotfuchs"


async def test_belege_auch_in_abschnitten(nachschlag):
    """Heutige Seiten packen jeden Abschnitt in ein <section>: Belege fallen trotzdem weg, Weblinks bleiben online."""
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Svante_Arrhenius")).json()
    assert [s["titel"] for s in a["abschnitte"]] == ["Leben"]
    assert "Ein Buch" not in a["html"] and "Beleg" not in a["html"]
    assert a["online"] == ["https://example.org/arrhenius"]
    # Bildname mit wörtlichem %2C: Weg einmal verschlüsselt, das Bild kommt
    weg = re.search(r'src="([^"]+Ufer\.png)"', a["html"]).group(1)
    assert weg.endswith("/K%C3%B6ln%252C_Ufer.png")
    assert (await c.get(weg)).content == probebuch.PNG


async def test_steckbrief_aus_zellen_mit_klassen(nachschlag):
    """Infobox der englischen Ausgabe (td mit Klassen und Stil): Werte kommen als gesäubertes HTML, nie als Rohtext."""
    c, _, _ = nachschlag
    s = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Ancient_Egypt")).json()["steckbrief"]
    assert s["titel"] == "Ancient Egypt"
    assert "infobox" not in s["html"] and "style" not in s["html"] and "scope" not in s["html"]
    assert '<dt>Capital</dt><dd><i>See</i> <a href="/lesen/probe_de_all_2026-01/Raubtiere" class="wl">List of capitals</a> &lt;x&gt;</dd>' in s["html"]
    assert "<figcaption>Map of the Nile</figcaption>" in s["html"] and "<dt>Religion</dt><dd>Egyptian religion</dd>" in s["html"]


async def test_startseite_des_buchs_als_uebersicht(nachschlag):
    """Die Startseite ist eine Kachelseite, kein Artikel: Nachschlag liest ihre Kacheln aus (ohne Ziel fallen weg)."""
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probe_de_all_2026-01/index")).json()
    assert a["darstellung"] == "uebersicht" and a["baustein"] == "uebersicht" and a["titel"] == "Probelexikon"
    assert a["kacheln"] == [
        {"pfad": "Rotfuchs", "titel": "Rotfuchs", "bild": "/api/v1/inhalt/medien/probe_de_all_2026-01/_assets_/a/fuchs.png"},
        {"pfad": "Kreuzfuchs", "titel": "Kreuzfuchs", "bild": ""}]


async def test_stammbaum_und_verstecktes(nachschlag):
    """Was die Quelle nur per Stil sagt: Verstecktes fällt weg, Linien eines Stammbaums werden Klassen, der Kasten
    schwebt rechts; Stilangaben selbst kommen nie mit."""
    c, _, _ = nachschlag
    html = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Rotfuchs")).json()["html"]
    assert "Wartung" not in html and "style=" not in html
    assert '<table class="rechts">' in html and '<table class="klade">' in html
    assert '<td class="linie-unten">' in html and '<td class="linie-unten linie-links">' in html


async def test_weiterleitung_auf_abschnitt(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probe_de_all_2026-01/Stadtfuchs")).json()
    assert (a["pfad"], a["angefragt"], a["anker"]) == ("Rotfuchs", "Stadtfuchs", "Lebensraum")
    assert (await c.get("/api/v1/artikel/probe_de_all_2026-01/Gibt_es_nicht")).status_code == 404


async def test_medien_und_original(nachschlag):
    c, _, _ = nachschlag
    r = await c.get("/api/v1/inhalt/medien/probe_de_all_2026-01/_assets_/a/fuchs.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content == probebuch.PNG
    assert "immutable" in r.headers["cache-control"]
    r = await c.get("/api/v1/inhalt/original/probe_de_all_2026-01/Rotfuchs")
    csp = r.headers["content-security-policy"]
    assert r.status_code == 200 and "sandbox" in csp and "allow-scripts" not in csp and "script-src 'none'" in csp
    assert "<script" not in r.text and "Rotfuchs" in r.text


async def test_medien_mit_lesezugang_ohne_kopf(nachschlag):
    """Wie <img> und <iframe>: ohne Kopf, nur mit dem Cookie des Lesezugangs (gilt nur unter /api/v1/inhalt)."""
    c, _, _ = nachschlag
    assert (await c.post("/api/v1/anmeldung/zugang")).status_code == 204
    token = c.headers.pop("X-Kellerwolke-Sitzung")
    try:
        assert (await c.get("/api/v1/inhalt/medien/probe_de_all_2026-01/_assets_/a/fuchs.png")).status_code == 200
        assert (await c.get("/api/v1/buecher")).status_code == 401
    finally:
        c.headers["X-Kellerwolke-Sitzung"] = token


async def test_vorschlaege_zeigen_weiterleitungen(nachschlag):
    c, _, _ = nachschlag
    v = (await c.get("/api/v1/vorschlaege", params={"anfang": "Stadt"})).json()
    assert v[0]["titel"] == "Stadtfuchs" and v[0]["weiterleitung"]


async def test_suche_nur_im_index(nachschlag):
    c, _, _ = nachschlag
    s = (await c.get("/api/v1/suche", params={"frage": "Städte"})).json()
    assert s["nur_index"] and s["hinweis"] and not s["bedeutung_angebunden"]
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
    assert s["nur_index"] and s["treffer"] and s["zeiten"]["bedeutung_ms"] is None and s["bedeutung_angebunden"]


DOKU = "probedoku_en_php_2026-08"


async def test_dokumentation_nach_entwurf(nachschlag):
    """Handbuch (devdocs2zim) neu gesetzt: Teile mit eigenen Namen, Signatur, Parameter mit Typ, Änderungen, Beispiel
    mit eingefärbtem Code und Ausgabe, Siehe auch; Rubrik und Nachbarn aus der Gliederung; Steckbrief mit Fassungen."""
    c, _, _ = nachschlag
    a = (await c.get(f"/api/v1/artikel/{DOKU}/function.array-map")).json()
    assert (a["darstellung"], a["baustein"], a["titel"], a["titelart"]) == ("lesedesign", "dokumentation", "array_map", "code")
    assert [(s["titel"], s["ebene"]) for s in a["abschnitte"]] == [
        ("Beschreibung", 2), ("Parameter", 2), ("Änderungen", 2), ("Beispiele", 2), ("Beispiel 1: array_map() example", 3),
        ("Siehe auch", 2)]
    assert a["rubrik"] == "Array" and [n["pfad"] for n in a["nachbarn"]] == ["function.array-filter", "function.array-map"]
    html = a["html"]
    assert html.startswith('<p class="einleitung">Applies the callback to the elements</p>')
    assert '<span class="name">array_map</span>(<span class="typ">?callable</span> <span class="var">$callback</span>' in html
    assert '<dt>$callback<span class="typ">?callable</span></dt>' in html and 'class="parameterliste"' in html
    assert '<table class="aenderungen">' in html
    assert re.search(r'<h3 class="bkopf" id="[^"]+">Beispiel 1: array_map\(\) example</h3>', html)
    assert '<span class="c-fn">array_map</span>(<span class="c-str">\'cube\'</span>' in html
    assert '<div class="ausgabe-titel">Ausgabe</div><pre class="ausgabe">Array' in html and "will output" not in html
    assert f'<a href="/lesen/{DOKU}/function.array-filter" class="wl"><code>array_filter()</code><span>Filters elements of an array</span></a>' in html
    assert "attribution" not in html and "php.net" not in html
    s = a["steckbrief"]
    assert s["titel"] == "array_map" and s["code"]
    assert '<div class="versionen"><span>PHP 4 &gt;= 4.0.6</span><span>PHP 5</span>' in s["html"] and "18.08.2026" in s["html"]


async def test_startseite_einer_dokumentation_als_rubriken(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get(f"/api/v1/artikel/{DOKU}/index")).json()
    assert a["darstellung"] == "uebersicht" and a["gruppen"][0]["titel"] == "Array"
    assert [e["titel"] for e in a["gruppen"][0]["eintraege"]] == ["array_filter", "array_map"]


async def test_spiegel_von_php_net_wie_die_dokumentation(nachschlag):
    """Der Spiegel von php.net (warc2zim) wird wie das Handbuch gesetzt: Code aus dem von php.net gefärbten HTML
    (Zeilen als <br>) neu eingefärbt, Rubrik aus den Brotkrumen, Nachbarn aus der Seitenleiste, Notizen gezählt; die
    Seite von php.net selbst (Sprachwahl, Skripte, Notizen) fällt weg."""
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probespiegel_en_all_2024-08/www.php.net/manual/en/function.array-map.php")).json()
    assert (a["baustein"], a["titel"], a["titelart"], a["rubrik"]) == ("dokumentation", "array_map", "code", "Array Functions")
    assert [n["titel"] for n in a["nachbarn"]] == ["array_keys", "array_map"]
    buch = (await c.get("/api/v1/buecher/probespiegel_en_all_2024-08")).json()
    assert buch["art"] == "dokumentation" and buch["faehigkeiten"]["lesedesign"]   # Art nach der Quelle des Spiegels
    assert [n["pfad"] for n in a["nachbarn"]][1] == "www.php.net/manual/en/function.array-map.php"
    html = a["html"]
    assert '<pre><span class="c-tag">&lt;?php</span>\n<span class="c-var">$b</span> = <span class="c-fn">array_map</span>(<span class="c-str">\'cube\'</span>);\n<span class="c-tag">?&gt;</span></pre>' in html
    assert "<script" not in html and "select" not in html and "first" not in html
    assert "<dt>Notizen</dt><dd>2 der Nutzer</dd>" in a["steckbrief"]["html"]
