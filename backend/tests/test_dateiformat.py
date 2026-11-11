"""Buchart Dateiformat (WIKI-87): Erkennen am Erzeuger, Steckbrief, Texte je Quelle mit aufklappbarer Fassung,
Startseite als Übersicht der Kategorien."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.artikel import Artikelleser  # noqa: E402
from app.bibliothek import Bibliothek  # noqa: E402
from app.bibliothek.ordner import art_aus  # noqa: E402

BUCH = "dateiformate_de_all_2026-11"


@pytest.fixture(scope="module")
def leser(tmp_path_factory) -> Artikelleser:
    ordner = tmp_path_factory.mktemp("dateiformate")
    probebuch.bauen_dateiformate(ordner)
    return Artikelleser(Bibliothek(lambda: str(ordner)))


def test_art():
    assert art_aus("dateiformate v0.1.0") == "dateiformat"


async def test_buchsymbol(leser, tmp_path):
    """WIKI-88: ein Buch, das ein Symbol mitbringt, nennt dessen Adresse; ohne Symbol bleibt sie leer."""
    buch = await leser._bib.buch(BUCH)
    assert buch.symbol == f"/api/v1/inhalt/symbol/{BUCH}"
    assert (await leser._bib.symbol(BUCH)) == probebuch.PNG
    ohne = tmp_path / "ohne"
    probebuch.bauen(ohne, "probe_de_all_2026-01")
    andere = Bibliothek(lambda: str(ohne))
    assert (await andere.buch("probe_de_all_2026-01")).symbol == ""


async def test_formatseite(leser):
    buch = await leser._bib.buch(BUCH)
    assert buch.art == "dateiformat" and buch.faehigkeiten.lesedesign
    a = await leser.lesen(BUCH, "format/png")
    assert a.baustein == "dateiformat" and a.darstellung == "lesedesign"
    assert a.titel == "PNG - Portable Network Graphics"
    assert a.einleitung == "Rasterbild mit verlustfreier Kompression."
    assert a.steckbrief and "<dt>Endungen</dt>" in a.steckbrief.html and "image/png" in a.steckbrief.html
    assert "steckbrief" not in a.html and "<h1" not in a.html
    assert [(x.titel, x.ebene) for x in a.abschnitte] == [("Formatbeschreibung", 2), ("Aufbau", 3)]   # ohne die Fassung
    assert "<details" in a.html and "Englisches Original" in a.html
    assert 'class="wl"' in a.html and "Fehlt" in a.html and 'href="fehlt"' not in a.html
    assert a.bild.startswith("/api/v1/inhalt/medien/") and "https://example.org/png/" in a.online
    assert [(k.pfad, k.titel) for k in a.kategorien] == [("kategorie/bild", "Bild")]


async def test_kategorieseite(leser):
    a = await leser.lesen(BUCH, "kategorie/bild")
    assert a.darstellung == "kategorie" and a.titel == "Bild"
    k = a.kategorie
    assert [(x.pfad, x.titel) for x in k.ober] == [("kategorie/medien", "Bild, Ton und Modelle")]
    assert [(x.pfad, x.titel) for x in k.seiten] == [("format/png", "PNG"), ("format/gif", "GIF")]
    assert "Bilder aller Art" in a.html and "Über diese Kategorie" in a.html
    ober = await leser.lesen(BUCH, "kategorie/medien")
    assert [(x.pfad, x.titel) for x in ober.kategorie.unter] == [("kategorie/bild", "Bild")]


async def test_startseite(leser):
    a = await leser.lesen(BUCH, "index")
    assert a.darstellung == "uebersicht"
    assert [(g.titel, [(e.pfad, e.titel) for e in g.eintraege]) for g in a.gruppen] == [
        ("Bild, Ton und Modelle", [("kategorie/bild", "Bild")])]
