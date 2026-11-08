"""WIKI-25: die Antwort des Modells wird nachsichtig gelesen; nur Kennungen des Themas, jeder Artikel einmal, beim
Einsortieren nur vorhandene Bereiche."""

from app.modell.themen import Bereich, Thema, Themeneintrag
from app.themen.ordnen import lesen


def thema() -> Thema:
    eintrag = lambda i, b="": Themeneintrag(id=i, bereich=b, buch_name="wp", buch="wp_1", pfad=i, titel=i, platz=0)  # noqa: E731
    return Thema(id="t", titel="Planeten", angelegt="2026-11-08", bereiche=[Bereich(id="b1", titel="Gasriesen", platz=0)],
                 eintraege=[eintrag("saturn"), eintrag("mars"), eintrag("jupiter", "b1")])


def test_bereiche_vorschlagen():
    roh = {"begruendung": "nach Art", "bereiche": [{"titel": "Gesteinsplaneten", "artikel": ["mars", "erfunden"]},
                                                   {"titel": "Gasriesen", "artikel": ["saturn", "mars"]}, {"titel": "", "artikel": ["x"]},
                                                   "kaputt"]}
    v = lesen(roh, "bereiche", thema(), {"saturn", "mars", "jupiter"})
    assert [(b.titel, b.bereich, b.eintraege) for b in v.bereiche] == [("Gesteinsplaneten", "", ["mars"]), ("Gasriesen", "b1", ["saturn"])]


def test_einsortieren_nur_vorhandene_bereiche():
    roh = {"begruendung": "", "bereiche": [{"titel": "gasriesen", "artikel": ["saturn"]}, {"titel": "Neu", "artikel": ["mars"]}]}
    v = lesen(roh, "einsortieren", thema(), {"saturn", "mars"})
    assert [(b.bereich, b.eintraege) for b in v.bereiche] == [("b1", ["saturn"])]
