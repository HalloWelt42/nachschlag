"""Vorgaben je Dienst für die Leitstelle (WIKI-100, Leitstelle LS-28): auf welchem Rechner ein Dienst von Nachschlag
bevorzugt rechnet und mit welchem Vorrang. Beides stellt der Nutzer beim Dienst in den Einstellungen ein. Jeder Dienst
bekommt hier seine Leitstelle mit dieser Vorgabe (`leitstelle(dienst)`); die Dienste selbst kennen sie nicht.

Der Rechner ist ein Wunsch, die Leitstelle weicht aus. Der Vorrang gilt für Arbeit, auf die jemand wartet; wo ein Aufruf
selbst Hintergrund sagt (ein Buch bauen, über Nacht), bleibt es Hintergrund."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from appkern.leitstelle import Leitstelle

from .einstellungen import AppEinstellungen

Dienst = Literal["vorlesen", "spracheingabe", "uebersetzung", "buch"]


def vorgabe(e: AppEinstellungen, dienst: Dienst) -> tuple[list[str], str]:
    """Rechnerwunsch (leer: die Leitstelle entscheidet) und Vorrang eines Dienstes aus den Einstellungen."""
    rechner, vorrang = {"vorlesen": (e.vorlesen_rechner, e.vorlesen_vorrang),
                        "spracheingabe": (e.spracheingabe_rechner, e.spracheingabe_vorrang),
                        "uebersetzung": (e.uebersetzung_rechner, e.uebersetzung_vorrang),
                        "buch": (e.buch_rechner, e.buch_vorrang)}[dienst]
    return ([rechner] if rechner.strip() else []), vorrang


class Vorgaben:
    def __init__(self, leitstelle: Callable[[], Leitstelle | None], einstellungen: Callable[[], AppEinstellungen]) -> None:
        self._ls, self._e = leitstelle, einstellungen

    def leitstelle(self, dienst: Dienst) -> Callable[[], Leitstelle | None]:
        """Die Leitstelle für diesen Dienst: jede Anfrage trägt seine Vorgabe, gelesen beim Senden (eine geänderte
        Einstellung gilt sofort). Ohne Leitstelle None."""
        def holen() -> Leitstelle | None:
            ls = self._ls()
            return ls.mit_vorgabe(lambda: vorgabe(self._e(), dienst)) if ls is not None else None
        return holen
