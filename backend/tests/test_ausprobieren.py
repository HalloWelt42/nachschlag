"""Ausprobieren (WIKI-48, WIKI-52): Angebot, Probelauf und Funktionen je PHP-Fassung über den Verbund bei der
Codeschmiede; ohne Adresse oder bei Ablehnung ein Grund."""

from __future__ import annotations

from dataclasses import dataclass

from appkern.verbund import VerbundFehler

from app.ausprobieren import Ausprobieren

ANGEBOT = [{"sprache": "python", "fassungen": [], "aufzeichnen": True},
           {"sprache": "javascript", "fassungen": [], "aufzeichnen": True},
           {"sprache": "php", "fassungen": ["8.5", "7.4"], "aufzeichnen": False}]


@dataclass
class Antwort:
    daten: object

    def json(self):
        return self.daten


class Verbund:
    """Antwortet wie die Codeschmiede; `fehler` lehnt jede Anfrage ab, `funktionen` sind die Fassungen, die antworten."""

    def __init__(self, fehler: VerbundFehler | None = None, funktionen: tuple[str, ...] = ("8.5", "7.4")) -> None:
        self.fehler, self.funktionen, self.aufrufe = fehler, funktionen, []

    async def anfrage(self, methode, adresse, pfad, **art):
        self.aufrufe.append((methode, adresse, pfad, art))
        if self.fehler:
            raise self.fehler
        if pfad.endswith("/sprachen"):
            return Antwort(ANGEBOT)
        if pfad.endswith("/funktionen/php"):
            return Antwort({f: ["strlen"] + (["str_contains"] if f == "8.5" else ["each"]) for f in self.funktionen})
        if pfad.endswith("/ausfuehren"):
            return Antwort({"art": "php", "ausgabe": "8\n", "hinweise": "", "fehler": None, "laufzeit_ms": 9})
        return Antwort({"ausgabe": "6\n", "fehler": None, "schritte": [{"zeile": 1}]})


async def test_angebot_und_probelauf_mit_aufzeichnung():
    v = Verbund()
    a = Ausprobieren(lambda: v, lambda: "https://codeschmiede.local/")
    stand = await a.stand()
    assert stand.bereit and [s.sprache for s in stand.sprachen] == ["python", "javascript", "php"]
    assert stand.sprachen[2].fassungen == ["8.5", "7.4"] and not stand.sprachen[2].aufzeichnen
    lauf = await a.laufen("print(6)", "python", "", [])
    assert lauf.aufzeichnung["ausgabe"] == "6\n" and not lauf.grund
    aufruf = v.aufrufe[-1]
    assert aufruf[:3] == ("POST", "https://codeschmiede.local", "/api/v1/sandbox/aufzeichnen")
    assert aufruf[3]["json"] == {"code": "print(6)", "sprache": "python", "eingabe": []}
    await a.stand()
    assert sum(p.endswith("/sprachen") for _, _, p, _ in v.aufrufe) == 1          # das Angebot gilt eine Weile


async def test_php_laeuft_ohne_aufzeichnung_in_der_fassung():
    v = Verbund()
    a = Ausprobieren(lambda: v, lambda: "https://c")
    lauf = await a.laufen("<?php echo 8;", "php", "7.4", [])
    assert lauf.aufzeichnung["ausgabe"] == "8\n" and lauf.aufzeichnung["schritte"] == []
    assert v.aufrufe[-1][2] == "/api/v1/sandbox/ausfuehren"
    assert v.aufrufe[-1][3]["json"] == {"code": "<?php echo 8;", "sprache": "php", "fassung": "7.4"}


async def test_funktionen_je_fassung_gemerkt_wenn_alle_antworten():
    v = Verbund(funktionen=("8.5",))
    a = Ausprobieren(lambda: v, lambda: "https://c")
    assert list(await a.funktionen()) == ["8.5"]
    v.funktionen = ("8.5", "7.4")
    bestand = await a.funktionen()
    assert "each" in bestand["7.4"] and "str_contains" in bestand["8.5"]
    gefragt = len(v.aufrufe)
    await a.funktionen()
    assert len(v.aufrufe) == gefragt                    # alle Fassungen da: nicht noch einmal gefragt


async def test_ohne_adresse_oder_abgelehnt_ein_grund():
    ohne = Ausprobieren(lambda: Verbund(), lambda: "")
    assert not (await ohne.stand()).bereit and "Codeschmiede" in (await ohne.laufen("x", "python", "", [])).grund
    abgelehnt = Ausprobieren(lambda: Verbund(VerbundFehler("Diese App darf die Sandbox nicht nutzen", 403)), lambda: "https://c")
    assert "lässt Nachschlag nicht zu" in (await abgelehnt.laufen("x", "python", "", [])).grund
    assert not (await abgelehnt.stand()).bereit and await abgelehnt.funktionen() == {}
    weg = Ausprobieren(lambda: Verbund(VerbundFehler("nicht erreichbar (ConnectError)")), lambda: "https://c")
    assert "nicht erreichbar" in (await weg.laufen("x", "python", "", [])).grund
