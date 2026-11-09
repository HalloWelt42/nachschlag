"""WIKI-56: die Bedeutungssuche bindet sich selbst an, solange in den Einstellungen nichts gewählt ist (Sammlung mit der
Lexikon-Quelle des Fundus, Buch, dessen Datei der Fundus einliest); Gewähltes geht immer vor."""

import asyncio

import httpx

from appkern.verbund import VerbundFehler

from app.suche.anbindung import Bedeutungsanbindung

SAMMLUNGEN = {"eintraege": [
    {"sammlung": {"kennung": "s-wiki", "name": "Wikipedia (Deutsch)", "dokumente": 5}, "quellen": [{"art": "lexikon"}]},
    {"sammlung": {"kennung": "s-notizen", "name": "Notizen", "dokumente": 3}, "quellen": [{"art": "ordner"}]}]}


class Fundus:
    """Nachgestellter Verbund zum Fundus: antwortet wie dessen Wege, oder ist weg; `zoegern` hält die Liste der
    Sammlungen auf (der echte Fundus braucht dafür bisweilen eine halbe Minute)."""

    def __init__(self) -> None:
        self.da = True
        self.zoegern = asyncio.Event()
        self.zoegern.set()
        self.listen = 0

    async def anfrage(self, methode: str, adresse: str, pfad: str, **art) -> httpx.Response:
        if not self.da:
            raise VerbundFehler("Fundus nicht erreichbar")
        if pfad == "/api/v1/sammlungen":
            self.listen += 1
            await self.zoegern.wait()
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


async def test_start_wartet_nicht_auf_den_fundus():
    """WIKI-86: der Start ist sofort fertig, auch wenn der Fundus lange braucht; der Abgleich kommt im Hintergrund nach.
    Neue Zugänge beim Start stoßen keinen zweiten Abgleich an, einer danach schon."""
    f = Fundus()
    f.zoegern.clear()
    a = anbindung(f, {})
    await asyncio.wait_for(a.starten(), 0.1)
    await asyncio.sleep(0.01)                           # wie beim Start: andere Dienste warten, der Abgleich beginnt
    await asyncio.wait_for(a.verbunden(), 0.1)
    await asyncio.sleep(0.01)
    assert a.sammlung() == "" and f.listen == 1         # bis zum ersten Abgleich: nur der Index
    f.zoegern.set()
    await asyncio.sleep(0.01)
    assert a.sammlung() == "s-wiki" and f.listen == 1
    await a.verbunden()
    await asyncio.sleep(0.01)
    assert f.listen == 2
    await a.stoppen()
