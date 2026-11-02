"""Ausprobieren (WIKI-48): Probelauf über den Verbund bei der Codeschmiede; ohne Adresse oder bei Ablehnung ein Grund."""

from __future__ import annotations

from dataclasses import dataclass

from appkern.verbund import VerbundFehler

from app.ausprobieren import Ausprobieren


@dataclass
class Antwort:
    daten: dict

    def json(self):
        return self.daten


class Verbund:
    def __init__(self, fehler: VerbundFehler | None = None) -> None:
        self.fehler, self.aufrufe = fehler, []

    async def anfrage(self, methode, adresse, pfad, **art):
        self.aufrufe.append((methode, adresse, pfad, art))
        if self.fehler:
            raise self.fehler
        return Antwort({"ausgabe": "6\n", "fehler": None, "schritte": [{"zeile": 1}]})


async def test_probelauf_ueber_die_codeschmiede():
    v = Verbund()
    a = Ausprobieren(lambda: v, lambda: "https://codeschmiede.local/")
    assert a.stand().bereit and a.stand().sprachen == ["python", "javascript"]
    lauf = await a.laufen("print(6)", "python", [])
    assert lauf.aufzeichnung["ausgabe"] == "6\n" and not lauf.grund
    assert v.aufrufe[0][:3] == ("POST", "https://codeschmiede.local", "/api/v1/sandbox/aufzeichnen")
    assert v.aufrufe[0][3]["json"] == {"code": "print(6)", "sprache": "python", "eingabe": []}


async def test_ohne_adresse_oder_abgelehnt_ein_grund():
    ohne = Ausprobieren(lambda: Verbund(), lambda: "")
    assert not ohne.stand().bereit and "Codeschmiede" in (await ohne.laufen("x", "python", [])).grund
    abgelehnt = Ausprobieren(lambda: Verbund(VerbundFehler("Diese App darf die Sandbox nicht nutzen", 403)), lambda: "https://c")
    assert "lässt Nachschlag nicht zu" in (await abgelehnt.laufen("x", "python", [])).grund
    weg = Ausprobieren(lambda: Verbund(VerbundFehler("nicht erreichbar (ConnectError)")), lambda: "https://c")
    assert "nicht erreichbar" in (await weg.laufen("x", "python", [])).grund
