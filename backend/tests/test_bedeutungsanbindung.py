"""WIKI-56: die Bedeutungssuche bindet sich selbst an, solange in den Einstellungen nichts gewählt ist (Sammlung mit der
Lexikon-Quelle des Fundus, Buch, dessen Datei der Fundus einliest); Gewähltes geht immer vor."""

import httpx

from appkern.verbund import VerbundFehler

from app.suche.anbindung import Bedeutungsanbindung

SAMMLUNGEN = {"eintraege": [
    {"sammlung": {"kennung": "s-wiki", "name": "Wikipedia (Deutsch)", "dokumente": 5}, "quellen": [{"art": "lexikon"}]},
    {"sammlung": {"kennung": "s-notizen", "name": "Notizen", "dokumente": 3}, "quellen": [{"art": "ordner"}]}]}


class Fundus:
    """Nachgestellter Verbund zum Fundus: antwortet wie dessen Wege, oder ist weg."""

    def __init__(self) -> None:
        self.da = True

    async def anfrage(self, methode: str, adresse: str, pfad: str, **art) -> httpx.Response:
        if not self.da:
            raise VerbundFehler("Fundus nicht erreichbar")
        if pfad == "/api/v1/sammlungen":
            return httpx.Response(200, json=SAMMLUNGEN)
        if pfad == "/api/v1/quellenstand/dateien":
            return httpx.Response(200, json={"dateien": ["wikipedia_de_all_maxi_2026-01.zim", "fremd_2025-01.zim"]})
        raise VerbundFehler("nicht da", 404)


def anbindung(fundus: Fundus, gewaehlt: dict) -> Bedeutungsanbindung:
    async def buecher() -> list[str]:
        return ["wikipedia_de_all_maxi_2026-01", "wikipedia_de_all_maxi_2026-10", "devdocs_en_php_2026-02"]

    async def juengste(k: str) -> str:
        return "wikipedia_de_all_maxi_2026-10" if k.startswith("wikipedia_de_all_maxi") else k

    return Bedeutungsanbindung(lambda: fundus, lambda: "http://fundus.test", lambda: gewaehlt.get("sammlung", ""),
                               lambda: gewaehlt.get("buch", ""), buecher, juengste)


async def test_von_selbst_und_gewaehltes_geht_vor():
    f, gewaehlt = Fundus(), {}
    a = anbindung(f, gewaehlt)
    await a.abgleichen()
    assert a.sammlung() == "s-wiki" and await a.buch() == "wikipedia_de_all_maxi_2026-10"
    angebot = await a.angebot()
    assert [o.wert for o in angebot.optionen] == ["s-wiki", "s-notizen"] and "von selbst: Wikipedia (Deutsch)" in angebot.stand
    gewaehlt.update(sammlung="s-notizen", buch="devdocs_en_php_2026-02")
    assert a.sammlung() == "s-notizen" and await a.buch() == "devdocs_en_php_2026-02"


async def test_ohne_fundus_bleibt_es_beim_letzten_stand():
    f = Fundus()
    a = anbindung(f, {})
    await a.abgleichen()
    f.da = False
    await a.abgleichen()
    assert a.sammlung() == "s-wiki"                 # ein kurzer Ausfall nimmt die Anbindung nicht weg
