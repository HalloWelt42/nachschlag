"""WIKI-23: Notizen je Artikel und Themen als Markdown in der Ablage (Kellerwolke oder Datenordner, WIKI-11); ohne
Notizen geht die Datei weg, abgeschaltet schreibt nichts, Verweise führen zurück in Nachschlag."""

from ablage_probe import Speicher

from app.markdownablage import Markdownablage, notizen_md, thema_md
from app.modell.artikel import Beleg
from app.modell.meins import Notiz
from app.modell.themen import Bereich, Thema, Themeneintrag


def notiz(text: str, zitat: str = "", **weiter) -> Notiz:
    return Notiz(id=text or zitat, buch_name="wikipedia_de_all", buch="wikipedia_de_all_2026-10", pfad="Saturn_(Planet)",
                 titel="Saturn (Planet)", zitat=zitat, text=text, angelegt="2026-11-08T10:00", geaendert="2026-11-08T10:00",
                 **weiter)


def test_darstellung():
    md = notizen_md("Saturn (Planet)", "wikipedia_de_all", "https://n.test/lesen/x/Saturn",
                    [notiz("Ringe aus Eis", "Die Ringe bestehen\nvor allem aus Eis", abschnitt="Ringe",
                           belege=[Beleg(nummer=3, text="NASA", url="https://nasa.gov")])])
    assert md.startswith("# Saturn (Planet)") and "([Artikel öffnen](https://n.test/lesen/x/Saturn))" in md
    assert "### Ringe" in md and "> Die Ringe bestehen\n> vor allem aus Eis" in md and "- Beleg [3]: NASA https://nasa.gov" in md
    t = Thema(id="t", titel="Planeten", beschreibung="Unser Sonnensystem", angelegt="2026-11-08",
              bereiche=[Bereich(id="b", titel="Gasriesen", platz=0)],
              eintraege=[Themeneintrag(id="e", bereich="b", buch_name="wikipedia_de_all", buch="wikipedia_de_all_2026-10",
                                       pfad="Saturn_(Planet)", titel="Saturn (Planet)", platz=0)])
    md = thema_md(t, [notiz("Ringe aus Eis")], "- Saturn. In: Wikipedia.", "https://n.test")
    assert "## Gasriesen" in md and "- [Saturn (Planet)](https://n.test/lesen/wikipedia_de_all_2026-10/Saturn_%28Planet%29)" in md
    assert "  - Ringe aus Eis" in md and "## Literatur" in md and "Ohne Bereich" not in md


async def test_ablage_nach_aenderung_und_alle():
    kw, bestand, an = Speicher(), [notiz("eins"), notiz("zwei", "Stelle")], {"wert": True}

    async def notizen(konto, buch, pfad):
        return list(bestand)

    a = Markdownablage(lambda: kw, notizen, lambda: "https://n.test", lambda: an["wert"])
    datei = "Notizen/wikipedia_de_all/Saturn (Planet).md"
    await a.nach_aenderung("k", bestand[0])
    assert b"eins" in kw.dateien[datei] and b"zwei" in kw.dateien[datei]
    bestand.clear()
    await a.nach_aenderung("k", notiz("eins"))                 # letzte Notiz gelöscht: Datei in den Papierkorb
    assert datei not in kw.dateien and kw.geloescht == [datei]
    an["wert"] = False
    bestand.append(notiz("drei"))
    await a.nach_aenderung("k", bestand[0])                    # abgeschaltet: nichts
    assert kw.dateien == {}
    assert await a.alle_ablegen("k") == (1, "Apps/Nachschlag/Notizen") and datei in kw.dateien
