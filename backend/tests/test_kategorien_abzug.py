"""Kategorien aus den Datenabzügen von Wikimedia (WIKI-75): ein kleiner Abzug im Aufbau der echten Dateien (page,
linktarget, categorylinks mit cl_target_id, page_props, Namensräume) wird geladen und aufbereitet, daraus entstehen die
Kategorien des Probebuchs; Nachschlag zeigt sie am Artikel und als Kategorieseite. Versteckte Kategorien fehlen, Kreise
im Baum halten nicht auf, Kategorien ohne Seite des Buchs fehlen."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.artikel import Artikelleser  # noqa: E402
from app.bibliothek import Bibliothek, EintragFehlt  # noqa: E402
from app.eigenindex.ablage import Eigenindizes  # noqa: E402
from app.kategorien import aufbau, schema  # noqa: E402
from app.kategorien.abfrage import Kategorienindex  # noqa: E402
from app.kategorien.abzug import Abzuege  # noqa: E402
from app.kategorien.wikis import wiki  # noqa: E402

BUCH = "probe_de_all_2026-01"

# Seiten: Artikel 1 bis 4 (4 ist eine Weiterleitung), Kategorieseiten 10 bis 15 (13 ist versteckt)
PAGE = [(1, 0, "Rotfuchs", 0), (2, 0, "Svante_Arrhenius", 0), (3, 0, "Nicht_im_Buch", 0), (4, 0, "Vulpes_vulpes", 1),
        (10, 14, "Füchse", 0), (11, 14, "Tiere", 0), (12, 14, "Alles", 0), (13, 14, "Wartung", 0), (14, 14, "Schwede", 0),
        (15, 14, "Leer", 0)]
LINKTARGET = [(100, "Füchse"), (101, "Tiere"), (102, "Alles"), (103, "Wartung"), (104, "Schwede"), (105, "Leer")]
# (von, Art, Ziel): Rotfuchs in Füchse und Wartung, Arrhenius in Schwede, Nicht_im_Buch in Leer; Füchse in Tiere, Tiere in
# Alles und (Kreis) in Füchse, Schwede in Alles
CATEGORYLINKS = [(1, "page", 100), (1, "page", 103), (2, "page", 104), (3, "page", 105), (10, "subcat", 101),
                 (11, "subcat", 102), (11, "subcat", 100), (14, "subcat", 102)]


def _sql(tabelle: str, zeilen: list[str], je_zeile: bool = True) -> bytes:
    """Wie die Abzüge heute (ein Datensatz je Zeile) oder früher (alle Werte hinter dem INSERT in einer Zeile)."""
    kopf = f"-- MySQL dump\nCREATE TABLE `{tabelle}` (\n  `x` int\n) ENGINE=InnoDB;\n"
    werte = ",\n".join(zeilen) if je_zeile else ",".join(zeilen)
    return gzip.compress((kopf + f"INSERT INTO `{tabelle}` VALUES" + ("\n" if je_zeile else " ") + werte + ";\n").encode())


def _dateien() -> dict[str, bytes]:
    return {
        "page": _sql("page", [f"({i},{ns},'{t}',{u},0,0.5,'20261101000000','20261101000000',1,100,'wikitext',NULL)"
                              for i, ns, t, u in PAGE]),
        "linktarget": _sql("linktarget", [f"({i},14,'{t}')" for i, t in LINKTARGET] + ["(200,0,'Rotfuchs')"]),
        "categorylinks": _sql("categorylinks", [f"({v},'SCHLUESSEL','2026-11-01 00:00:00','','{a}',1,{z})"
                                                for v, a, z in CATEGORYLINKS]),
        "page_props": _sql("page_props", ["(13,'hiddencat','',NULL)", "(1,'wikibase_item','Q8332',NULL)"], je_zeile=False),
        "siteinfo-namespaces": gzip.compress(json.dumps({"query": {"namespaces": {"14": {"*": "Kategorie"}}}}).encode()),
    }


@pytest.fixture(scope="module")
def ordner(tmp_path_factory) -> Path:
    o = tmp_path_factory.mktemp("abzug")
    probebuch.bauen(o)
    dateien = _dateien()

    def antworten(anfrage: httpx.Request) -> httpx.Response:
        name = anfrage.url.path.rsplit("/", 1)[-1]
        tabelle = name.removeprefix("dewiki-latest-").removesuffix(".sql.gz").removesuffix(".json.gz")
        return httpx.Response(200, content=dateien[tabelle], headers={"Last-Modified": "Fri, 06 Nov 2026 10:00:00 GMT"})

    abzug = Abzuege(o / "abzuege", httpx.Client(transport=httpx.MockTransport(antworten)), alter_tage=10_000).bereit("dewiki")
    assert abzug is not None
    archiv, _ = Bibliothek(lambda: str(o)).geoeffnet(BUCH)
    (o / "kategorien").mkdir()
    stand = aufbau.bauen(archiv, BUCH, abzug, o / "kategorien" / schema.dateiname(BUCH))
    assert stand and stand.fertig and stand.seiten == 2                  # Rotfuchs und Arrhenius
    return o


@pytest.fixture(scope="module")
def leser(ordner) -> Artikelleser:
    ablage = Eigenindizes(lambda: str(ordner / "kategorien"), gueltig=schema.gueltig)
    return Artikelleser(Bibliothek(lambda: str(ordner)), Kategorienindex(ablage))


async def test_kategorien_am_artikel_ohne_versteckte(leser):
    assert [(k.pfad, k.titel) for k in (await leser.lesen(BUCH, "Rotfuchs")).kategorien] == [("Kategorie:Füchse", "Füchse")]
    assert [k.titel for k in (await leser.lesen(BUCH, "Svante_Arrhenius")).kategorien] == ["Schwede"]


async def test_kategorieseite_mit_kreis_und_unterkategorien(leser):
    f = await leser.lesen(BUCH, "Kategorie:Füchse")
    assert f.darstellung == "kategorie" and f.titel == "Füchse"
    assert [s.pfad for s in f.kategorie.seiten] == ["Rotfuchs"] and f.kategorie.seiten_gesamt == 1
    assert [o.titel for o in f.kategorie.ober] == ["Tiere"] and [u.titel for u in f.kategorie.unter] == ["Tiere"]  # Kreis
    alles = await leser.lesen(BUCH, "Kategorie:Alles")
    assert [(u.titel, u.anzahl) for u in alles.kategorie.unter] == [("Schwede", 1), ("Tiere", 0)]
    assert alles.kategorie.seiten == [] and alles.rubrik == "Kategorie · 2 Unterkategorien"


async def test_ohne_seite_im_buch_und_versteckt_keine_kategorie(leser):
    for pfad in ("Kategorie:Leer", "Kategorie:Wartung", "Kategorie:Gibt_es_nicht"):
        with pytest.raises(EintragFehlt):
            await leser.lesen(BUCH, pfad)


async def test_weitere_seiten_ab_der_letzten(ordner):
    k = Kategorienindex(Eigenindizes(lambda: str(ordner / "kategorien"), gueltig=schema.gueltig))
    seite = (await k.kategorie(BUCH, "Kategorie:Füchse"))[1].seiten[0]
    assert await k.weitere(BUCH, "Kategorie:Füchse", seite.nr) == []
    assert [s.pfad for s in await k.weitere(BUCH, "Kategorie:Füchse", 0)] == ["Rotfuchs"]
    assert await k.weitere(BUCH, "Kategorie:Leer", 0) is None


def test_wiki_und_ordnung():
    assert wiki("wikipedia_de_all_maxi_2026-01") == "dewiki" and wiki("wikivoyage_en_all_2026-10") == "enwikivoyage"
    assert wiki("klexikon_de_all_maxi_2026-11") is None and wiki("devdocs_en_astro_2026-10") is None
    assert sorted(["Zebra", "Birne", "Ast", "Äpfel"], key=schema.ordnung) == ["Äpfel", "Ast", "Birne", "Zebra"]
