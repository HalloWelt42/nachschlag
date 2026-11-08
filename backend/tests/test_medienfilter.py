"""WIKI-24: Medien kennen ihre Art (Bild, Karte, Ton) und ob das große Bild geholt ist; die Mediensuche filtert danach."""

from app.medien.dienst import Medien, medien_aus, pfad_im_buch
from app.modell.artikel import Artikel

HTML = """
<h2>Lage</h2>
<figure><img src="/api/v1/inhalt/medien/wp/_assets_/ab/Saturn_Lagekarte.png" width="300" height="200">
  <figcaption>Lage im Sonnensystem</figcaption></figure>
<h2>Aufbau</h2>
<figure><img src="/api/v1/inhalt/medien/wp/_assets_/cd/Saturn_Ringe.jpg" width="400" height="300">
  <figcaption>Die Ringe</figcaption></figure>
<figure><audio controls><source src="/api/v1/inhalt/medien/wp/_assets_/ef/Saturn_Klang.ogg"></audio>
  <figcaption>Radiowellen als Ton</figcaption></figure>
"""


def artikel() -> Artikel:
    return Artikel.model_construct(buch="wp", pfad="Saturn", titel="Saturn", html=HTML, steckbrief=None)


def test_arten_und_pfad_im_buch():
    m = medien_aus(artikel())
    assert [(x.art, x.abschnitt) for x in m] == [("karte", "Lage"), ("bild", "Aufbau"), ("ton", "Aufbau")]
    assert m[2].unterschrift == "Radiowellen als Ton" and m[2].datei == "Saturn_Klang.ogg"
    assert pfad_im_buch(m[1].bild) == "_assets_/cd/Saturn_Ringe.jpg" and pfad_im_buch("/anders/x.png") == ""


class Leser:
    async def lesen(self, buch, pfad):
        return artikel()


class Suche:
    async def suchen(self, frage, buecher, anzahl, wege):
        return type("E", (), {"treffer": [type("T", (), {"buch": "wp", "pfad": "Saturn"})()]})()


async def test_filter_nach_art_und_gross():
    geholt = {"_assets_/cd/Saturn_Ringe.jpg"}
    m = Medien(Leser(), Suche(), lambda buch, pfad: pfad in geholt)
    alle = (await m.suchen("Ringe", [])).medien
    assert alle[0].datei == "Saturn_Ringe.jpg" and [x.gross for x in alle].count(True) == 1     # Passendes zuerst
    assert [x.art for x in (await m.suchen("Saturn", [], "karte")).medien] == ["karte"]
    assert [x.art for x in (await m.suchen("Saturn", [], "ton")).medien] == ["ton"]
    assert [x.datei for x in (await m.suchen("Saturn", [], None, True)).medien] == ["Saturn_Ringe.jpg"]


def test_karten_wortgenau():
    from app.medien.dienst import KARTE
    assert all(KARTE.search(s) for s in ["Saturn_Lagekarte.png", "Fox_range.png", "World_map.svg", "grün eingefärbten Gebieten"])
    assert not any(KARTE.search(s) for s in ["In den orangen Gebieten", "Arrangement.jpg", "Orange.jpg", "Mapuche.jpg"])
