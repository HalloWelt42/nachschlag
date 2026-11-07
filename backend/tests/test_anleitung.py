"""Inhaltsart Anleitung (iFixit, WIKI-64): Erkennen an der Kategorie, Bausteine Anleitung, Gerät und Startseite, Sprache
aus dem Text, Zeitspanne."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.artikel import Artikelleser, wege  # noqa: E402
from app.bausteine.anleitung import zeitspanne  # noqa: E402
from app.bibliothek import Bibliothek  # noqa: E402
from app.bibliothek.ordner import art_aus  # noqa: E402
from app.eigenindex import aufbau, schema  # noqa: E402
from app.textsprache import sprache_von  # noqa: E402
from test_eigenindex import _inhalt  # noqa: E402

BUCH = "probefix_de_all_2026-03"


@pytest.fixture(scope="module")
def leser(tmp_path_factory) -> Artikelleser:
    ordner = tmp_path_factory.mktemp("anleitungen")
    probebuch.bauen_anleitungen(ordner)
    return Artikelleser(Bibliothek(lambda: str(ordner)))


def test_art_und_zeit_und_sprache():
    assert art_aus("", "", "iFixit;_pictures:yes;_category:iFixit") == "anleitung"
    assert art_aus("mwoffliner 1.17", "", "_category:iFixit") == "enzyklopaedie"      # ein Erzeuger geht vor
    assert zeitspanne("1 - 2 Stunden") == (60, 120) and zeitspanne("30 Minuten - 1 Stunde") == (30, 60)
    assert zeitspanne("10 Minuten") == (10, 10) and zeitspanne("Keine Schätzung") == (None, None)
    assert zeitspanne("30 Sekunden - 2 Stunden") == (0, 120)
    assert sprache_von("Löse die Schrauben und hebe die Abdeckung mit dem Spudger an, wenn du kannst") == "de"
    assert sprache_von("Remove the screws and lift the cover with the spudger if you can, it is easy") == "en"
    assert sprache_von("iPad 7") == ""


async def test_anleitung(leser):
    buch = await leser._bib.buch(BUCH)
    assert buch.art == "anleitung" and buch.faehigkeiten.lesedesign
    a = await leser.lesen(BUCH, "Anleitung/Probephone+Akku+tauschen/1")
    assert a.darstellung == "anleitung" and a.titel == "Probephone Akku tauschen"
    x = a.anleitung
    assert (x.art, x.sprache, x.schwierigkeit, x.zeit_von, x.zeit_bis, x.autor) == ("anleitung", "de", 2, 30, 60, "Tester")
    assert [w.name for w in x.werkzeuge] == ["Spudger", "Pinzette"] and [t.name for t in x.teile] == ["Akku"]
    assert len(x.schritte) == 2 and len(x.schritte[0].bilder) == 2 and x.schritte[0].bilder[0].startswith("/api/v1/inhalt/medien/")
    marken = [(z.stufe, z.marke, z.farbe) for z in x.schritte[1].zeilen]
    assert marken == [(0, "", ""), (1, "", "red"), (1, "", "yellow"), (0, "hinweis", "")]
    assert x.schritte[0].zeilen[0].marke == "vorsicht"
    assert "Schritt 2" in a.html and "Kamera" in a.html                            # Lesetext für Volltext und Vorlesen
    englisch = (await leser.lesen(BUCH, "Anleitung/Probephone+Display+Replacement/2")).anleitung
    assert englisch.sprache == "en" and englisch.schwierigkeit == 4
    assert (await leser.lesen(BUCH, "Teardown/Probephone+Teardown/3")).anleitung.art == "zerlegung"


async def test_geraet_kategorie_start_und_rest(leser):
    g = await leser.lesen(BUCH, "Device/Probephone")
    assert g.darstellung == "geraet" and g.titel == "Probephone" and g.geraet.kurz.startswith("Ein Telefon")
    assert [(e.pfad, e.titel, e.empfohlen) for e in g.geraet.anleitungen] == [
        ("Anleitung/Probephone+Akku+tauschen/1", "Probephone Akku tauschen", True),
        ("Anleitung/Probephone+Display+Replacement/2", "Display", False), ("Teardown/Probephone+Teardown/3", "Zerlegung", False)]
    assert [e.bauteil for e in g.geraet.anleitungen] == ["Akku", "Display", "Zerlegung"]   # hervorgehoben: Bauteil aus der Liste
    assert g.geraet.werkzeuge == ["Spudger", "Pinzette"] and "nur in den Tests" in g.html
    k = await leser.lesen(BUCH, "Device/Phone")
    assert [(e.pfad, e.titel) for e in k.geraet.unterkategorien] == [("Device/Probephone", "Probephone")]
    s = await leser.lesen(BUCH, "home/home")
    assert s.darstellung == "anleitungen" and [e.titel for e in s.geraet.unterkategorien] == ["Smartphones"]
    assert (await leser.lesen(BUCH, "User/1/x")).darstellung == "original"


def _index(ordner: Path, kennung: str, ziel: Path, **weiter) -> aufbau.Stand:
    bib = Bibliothek(lambda: str(ordner))
    archiv, buch = bib.geoeffnet(kennung)
    return aufbau.bauen(archiv, buch, wege(bib), ziel, **weiter)


def test_index_der_anleitungen_und_neue_fassung(tmp_path):
    """Nur Anleitungen und Geräteseiten kommen hinein (die Benutzerseite nicht), mit Sprache, Angaben, Werkzeugen und dem
    Baum; eine neue Fassung übernimmt alles davon unverändert aus der vorigen."""
    ordner = tmp_path / "b"
    probebuch.bauen_anleitungen(ordner)
    alt = tmp_path / "ix" / schema.dateiname(BUCH)
    alt.parent.mkdir()
    assert _index(ordner, BUCH, alt).fertig
    i = _inhalt(alt)
    assert [s[0] for s in i["seiten"]] == ["Anleitung/Probephone+Akku+tauschen/1", "Anleitung/Probephone+Display+Replacement/2",
                                           "Device/Phone", "Device/Probephone", "Teardown/Probephone+Teardown/3", "home/home"]
    assert ("User/1/x",) in [(o[0],) for o in i["ohne"]]
    assert i["anleitungen"][0] == ("Anleitung/Probephone+Akku+tauschen/1", "anleitung", "de", 2, "Mittel", "30 Minuten - 1 Stunde",
                                   30, 60, 2, "images/haupt.png")                       # Bild als Pfad im Buch
    assert [(a[0].split("/")[0], a[2]) for a in i["anleitungen"]] == [("Anleitung", "de"), ("Anleitung", "en"), ("Teardown", "de")]
    assert ("Spudger", "de", 2) in i["register_werkzeuge"] and ("Heat Gun", "en", 1) in i["register_werkzeuge"]
    assert i["geraet_kind"] == [("Device/Phone", "Device/Probephone"), ("home/home", "Device/Phone")]
    assert ("Device/Probephone", "Anleitung/Probephone+Akku+tauschen/1", "Akku", 1) in i["geraet_anleitung"]
    assert i["geraete"][1] == ("Device/Probephone", "images/g.png", "Ein Telefon für die Tests, gebaut 2026.")

    probebuch.bauen_anleitungen(ordner, "probefix_de_all_2026-06")
    neu = tmp_path / "ix" / schema.dateiname("probefix_de_all_2026-06")
    stand = _index(ordner, "probefix_de_all_2026-06", neu, vorlage=alt)
    assert stand.uebernommen == stand.seiten == 6 and _inhalt(neu) == i
