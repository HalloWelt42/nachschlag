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
    probebuch.bauen_qa(ordner)
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
    assert stand["fehler"] == [] and len(stand["buecher"]) == 4
    b = next(b for b in stand["buecher"] if b["kennung"] == "probe_de_all_2026-01")
    assert b["kennung"] == "probe_de_all_2026-01" and b["art"] == "enzyklopaedie" and b["startseite"] == "index"
    assert b["faehigkeiten"] == {"titelindex": True, "volltext": True, "bilder": True, "lesedesign": True}
    assert b["artikel"] == 9             # Seiten laut Zähler der Datei (index, sechs Artikel, zwei Sprungseiten), ohne Bilder
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
    assert [t["pfad"] for t in s["treffer"]].count("Rotfuchs") == 1           # Sprungseite Vulpes_vulpes zeigt aufs Ziel
    assert "Vulpes_vulpes" not in [t["pfad"] for t in s["treffer"]]


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


async def test_inhaltsverzeichnis_des_spiegels_als_rubriken(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probespiegel_en_all_2024-08/www.php.net/manual/en/index.php")).json()
    assert a["darstellung"] == "uebersicht"
    assert [(g["titel"], [e["titel"] for e in g["eintraege"]]) for g in a["gruppen"]] == [
        ("Allgemein", ["Copyright"]), ("Function Reference", ["Überblick", "array_map", "array_keys"])]
    assert a["gruppen"][1]["eintraege"][1]["pfad"] == "www.php.net/manual/en/function.array-map.php"


async def test_seitenpfade_mit_punkt_bleiben_seiten(nachschlag):
    """Direkt geöffnete Wege unter /lesen mit Punkt (Pfade aus Büchern) bekommen die Oberfläche, nie 404."""
    c, _, _ = nachschlag
    for weg in ("/lesen/probespiegel_en_all_2024-08/www.php.net/manual/en/function.array-map.php",
                f"/lesen/{DOKU}/language.types.array"):
        r = await c.get(weg)
        assert r.status_code == 200 and "Nicht gefunden" not in r.text, weg
    assert (await c.get("/sonst/datei.php")).status_code == 404          # außerhalb von /lesen gilt die Dateiregel


async def test_frage_und_antwort_nach_entwurf(nachschlag):
    """sotoki neu gesetzt: Frage mit Stimmen, Schlagwörtern und zugeklappten Kommentaren, die akzeptierte Antwort
    zuerst (vor einer mit mehr Stimmen), Wer und Wann auf Deutsch, Code als Block; Steckbrief und Inhalt dazu."""
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probeqa_en_all_2026-10/questions/84/clipboard")).json()
    assert (a["baustein"], a["titel"], a["rubrik"]) == ("frage_antwort", "How can I copy text to the clipboard?", "Fragen")
    assert [s["titel"] for s in a["abschnitte"]] == ["Frage", "2 Antworten", "40 · Martin Tournoij", "53 · Quincy Bowers"]
    html = a["html"]
    assert '<div class="qa-stimmen"><span class="zahl">520</span><span class="was">Stimmen</span></div>' in html
    assert '<div class="schlagwoerter"><span>os-clipboard</span></div>' in html
    assert '<span>gefragt 03.02.2015 von thameera</span>' in html
    assert '<details class="kommentare"><summary>1 Kommentar</summary><ul class="kommentar-liste"><li><b>+15</b>Asked on SO.' in html
    assert html.index('id="antwort-96"') < html.index('id="antwort-97"')       # akzeptiert vor mehr Stimmen
    assert '<div class="antwort akzeptiert" id="antwort-96">' in html and '<span class="akz-marke">Akzeptierte Antwort</span>' in html
    assert '<pre class="codeblock">set clipboard=unnamedplus\n</pre>' in html
    s = a["steckbrief"]
    assert s["titel"] == "Frage 84"
    assert "<dt>Antworten</dt><dd>2, eine akzeptiert</dd>" in s["html"] and "<dt>Gefragt</dt><dd>03.02.2015 von thameera</dd>" in s["html"]
    assert 'href="/lesen/probeqa_en_all_2026-10/questions/332/registers"' in s["html"]


async def test_fragenliste_als_karten_mit_blaettern(nachschlag):
    c, _, _ = nachschlag
    a = (await c.get("/api/v1/artikel/probeqa_en_all_2026-10/questions")).json()
    assert (a["darstellung"], a["titel"], a["weiter"], a["zurueck"]) == ("uebersicht", "Beliebteste Fragen", "questions_page=2", "")
    assert a["fragen"] == [{"pfad": "questions/84/clipboard", "titel": "How can I copy text to the clipboard?", "auszug": "Is there a way?",
                            "stimmen": 1520, "antworten": 2, "akzeptiert": True, "schlagwoerter": ["os-clipboard"], "gefragt": "03.02.2015"}]


async def test_merkzettel_verlauf_und_vorlieben(nachschlag):
    """Meins je Konto: merken (zweimal bleibt einer), Anteil aus dem Lesestand, Lesezeit zusammengezählt, Suche im
    Verlauf, jüngstes zuerst; Vorlieben setzen und löschen; vergessen."""
    c, _, _ = nachschlag
    buch = "probe_de_all_2026-01"
    for _ in range(2):
        m = (await c.post("/api/v1/meins/merkzettel", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs"})).json()
    assert (m["buch_name"], m["buch"]) == ("probe_de_all", buch)
    for anteil, sekunden in ((0.2, 30), (0.34, 40)):
        r = await c.put("/api/v1/meins/verlauf/lesestand", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs",
                                                                  "abschnitt": "Lebensraum", "anteil": anteil, "sekunden": sekunden})
        assert r.status_code == 204
    await c.post("/api/v1/meins/verlauf/suche", json={"frage": "Füchse in Städten", "treffer": 38})
    liste = (await c.get("/api/v1/meins/merkzettel")).json()
    assert len(liste) == 1 and liste[0]["anteil"] == 0.34 and liste[0]["buch"] == buch
    verlauf = (await c.get("/api/v1/meins/verlauf")).json()
    assert [v["art"] for v in verlauf] == ["suche", "artikel"]
    assert (verlauf[1]["sekunden"], verlauf[1]["abschnitt"], verlauf[1]["buch"]) == (70, "Lebensraum", buch)
    assert (await c.put("/api/v1/meins/vorlieben/fassung:devdocs_en_php", json={"wert": "8.3"})).status_code == 204
    assert (await c.get("/api/v1/meins/vorlieben")).json() == {"fassung:devdocs_en_php": "8.3"}
    await c.put("/api/v1/meins/vorlieben/fassung:devdocs_en_php", json={"wert": ""})
    assert (await c.get("/api/v1/meins/vorlieben")).json() == {}
    assert (await c.delete(f"/api/v1/meins/merkzettel/{m['id']}")).status_code == 204
    assert (await c.get("/api/v1/meins/merkzettel")).json() == []
    assert (await c.delete(f"/api/v1/meins/merkzettel/{m['id']}")).status_code == 404


async def test_notizen_an_stelle_und_artikel(nachschlag):
    """Notizen je Konto: an einer Stelle (Zitat mit Text davor) und am ganzen Artikel; je Artikel abfragbar, Ändern
    schiebt nach vorn, Löschen; unbekannte Notizen geben 404."""
    c, _, _ = nachschlag
    buch = "probe_de_all_2026-01"
    stelle = (await c.post("/api/v1/meins/notizen", json={
        "buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs", "abschnitt": "Merkmale",
        "zitat": " Birkfuchs mit gelb-roter Oberseite ", "davor": "Farbvariante ist der ", "text": ""})).json()
    assert (stelle["buch_name"], stelle["buch"], stelle["zitat"], stelle["text"]) == ("probe_de_all", buch, "Birkfuchs mit gelb-roter Oberseite", "")
    artikel = (await c.post("/api/v1/meins/notizen", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs", "text": "Wildpark"})).json()
    await c.post("/api/v1/meins/notizen", json={"buch": buch, "pfad": "Arrhenius", "titel": "Arrhenius", "text": "anderer Artikel"})
    nur = (await c.get("/api/v1/meins/notizen", params={"buch": buch, "pfad": "Rotfuchs"})).json()
    assert [n["id"] for n in nur] == [artikel["id"], stelle["id"]]
    geaendert = (await c.patch(f"/api/v1/meins/notizen/{stelle['id']}", json={"text": "häufigste Farbe"})).json()
    assert geaendert["text"] == "häufigste Farbe" and geaendert["geaendert"] > geaendert["angelegt"]
    alle = (await c.get("/api/v1/meins/notizen")).json()
    assert len(alle) == 3 and alle[0]["id"] == stelle["id"]
    assert (await c.delete(f"/api/v1/meins/notizen/{artikel['id']}")).status_code == 204
    assert (await c.delete(f"/api/v1/meins/notizen/{artikel['id']}")).status_code == 404
    assert (await c.patch(f"/api/v1/meins/notizen/{artikel['id']}", json={"text": "x"})).status_code == 404


async def test_themen_bereiche_eintraege_und_angebote(nachschlag):
    """Thema anlegen, Bereiche, Artikel hinein (zweimal bleibt einer), verschieben und umordnen, Lesestand und Notizen
    am Eintrag; Angebote aus der gespeicherten Suche ohne Bekanntes und Abgelehntes; Bereich löschen lässt die Artikel
    im Thema; Zuordnung; Thema löschen."""
    c, _, _ = nachschlag
    buch = "probe_de_all_2026-01"
    t = (await c.post("/api/v1/meins/themen", json={"titel": " Füchse ", "regel": "Städte", "regel_buch": buch})).json()
    assert (t["titel"], t["regel_buch"], t["eintraege"]) == ("Füchse", buch, [])
    w = f"/api/v1/meins/themen/{t['id']}"
    angebote = lambda: c.get(f"{w}/angebote")  # noqa: E731
    assert "Rotfuchs" in [a["pfad"] for a in (await angebote()).json()]
    tiere = (await c.post(f"{w}/bereiche", json={"titel": "Tiere"})).json()
    orte = (await c.post(f"{w}/bereiche", json={"titel": "Orte"})).json()
    assert (tiere["platz"], orte["platz"]) == (0, 1)
    for _ in range(2):
        rf = (await c.post(f"{w}/eintraege", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs", "bereich": tiere["id"]})).json()
    ar = (await c.post(f"{w}/eintraege", json={"buch": buch, "pfad": "Arrhenius", "titel": "Arrhenius"})).json()
    assert ar["bereich"] == "" and rf["bereich"] == tiere["id"]
    await c.put("/api/v1/meins/verlauf/lesestand", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs", "anteil": 0.5})
    await c.post("/api/v1/meins/notizen", json={"buch": buch, "pfad": "Rotfuchs", "titel": "Rotfuchs", "text": "x"})
    assert (await c.patch(f"{w}/eintraege/{ar['id']}", json={"bereich": tiere["id"], "platz": 0})).status_code == 204
    assert (await c.patch(f"{w}/bereiche/{orte['id']}", json={"platz": 0})).status_code == 204
    thema = (await c.get(w)).json()
    assert [b["titel"] for b in thema["bereiche"]] == ["Orte", "Tiere"]
    eintraege = {e["pfad"]: e for e in thema["eintraege"]}
    assert (eintraege["Arrhenius"]["platz"], eintraege["Rotfuchs"]["platz"]) == (0, 1)
    assert (eintraege["Rotfuchs"]["anteil"], eintraege["Rotfuchs"]["gelesen_je"], eintraege["Rotfuchs"]["notizen"]) == (0.5, True, 1)
    assert eintraege["Arrhenius"]["gelesen_je"] is False and len(thema["eintraege"]) == 2
    assert "Rotfuchs" not in [a["pfad"] for a in (await angebote()).json()]          # schon im Thema
    assert (await c.delete(f"{w}/bereiche/{tiere['id']}")).status_code == 204
    assert {e["bereich"] for e in (await c.get(w)).json()["eintraege"]} == {""}
    koepfe = (await c.get("/api/v1/meins/themen")).json()
    assert [(k["titel"], k["eintraege"], k["bereiche"], k["buecher"]) for k in koepfe] == [("Füchse", 2, 1, 1)]
    zuordnung = (await c.get("/api/v1/meins/themen/zuordnung")).json()
    assert {z["pfad"] for z in zuordnung} == {"Rotfuchs", "Arrhenius"} and zuordnung[0]["titel"] == "Füchse"
    assert (await c.delete(f"{w}/eintraege/{rf['id']}")).status_code == 204
    assert "Rotfuchs" in [a["pfad"] for a in (await angebote()).json()]
    assert (await c.post(f"{w}/abgelehnt", json={"buch": buch, "pfad": "Rotfuchs"})).status_code == 204
    assert "Rotfuchs" not in [a["pfad"] for a in (await angebote()).json()]          # abgelehnt kommt nicht wieder
    assert (await c.delete(w)).status_code == 204
    assert (await c.get(w)).status_code == 404 and (await c.get("/api/v1/meins/themen")).json() == []


async def test_stoebern_zufall_pfad_und_blaettern(nachschlag):
    """Zufall mit Bild und noch nicht gelesen; Schritt im Entdeckungspfad mit Verweisen und Nennungen; Blättern um einen
    Artikel, ab einem Buchstaben und seitenweise vor und zurück, ohne Weiterleitungen und Bilder."""
    c, _, _ = nachschlag
    buch = "probe_de_all_2026-01"
    z = (await c.get(f"/api/v1/stoebern/zufall/{buch}", params={"mit_bild": True})).json()
    assert z["bild"] and z["titel"] and z["buch"] == buch
    s = (await c.get(f"/api/v1/stoebern/schritt/{buch}/Rotfuchs")).json()
    assert s["fund"]["titel"] == "Rotfuchs" and s["fund"]["auszug"].startswith("Der Rotfuchs")
    assert s["von_hier"] and all(n["pfad"] != "Rotfuchs" for n in s["von_hier"]) and s["von_hier"][0]["hinweis"]
    assert s["aehnlich"] == [] and all(n["pfad"] != "Rotfuchs" for n in s["erwaehnt_in"])
    seite = (await c.get(f"/api/v1/stoebern/blaettern/{buch}", params={"um": "Vulpes_vulpes", "anzahl": 5})).json()
    pfade = [e["pfad"] for e in seite["eintraege"]]
    assert seite["hier"] == "Rotfuchs" and "Rotfuchs" in pfade and "Vulpes_vulpes" not in pfade and "Stadtfuchs" not in pfade
    assert pfade == sorted(pfade) and not any(p.startswith("_") for p in pfade)
    r = (await c.get(f"/api/v1/stoebern/blaettern/{buch}", params={"buchstabe": "R", "anzahl": 3})).json()
    assert r["eintraege"][0]["pfad"] >= "R"
    alle = (await c.get(f"/api/v1/stoebern/blaettern/{buch}", params={"buchstabe": "A", "anzahl": 3})).json()
    weiter = (await c.get(f"/api/v1/stoebern/blaettern/{buch}", params={"ab": alle["naechste"], "anzahl": 3})).json()
    zurueck = (await c.get(f"/api/v1/stoebern/blaettern/{buch}", params={"bis": weiter["erste"], "anzahl": 3})).json()
    assert zurueck["eintraege"] == alle["eintraege"] and weiter["eintraege"][0]["pfad"] > alle["eintraege"][-1]["pfad"]
    await c.put("/api/v1/meins/verlauf/lesestand", json={"buch": buch, "pfad": z["pfad"], "titel": z["titel"], "anteil": 0.1})
    for _ in range(5):
        assert (await c.get(f"/api/v1/stoebern/zufall/{buch}", params={"ungelesen": True})).json()["pfad"] != z["pfad"]


async def test_medien_im_artikel_und_suche(nachschlag):
    """Bilder eines Artikels mit Unterschrift und Abschnitt, jedes einmal; die Mediensuche sammelt Bilder der Artikel zur
    Frage, passende Unterschriften zuerst."""
    c, _, _ = nachschlag
    buch = "probe_de_all_2026-01"
    m = (await c.get(f"/api/v1/medien/artikel/{buch}/Rotfuchs")).json()
    assert m and len({x["bild"] for x in m}) == len(m) and all(x["pfad"] == "Rotfuchs" and x["artikel"] == "Rotfuchs" for x in m)
    assert m[0]["datei"] and m[0]["bild"].startswith("/api/v1/inhalt/medien/")
    e = (await c.get("/api/v1/medien", params={"frage": "Fuchs", "buecher": buch})).json()
    assert e["artikel"] >= 1 and e["medien"]
    if e["passend"]:
        assert "fuchs" in e["medien"][0]["unterschrift"].casefold()
    assert (await c.get(f"/api/v1/medien/artikel/{buch}/GibtEsNicht")).status_code == 404


def test_stimmen_mit_tausenderpunkt():
    from app.bausteine.frage_antwort import _deutsche_zahl
    assert (_deutsche_zahl("27527"), _deutsche_zahl("-3"), _deutsche_zahl("1234567"), _deutsche_zahl("x")) == ("27.527", "-3", "1.234.567", "x")


def test_stimmen_zaehlen_als_zahl_trotz_tausenderpunkt():
    """Steckbrief und Reihenfolge rechnen mit der Zahl; geschrieben wird mit Punkt (WIKI-38: Steckbrief zeigte 0)."""
    from lxml import html as lhtml
    from app.bausteine.frage_antwort import _beitrag
    kasten, stimmen, _ = _beitrag(lhtml.fromstring('<div data-score="27527"><div class="js-post-body"><p>x</p></div></div>'), "gefragt")
    assert stimmen == 27527 and kasten.xpath("string(.//span[@class='zahl'])") == "27.527"
    assert _beitrag(lhtml.fromstring('<div data-score="-3"></div>'), "beantwortet")[1] == -3


def test_verschachtelter_code_einmal_entmaskiert():
    """Stack Overflow: eingerückter Code als Block im Block, dort doppelt maskiert; der äußere Block bleibt, wie er ist."""
    from lxml import html as lhtml
    from app.bausteine.code import code_text
    pre = lhtml.fromstring("<pre><code>#include &lt;ctime&gt;\n<pre><code>if (c &amp;lt; n) cout &amp;lt;&amp;lt; &amp;quot;x&amp;quot;;</code></pre>"
                           "</code></pre>")
    assert code_text(pre) == '#include <ctime>\nif (c < n) cout << "x";'
    absichtlich = lhtml.fromstring("<pre><code>s.replace('&lt;', '&amp;lt;')</code></pre>")
    assert code_text(absichtlich) == "s.replace('<', '&lt;')"


def test_formeln_als_mathml_ohne_ersatzbild():
    """Formeln der Quelle (verstecktes MathML und schwarzes Ersatzbild) werden zu sichtbarem MathML ohne Bild und ohne
    TeX-Quelle; der Text danach bleibt; abgesetzte Formeln stehen in einem eigenen Kasten."""
    from lxml import html as lhtml
    from app.bausteine import html as h
    quelle = (
        '<div><p>Es gilt <span class="mwe-math-element mwe-math-element-inline"><span class="mwe-math-mathml-inline" '
        'style="display: none;"><math xmlns="http://www.w3.org/1998/Math/MathML" alttext="x+4"><semantics><mrow><mi>x</mi>'
        '<mo stretchy="false">+</mo><mn>4</mn></mrow><annotation encoding="application/x-tex">x+4</annotation></semantics>'
        '</math></span><img class="mwe-math-fallback-image-inline" src="formel.svg" alt="x+4"></span> und weiter.</p>'
        '<span class="mwe-math-element mwe-math-element-block"><span style="display: none;"><math display="block">'
        '<mi>E</mi></math></span><img src="block.svg"></span> danach</div>')
    wurzel = lhtml.fragment_fromstring(quelle)
    h.formeln_setzen(wurzel)
    h.stile_uebersetzen(wurzel)
    h.saeubern(wurzel)
    text = h.als_html(wurzel)
    assert "<img" not in text and "annotation" not in text and "x+4</annotation" not in text
    assert '<math alttext="x+4"><semantics><mrow><mi>x</mi><mo stretchy="false">+</mo><mn>4</mn></mrow></semantics></math> und weiter.' in text
    assert '<div class="formel"><math display="block"><mi>E</mi></math></div> danach' in text


def test_fehlende_bilder_fallen_weg():
    """Ein Bild, dessen Datei das Buch nicht enthält, kommt nicht in den Artikel (in einer Abbildung samt Unterschrift)
    und wird nie Leitbild."""
    from lxml import html as lhtml
    from app.bausteine import html as h
    from app.bausteine.basis import Wege
    wege = Wege(artikel=lambda b, p: f"/lesen/{b}/{p}", medien=lambda b, p: f"/m/{b}/{p}", original=lambda b, p: "",
                gibt_es=lambda b, p: p == "_assets_/da.jpg", datei=lambda b, p: None)
    wurzel = lhtml.fragment_fromstring('<div><figure><img src="./_assets_/fehlt.jpg" width="300"><figcaption>weg</figcaption></figure>'
                                       '<p>Text <img src="./_assets_/fehlt2.png" width="200"> mehr</p>'
                                       '<figure><img src="./_assets_/da.jpg" width="250"><figcaption>bleibt</figcaption></figure></div>')
    erstes = h.bilder_umschreiben(wurzel, "buch", "Artikel", wege)
    text = h.als_html(wurzel)
    assert erstes == "/m/buch/_assets_/da.jpg"
    assert "fehlt" not in text and "weg</figcaption>" not in text and "bleibt" in text and "Text  mehr" in text


async def test_meins_trennt_konten(tmp_path):
    """Was ein Konto merkt, sieht kein anderes."""
    from appkern.datenbank import Datenbank
    from app.meins import Meins
    from app.modell.meins import Merken, NotizAenderung, NotizNeu
    from app.modell.themen import EintragNeu, ThemaNeu
    from app.themen import Themen
    db = await Datenbank(tmp_path / "meins.sqlite").oeffnen()
    try:
        async def name(k): return k.rsplit("_", 1)[0]
        async def kennung(n): return n + "_2026-01"
        meins = Meins(db, name, kennung)
        await meins.starten()
        await meins.merken("eins", Merken(buch="probe_2026-01", pfad="A", titel="A"))
        assert len(await meins.merkzettel("eins")) == 1 and await meins.merkzettel("zwei") == []
        assert not await meins.vergessen("zwei", (await meins.merkzettel("eins"))[0].id)
        notiz = await meins.notieren("eins", NotizNeu(buch="probe_2026-01", pfad="A", titel="A", text="nur meins"))
        assert await meins.notizen("zwei") == [] and not await meins.notiz_loeschen("zwei", notiz.id)
        assert await meins.notiz_aendern("zwei", notiz.id, NotizAenderung(text="fremd")) is None
        themen = Themen(db, name, kennung)
        await themen.starten()
        t = await themen.anlegen("eins", ThemaNeu(titel="Meins"))
        assert await themen.liste("zwei") == [] and await themen.thema("zwei", t.id) is None
        assert await themen.bereich_anlegen("zwei", t.id, "fremd") is None and not await themen.loeschen("zwei", t.id)
        assert await themen.eintragen("zwei", t.id, EintragNeu(buch="probe_2026-01", pfad="A", titel="A")) is None
    finally:
        await db.schliessen()
