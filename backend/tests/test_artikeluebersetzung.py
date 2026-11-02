"""Artikel übersetzen (WIKI-8): Zerlegen in Textläufe mit Marken und Platzhaltern, Prüfen (Marken, Schachtelung,
Zahlen), Einsetzen; der Auftrag übersetzt in Teilen, halbiert bei unpassender Antwort, lässt Abgelehntes im Original
(mit Sprache), legt für alle ab und setzt nach einem Fehler beim Übersetzten an."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from lxml import html as lhtml

from appkern.auftraege import Auftraege
from appkern.datenbank import Datenbank
from appkern.leitstelle import NichtErreichbar

from app.modell.artikel import Artikel, Steckbrief
from app.modell.buch import Buch, Faehigkeiten
from app.uebersetzung.artikel import Artikeluebersetzer
from app.uebersetzung.zerlegen import Abgelehnt, einsetzen, laeufe, pruefen

TEXT = """<h2 id="Usage">Usage <code>map</code></h2>
<p>Use <a href="/lesen/b/array_map">array_map</a> to apply a <em>callback</em> to <b>3 <i>arrays</i></b>.<span class="beleg" data-beleg="2">[2]</span></p>
<ul><li>First item<ul><li>nested one</li></ul> after the list</li></ul>
<pre>echo "never translated";</pre>
<div class="beitrag-fuss">asked by Jane Doe on 2020-01-02</div>"""


def wurzel(html: str = TEXT):
    return lhtml.fragment_fromstring(html, create_parent="div")


def test_zerlegen_nur_text_mit_marken_und_platzhaltern():
    vorlagen = [l.vorlage for l in laeufe(wurzel())]
    assert vorlagen == ["Usage <x1/>", "Use <t1>array_map</t1> to apply a <t2>callback</t2> to <t3>3 <t4>arrays</t4></t3>.<x5/>",
                        "First item", "nested one", "after the list"]     # Code, Beitragsfuß und Belegtext gehen nie mit


def test_einsetzen_behaelt_struktur_und_unantastbares():
    w = wurzel()
    deutsch = ["Verwendung <x1/>", "Mit <t1>array_map</t1> wendet man einen <t2>Callback</t2> auf <t3>3 <t4>Arrays</t4></t3> an.<x5/>",
               "Erster Eintrag", "verschachtelt", "nach der Liste"]
    for lauf, text in zip(laeufe(w), deutsch):
        einsetzen(lauf, text)
    html = lhtml.tostring(w, encoding="unicode")
    assert '<h2 id="Usage">Verwendung <code>map</code></h2>' in html
    assert ('<p>Mit <a href="/lesen/b/array_map">array_map</a> wendet man einen <em>Callback</em> auf <b>3 <i>Arrays</i></b> an.'
            '<span class="beleg" data-beleg="2">[2]</span></p>') in html
    assert "<li>Erster Eintrag<ul><li>verschachtelt</li></ul> nach der Liste</li>" in html
    assert 'echo "never translated";' in html and "asked by Jane Doe" in html


@pytest.mark.parametrize("falsch, grund", [
    ("Zahle <t1>6</t1> Dollar <x2/> jetzt", "Zahlen"),
    ("Zahle <t1>5</t1> Dollar jetzt", "fehlen"),
    ("Zahle <t1>5 Dollar <x2/> jetzt", "nicht geschlossen"),
    ("Zahle <x1/> Dollar <t2>x</t2>", "vertauscht"),
    ("Zahle <t1>5</t1> <b>Dollar</b> <x2/>", "fremde"),
    ("Zahle <t1>5</t1> <t1>5</t1> <x2/>", "doppelt"),
])
def test_pruefung_lehnt_ab(falsch, grund):
    lauf = laeufe(wurzel("<p>Pay <b>5</b> dollars <code>x</code> now</p>"))[0]
    with pytest.raises(Abgelehnt, match=grund):
        pruefen(lauf, falsch)
    pruefen(lauf, "Jetzt <x2/> <t1>5</t1> Dollar zahlen")            # Stellung im Satz darf sich ändern
    pruefen(lauf, "Zahle <t1>5</t1> Dollar <x2/> jetzt")


def test_zahlen_in_anderer_schreibweise_bleiben_dieselben():
    lauf = laeufe(wurzel("<p>It costs 1,000.50 dollars since 2020</p>"))[0]
    pruefen(lauf, "Es kostet seit 2020 1.000,50 Dollar")


# ----- Der Auftrag -------------------------------------------------------------------------------------------------------

@dataclass
class Antwort:
    text: str
    modell: str = "qwen/qwen3-next-80b"


class Leitstelle:
    """Nachgestellt: übersetzt jedes Stück nach einer Tabelle; `kaputt` liefert bei mehreren Stücken eins zu wenig."""

    def __init__(self, tabelle: dict[str, str], kaputt: bool = False, fehler: Exception | None = None) -> None:
        self.tabelle, self.kaputt, self.fehler = tabelle, kaputt, fehler
        self.aufrufe: list[list[str]] = []

    async def chat(self, nachrichten, **optionen) -> Antwort:
        stuecke = json.loads(nachrichten[1].inhalt)["stuecke"]
        self.aufrufe.append(stuecke)
        if self.fehler:
            raise self.fehler
        aus = [self.tabelle.get(s, s) for s in stuecke]
        if self.kaputt and len(aus) > 1:
            aus = aus[:-1]
        return Antwort(json.dumps({"stuecke": aus}))


BUCH = Buch(kennung="devdocs_en_php_2026-08", name="devdocs_en_php", titel="PHP", sprache="eng", art="dokumentation",
            eintraege=1, artikel=1, medien=0, groesse=1, faehigkeiten=Faehigkeiten(titelindex=True, volltext=True, bilder=False,
                                                                                    lesedesign=True))
ARTIKEL = Artikel(buch=BUCH.kennung, pfad="function.array-map", angefragt="function.array-map", titel="array_map",
                  titelart="code", darstellung="lesedesign", baustein="dokumentation", original="/o",
                  html="<h2 id='d'>Description</h2><p>Applies the <em>callback</em> to 2 arrays.</p><p>Returns an array.</p>",
                  steckbrief=Steckbrief(titel="array_map", code=True, html="<dl><dt>Since</dt><dd>PHP 4</dd></dl>"))
DEUTSCH = {"Description": "Beschreibung", "Applies the <t1>callback</t1> to 2 arrays.": "Wendet den <t1>Callback</t1> auf 2 Arrays an.",
           "Returns an array.": "Gibt ein Array zurück.", "Since": "Seit", "PHP 4": "PHP 4"}


DEUTSCHES = BUCH.model_copy(update={"kennung": "wikipedia_de_all_2026-10", "sprache": "deu", "art": "enzyklopaedie"})


class Bib:
    async def buch(self, kennung: str) -> Buch:
        return DEUTSCHES if kennung == DEUTSCHES.kennung else BUCH


class Leser:
    async def lesen(self, buch: str, pfad: str) -> Artikel:
        return ARTIKEL


@pytest.fixture
async def db(tmp_path: Path):
    d = await Datenbank(tmp_path / "a.sqlite").oeffnen()
    yield d
    await d.schliessen()


async def dienst(db, leitstelle) -> tuple[Artikeluebersetzer, Auftraege]:
    auftraege = Auftraege(db, [])
    u = Artikeluebersetzer(db, auftraege, Bib(), Leser(), lambda: leitstelle, lambda: "")
    await u.starten()
    await auftraege.starten()
    return u, auftraege


async def bis_fertig(u: Artikeluebersetzer, zustaende=("fertig", "fehler")):
    for _ in range(500):
        stand = await u.stand(BUCH.kennung, ARTIKEL.pfad)
        if stand.zustand in zustaende:
            return stand
        await asyncio.sleep(0.01)
    raise AssertionError(stand)


async def test_auftrag_uebersetzt_legt_ab_und_kennzeichnet(db):
    leitstelle = Leitstelle(DEUTSCH)
    u, auftraege = await dienst(db, leitstelle)
    try:
        assert (await u.stand(BUCH.kennung, ARTIKEL.pfad)).zustand == "fehlt"
        assert (await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")).zustand == "laeuft"
        stand = await bis_fertig(u)
        ue = stand.uebersetzung
        assert ue.titel == "array_map"                                   # Titel aus dem Code bleibt
        assert "Wendet den <em>Callback</em> auf 2 Arrays an." in ue.html and "Gibt ein Array zurück." in ue.html
        assert [a.titel for a in ue.abschnitte] == ["Beschreibung"] and ue.abschnitte[0].anker == "d"
        assert "<dt>Seit</dt>" in ue.steckbrief.html
        assert (ue.aus, ue.modell, ue.im_original) == ("Englischen", "qwen/qwen3-next-80b", 0)
        assert len(leitstelle.aufrufe) == 1                              # ein Teil, ein Aufruf
        await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")           # liegt ab: kein neuer Auftrag
        assert len(leitstelle.aufrufe) == 1
        # woher der erledigte Auftrag kommt (WIKI-50): ein Verweis auf den Artikel
        herkunft = (await auftraege.liste()).eintraege[0].herkunft
        assert (herkunft.titel, herkunft.ziel) == ("Zum Artikel", f"lesen/{BUCH.kennung}/{ARTIKEL.pfad}")
    finally:
        await auftraege.stoppen()


async def test_unpassende_antwort_wird_halbiert_abgelehntes_bleibt_im_original(db):
    tabelle = DEUTSCH | {"Returns an array.": "Gibt 3 Arrays zurück."}  # falsche Zahl: bleibt englisch
    leitstelle = Leitstelle(tabelle, kaputt=True)
    u, auftraege = await dienst(db, leitstelle)
    try:
        await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")
        ue = (await bis_fertig(u)).uebersetzung
        assert "Wendet den <em>Callback</em> auf 2 Arrays an." in ue.html
        assert re.search(r'<p lang="en">Returns an array\.</p>', ue.html)
        assert ue.im_original == 1
        assert max(len(a) for a in leitstelle.aufrufe[1:]) < len(leitstelle.aufrufe[0])   # halbiert
    finally:
        await auftraege.stoppen()


async def test_ohne_leitstelle_nicht_moeglich_deutsch_nicht_noetig(db):
    u, auftraege = await dienst(db, None)
    try:
        stand = await u.stand(BUCH.kennung, ARTIKEL.pfad)
        assert stand.zustand == "nicht_moeglich" and "Leitstelle" in stand.grund
        assert (await u.stand(DEUTSCHES.kennung, "Fuchs")).zustand == "nicht_noetig"
    finally:
        await auftraege.stoppen()


async def test_fehler_der_leitstelle_und_wiederholen(db):
    leitstelle = Leitstelle(DEUTSCH, fehler=NichtErreichbar("Leitstelle antwortet nicht"))
    u, auftraege = await dienst(db, leitstelle)
    try:
        await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")
        stand = await bis_fertig(u)
        assert stand.zustand == "fehler" and "nicht möglich" in stand.grund
        leitstelle.fehler = None
        assert (await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")).zustand == "laeuft"
        assert (await bis_fertig(u)).zustand == "fertig"
    finally:
        await auftraege.stoppen()


async def test_kommentare_im_code_eigens_uebersetzt_code_bleibt(db):
    """WIKI-8: Kommentare im Code als eigene Stücke (ohne Kommentarzeichen); der Code bleibt Zeichen für Zeichen, die
    Paare stehen je Codeabschnitt; was Bezeichner verändert, bleibt im Original."""
    import app.uebersetzung.artikel as modul

    code = '<pre><span class="c-kom">// returns the cube of $n</span>\n$b = cube(3); <span class="c-kom">// calls cube()</span></pre>'
    artikel = ARTIKEL.model_copy(update={"html": ARTIKEL.html + code})
    tabelle = DEUTSCH | {"returns the cube of $n": "gibt die dritte Potenz von $n zurück", "calls cube()": "ruft die Funktion auf"}
    leitstelle = Leitstelle(tabelle)

    class EigenerLeser:
        async def lesen(self, buch, pfad):
            return artikel

    auftraege = Auftraege(db, [])
    u = modul.Artikeluebersetzer(db, auftraege, Bib(), EigenerLeser(), lambda: leitstelle, lambda: "")
    await u.starten()
    await auftraege.starten()
    try:
        await u.anstossen(BUCH.kennung, ARTIKEL.pfad, "Probe")
        ue = (await bis_fertig(u)).uebersetzung
        assert [(k.block, k.original, k.uebersetzt) for k in ue.kommentare] == [
            (0, "// returns the cube of $n", "// gibt die dritte Potenz von $n zurück")]   # cube() fehlte: bleibt Original
        assert '<span class="c-kom">// returns the cube of $n</span>' in ue.html                # der Code selbst bleibt
        assert ["returns the cube of $n", "calls cube()"] in leitstelle.aufrufe
    finally:
        await auftraege.stoppen()
