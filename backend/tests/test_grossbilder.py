"""Große Bilder in Nachschlag (WIKI-80): Namen im Wiki aus Pfaden im Buch, Bilder mit großem Original im Artikel,
Vormerken beim Bildholer (geöffnet zuerst, Gelesenes einmal), Regeln, Ablage lesen, Medienweg mit gross."""

from __future__ import annotations

from pathlib import Path

import httpx
from lxml import html as lhtml

from app.bausteine import html as h
from app.bausteine.basis import Wege
from app.bilder import Grossbilder, grosse_bilder, wiki_name
from app.modell.artikel import Artikel
from bildholer import ablage
from bildholer.api import app_bauen
from bildholer.modelle import Regeln

BUCH = "wikipedia_de_all_maxi_2026-01"


def test_wiki_name():
    assert wiki_name("_assets_/0c70/Saturn_from_Cassini_Orbiter_(2004-10-06).jpg") == "Saturn_from_Cassini_Orbiter_(2004-10-06).jpg"
    assert wiki_name("_assets_/0c70/Plasma_magnet_saturn.svg.png") == "Plasma_magnet_saturn.svg"
    assert wiki_name("_assets_/a/K%C3%B6ln%2C_Ufer.jpg.webp") == "Köln,_Ufer.jpg"
    assert wiki_name("Saturn_(Planet)") is None and wiki_name("_assets_/a/") is None


def test_bilder_mit_grossem_original_markiert():
    wege = Wege(artikel=lambda b, p: f"/lesen/{b}/{p}", medien=lambda b, p: f"/api/v1/inhalt/medien/{b}/{p}",
                original=lambda b, p: "", gibt_es=lambda b, p: True)
    wurzel = lhtml.fragment_fromstring(
        '<div><img src="./_assets_/x/Gross.jpg" width="310" data-file-width="8888">'
        '<img src="./_assets_/x/Klein.png" width="200" data-file-width="278">'
        '<img src="./_assets_/x/Symbol.svg.png" width="24" data-file-width="400"></div>')
    h.bilder_umschreiben(wurzel, BUCH, "Saturn_(Planet)", wege)
    html = lhtml.tostring(wurzel, encoding="unicode")
    assert grosse_bilder(html) == ["_assets_/x/Gross.jpg"] and 'data-gross="8888"' in html


def _artikel(html: str, pfad: str = "Saturn_(Planet)") -> Artikel:
    return Artikel(buch=BUCH, pfad=pfad, angefragt=pfad, titel="Saturn", darstellung="lesedesign", baustein="enzyklopaedie",
                   html=html, original="")


class Leser:
    def __init__(self) -> None:
        self.gelesen: list[str] = []

    async def lesen(self, buch: str, pfad: str) -> Artikel:
        self.gelesen.append(pfad)
        return _artikel(f'<img data-gross="900" src="/api/v1/inhalt/medien/{buch}/_assets_/x/{pfad}.jpg">', pfad)


async def test_vormerken_regeln_und_gelesene_einmal(tmp_path: Path):
    bildholer = app_bauen(tmp_path / "daten", tmp_path / "bilder", arbeiten=False)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=bildholer))
    leser = Leser()

    async def gelesen() -> list[tuple[str, str]]:
        return [(BUCH, "Mond"), ("klexikon_de_all_maxi_2026-11", "Fuchs"), (BUCH, "Mars")]

    g = Grossbilder(lambda: str(tmp_path / "bilder"), lambda: "http://bildholer", lambda: Regeln(abstand_s=7),
                    lambda: True, leser, [gelesen], client)
    await g.geoeffnet(_artikel('<p><img data-gross="8888" src="/api/v1/inhalt/medien/x/_assets_/h/Saturn.jpg"></p>'))
    s = await g.stand()
    assert s and s.offen == {"0": 1} and s.abstand_s == 7                     # Regeln gingen vor dem Vormerken mit
    assert await g.gelesene_vormerken() == 2 and leser.gelesen == ["Mond", "Mars"]   # Klexikon ist kein Wiki von Wikimedia
    assert await g.gelesene_vormerken() == 0 and leser.gelesen == ["Mond", "Mars"]   # jeder Artikel einmal
    assert (await g.stand()).offen == {"0": 1, "1": 2}
    assert (await g.anhalten(True)).zustand == "angehalten"
    assert (await g.verbindung()).ok


async def test_ablage_lesen_und_ohne_bildholer(tmp_path: Path):
    ablage.ablegen(tmp_path, b"GROSS", ablage.Angaben(quelle="de.wikipedia.org", name="Saturn.svg", breite=1280, hoehe=640,
                                                      original=8888, bytes=5, mime="image/png", am="2026-11-08T14:00:00+01:00"))
    g = Grossbilder(lambda: str(tmp_path), lambda: "http://nirgends.invalid", lambda: Regeln(), lambda: True, Leser(), [],
                    httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    pfad, angaben = g.finden(BUCH, "_assets_/x/Saturn.svg.png")
    assert pfad.read_bytes() == b"GROSS" and angaben.original == 8888
    assert g.finden(BUCH, "_assets_/x/Fehlt.jpg") is None and g.finden("klexikon_de_all_maxi_2026-11", "_assets_/x/Saturn.svg.png") is None
    assert await g.stand() is None and await g.vormerken(BUCH, ["_assets_/x/A.jpg"], 0) == 0
    assert not (await g.verbindung()).ok
