"""WIKI-93: Vorschläge beim Tippen über alle Bücher geordnet: genauer Titel zuerst, Artikel vor Weiterleitungen,
jede Seite einmal."""

from app.modell.suche import Vorschlag
from app.suche.vorschlaege import genaue_wege, ordnen, stufe


def v(titel: str, buch: str = "wp", pfad: str = "", weiter: str = "") -> Vorschlag:
    return Vorschlag(buch=buch, pfad=pfad or titel.replace(" ", "_"), titel=titel, weiterleitung=weiter)


def test_genauer_titel_vor_weiterleitungen_und_einmal_je_seite():
    kandidaten = [v("Leipziger Bucht", weiter="Leipziger_Tieflandsbucht"), v("Leipzig-Schönefeld", weiter="Schönefeld"),
                  v("Messe Leipzig", weiter="Leipziger_Messe"), v("Leipziger Messe"), v("Leipzig (Stadt)", weiter="Leipzig"),
                  v("Leipzig"), v("Leipzig", buch="klexikon")]
    titel = [(x.buch, x.titel) for x in ordnen(kandidaten, "leipzig", {"wp": 0, "klexikon": 1}, 6)]
    assert titel[:2] == [("wp", "Leipzig"), ("klexikon", "Leipzig")]
    assert ("wp", "Leipzig (Stadt)") not in titel                      # führt auf dieselbe Seite wie Leipzig
    assert titel.index(("wp", "Leipziger Messe")) < titel.index(("wp", "Leipziger Bucht"))   # Artikel vor Weiterleitung
    assert stufe("Messe Leipzig", "leip") == 2 and stufe("Leipzig", "Leipzig") == 0


def test_genaue_wege():
    assert genaue_wege("rotfuchs") == ["rotfuchs", "Rotfuchs"]
    assert genaue_wege("neue welt") == ["neue welt", "Neue welt", "neue_welt", "Neue_welt"]
