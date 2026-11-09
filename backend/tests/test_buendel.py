"""Bündel (WIKI-83): Übungsbücher derselben Herkunft bilden eine Ebene, das Gesamtbuch öffnet sie; Bücher anderer Art,
einzelne und archivierte bleiben für sich."""

from __future__ import annotations

from app.bibliothek.buendel import buendeln
from app.modell.buch import Archivstand, Buch, Faehigkeiten


def _buch(name: str, titel: str, art: str = "uebung", archiv: bool = False, stand: str = "2026-10") -> Buch:
    f = Faehigkeiten(titelindex=True, volltext=True, bilder=False, lesedesign=True)
    return Buch(kennung=f"{name}_{stand}", name=name, titel=titel, art=art, eintraege=1, artikel=1, medien=0, groesse=1,
                faehigkeiten=f, ordner="/b", archiv=Archivstand(grund="ersetzt") if archiv else None)


def test_uebungen_derselben_herkunft_bilden_ein_buendel():
    buecher = [_buch("freecodecamp_de_all", "FreeCodeCamp"), _buch("wikipedia_de_all_maxi", "Wikipedia", art="enzyklopaedie"),
               _buch("freecodecamp_de_rosetta-code", "Rosetta-Code"), _buch("freecodecamp_de_project-euler", "Project Euler"),
               _buch("freecodecamp_en_rosetta-code", "Rosetta Code"), _buch("freecodecamp_de_all", "FreeCodeCamp alt", archiv=True, stand="2026-09")]
    aus = buendeln(buecher)
    assert [b.kennung for b in aus] == [b.kennung for b in buecher], "Reihenfolge und Bücher bleiben"
    angaben = [(b.titel, b.buendel, b.buendel_titel, b.buendel_gesamt) for b in aus]
    assert [b.buendel_im_gesamt for b in aus] == [False, False, True, True, False, False], "Themen stecken im Gesamtbuch"
    assert angaben == [("FreeCodeCamp", "freecodecamp_de", "FreeCodeCamp", True), ("Wikipedia", "", "", False),
                       ("Rosetta-Code", "freecodecamp_de", "FreeCodeCamp", False), ("Project Euler", "freecodecamp_de", "FreeCodeCamp", False),
                       ("Rosetta Code", "", "", False), ("FreeCodeCamp alt", "", "", False)]


def test_ohne_gesamtbuch_heisst_die_ebene_nach_der_herkunft():
    aus = buendeln([_buch("freecodecamp_de_rosetta-code", "Rosetta-Code"), _buch("freecodecamp_de_project-euler", "Project Euler")])
    assert {(b.buendel_titel, b.buendel_gesamt) for b in aus} == {("Freecodecamp", False)}
