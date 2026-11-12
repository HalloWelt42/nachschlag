"""Kategorien in Büchern, die sie mitbringen (WIKI-75): Leiste am Artikel ohne Wartungskategorien, Kategorieseite mit
Ober- und Unterkategorien und allen Seiten aus den nachgeladenen Teilen; Bücher ohne Kategorien bleiben wie zuvor."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.artikel import Artikelleser  # noqa: E402
from app.bibliothek import Bibliothek  # noqa: E402

BUCH = "probekat_de_all_maxi_2026-11"


@pytest.fixture(scope="module")
def leser(tmp_path_factory) -> Artikelleser:
    o = tmp_path_factory.mktemp("kategorien")
    probebuch.bauen_kategorien(o)
    probebuch.bauen(o)
    return Artikelleser(Bibliothek(lambda: str(o)))


async def test_kategorien_am_artikel_und_kategorieseite(leser):
    a = await leser.lesen(BUCH, "Tier03")
    assert a.darstellung == "lesedesign" and [(k.pfad, k.titel) for k in a.kategorien] == [("Kategorie:Tiere", "Tiere")]
    k = await leser.lesen(BUCH, "Kategorie:Tiere")
    assert k.darstellung == "kategorie" and k.titel == "Tiere" and "Alle Tiere" in k.html
    assert [s.pfad for s in k.kategorie.seiten] == ["Tier01", "Tier02", "Tier03", "Tier04", "Tier05"]   # alle Teile, nicht nur zwei
    assert [u.titel for u in k.kategorie.unter] == ["Kategorie:Füchse"] and k.kategorie.ober == []      # Alles gibt es nicht
    assert k.rubrik == "Kategorie · 1 Unterkategorien · 5 Seiten"
    f = await leser.lesen(BUCH, "Kategorie:Füchse")
    assert [o.pfad for o in f.kategorie.ober] == ["Kategorie:Tiere"] and [s.pfad for s in f.kategorie.seiten] == ["Tier05"]
    ohne = await leser.lesen("probe_de_all_2026-01", "Rotfuchs")       # Lexikon ohne Kategorien: keine Leiste
    assert ohne.kategorien == []


async def test_kategorienbaum_einer_seite(leser):
    """WIKI-96: je Kategorie der Seite ihre Oberkategorien und andere Seiten darin, die eigene nicht; ohne Kategorien
    kein Baum."""
    baum = await leser.kategorienbaum(BUCH, "Tier05", je=3)
    tiere = next(z for z in baum if z.kategorie.titel == "Tiere")
    assert [s.pfad for s in tiere.seiten] == ["Tier01", "Tier02", "Tier03"] and tiere.seiten_gesamt == 5
    fuechse = next((z for z in baum if z.kategorie.pfad == "Kategorie:Füchse"), None)
    if fuechse is not None:                                             # Tier05 steht auch bei den Füchsen
        assert [o.pfad for o in fuechse.ober] == ["Kategorie:Tiere"] and fuechse.seiten == []
    assert await leser.kategorienbaum("probe_de_all_2026-01", "Rotfuchs") == []
