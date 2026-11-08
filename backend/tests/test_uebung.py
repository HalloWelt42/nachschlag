"""Inhaltsart Übungen (freeCodeCamp, fcc2zim, WIKI-66): Erkennen am Erzeuger, Aufgabe aus dem Markdown, Startseite aus
der Gliederung, Sprung in die Skript-Anwendung ist keine Weiterleitung, Index mit allen Aufgaben."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.artikel import Artikelleser, wege  # noqa: E402
from app.bibliothek import Bibliothek  # noqa: E402
from app.bibliothek.ordner import sprungziel  # noqa: E402
from app.eigenindex import abfrage, aufbau, schema  # noqa: E402

BUCH = "probecamp_de_all_2026-10"


@pytest.fixture(scope="module")
def ordner(tmp_path_factory) -> Path:
    o = tmp_path_factory.mktemp("uebungen")
    probebuch.bauen_uebungen(o)
    probebuch.bauen(o)
    return o


def test_sprung_in_die_anwendung_ist_keine_weiterleitung():
    assert sprungziel("text/html", b"<meta http-equiv=\"refresh\" content=\"0;URL='Rotfuchs#Merkmale'\" />") == ("Rotfuchs", "Merkmale")
    assert sprungziel("text/html", probebuch._sprung_in_anwendung("k/b/a1").encode()) is None
    assert sprungziel("text/markdown", b"<meta http-equiv=refresh content='0;URL=x'>") is None


async def test_aufgabe_und_startseite(ordner):
    leser = Artikelleser(Bibliothek(lambda: str(ordner)))
    b = await leser._bib.buch(BUCH)
    assert b.art == "uebung" and b.faehigkeiten.lesedesign
    a = await leser.lesen(BUCH, "index/grundlagen/rechnen/a1.html")
    assert a.darstellung == "uebung" and a.pfad == "index/grundlagen/rechnen/a1.html" and a.titel == "Summe bilden"
    u = a.uebung
    assert (u.kurs_titel, u.block_titel, u.nr, u.anzahl) == ("Grundlagen der Programmierung", "Rechnen", 1, 2)
    assert u.vorige is None and u.naechste.pfad == "index/grundlagen/rechnen/a2.html"
    assert "<code>summe</code>" in u.beschreibung and "<code>+</code>" in u.anleitung
    assert [h.test for h in u.hinweise] == ["assert(typeof summe === 'function');", "assert.strictEqual(summe(1, 2), 3);"]
    assert u.startcode[0].sprache == "js" and "function summe(a, b)" in u.startcode[0].code
    assert "return a + b" in u.loesungen[0].code and "return" not in u.startcode[0].code
    zwei = (await leser.lesen(BUCH, "index/grundlagen/rechnen/a2.html")).uebung   # Markdown mit anderer Dateiart
    assert zwei.nr == 2 and zwei.vorige.titel == "Summe bilden" and "multipliziert" in zwei.beschreibung
    s = await leser.lesen(BUCH, "index.html")
    assert s.darstellung == "uebungen" and s.rubrik == "2 Aufgaben"
    [k] = s.kurse.kurse
    assert k.einleitung == ["Erste Schritte mit JavaScript."] and k.bloecke[0].einleitung == ["Zahlen verknüpfen."]
    assert [x.titel for x in k.bloecke[0].aufgaben] == ["Summe bilden", "Produkt bilden"]
    # ein Abschnittssprung eines Lexikons bleibt eine Weiterleitung
    assert (await leser.lesen("probe_de_all_2026-01", "Rotfuchs")).titel == "Rotfuchs"


def test_index_mit_allen_aufgaben(ordner, tmp_path):
    bib = Bibliothek(lambda: str(ordner))
    archiv, b = bib.geoeffnet(BUCH)
    ziel = tmp_path / schema.dateiname(BUCH)
    stand = aufbau.bauen(archiv, b, wege(bib), ziel)
    assert stand.fertig and stand.seiten == 3                   # Startseite und zwei Aufgaben
    funde, _ = abfrage.suchen(ziel, "multipliziert")
    assert funde[0].pfad == "index/grundlagen/rechnen/a2.html"
