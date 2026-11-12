"""Eine markierte Stelle übersetzen (WIKI-47): aus der Leiste über einer Markierung, ins Deutsche (in deutschem Text ins
Englische). Code bleibt Code: übersetzt werden nur Kommentare und Text in natürlicher Sprache, Zeilen und Einrückung
bleiben. Über die Leitstelle, ohne Ablage (Stellen sind kurz und selten gleich). Ohne Leitstelle ist das ein Zustand mit
Grund, kein Fehler."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, antwortform, gerade, json_lesen

#: so lang darf eine markierte Stelle sein (ein paar Absätze)
HOECHSTENS = 4000
Ziel = Literal["de", "en"]
ZIELE: dict[str, str] = {"de": "Deutsche", "en": "Englische"}

ANWEISUNG = """Übersetze den Text ins {ziel}. Ist er Code, übersetze nur Kommentare und Text in natürlicher Sprache
(Zeichenketten mit Sätzen); Schlüsselwörter, Namen, Bezeichner, Zahlen und Zeichen des Codes bleiben unverändert, ebenso
Zeilenumbrüche und Einrückung. Namen von Personen, Produkten, Befehlen und Funktionen bleiben. Nichts weglassen, nichts
erklären. Nur gerade Anführungszeichen (") und einfache Bindestriche (-).
Antworte nur mit dem JSON-Objekt {{"text": "..."}}."""

FORM = antwortform("stelle", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
                              "additionalProperties": False})


class Stellenstand(BaseModel):
    bereit: bool
    grund: str = ""


class Stellenuebersetzung(BaseModel):
    ziel: Ziel
    text: str = ""
    modell: str = ""
    grund: str = ""                      # warum es gerade nicht geht (dann ist text leer)


class Stellenuebersetzer:
    def __init__(self, leitstelle: Callable[[], Leitstelle | None], modell: Callable[[], str]) -> None:
        self._leitstelle, self._modell = leitstelle, modell

    def stand(self) -> Stellenstand:
        if self._leitstelle() is None:
            return Stellenstand(bereit=False, grund="Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        return Stellenstand(bereit=True)

    async def uebersetzen(self, text: str, ziel: Ziel) -> Stellenuebersetzung:
        leitstelle = self._leitstelle()
        if leitstelle is None:
            return Stellenuebersetzung(ziel=ziel, grund="Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        try:
            antwort = await leitstelle.chat([Nachricht.system(ANWEISUNG.format(ziel=ZIELE[ziel])), Nachricht.nutzer(text)],
                                            modell=self._modell(), titel="Stelle übersetzen",
                                            response_format=FORM, temperature=0)
            uebersetzt = gerade(str(json_lesen(antwort.text).get("text", ""))).strip("\n")
        except LeitstellenFehler as f:
            return Stellenuebersetzung(ziel=ziel, grund=f"Übersetzung gerade nicht möglich: {f}")
        except (ValueError, AttributeError):
            return Stellenuebersetzung(ziel=ziel, grund="Die Übersetzung kam unlesbar zurück")
        return Stellenuebersetzung(ziel=ziel, text=uebersetzt, modell=antwort.modell or "")
