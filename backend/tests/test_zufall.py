"""Zufallsartikel (Startseite, Knopf Zufall): eine Sprungseite, deren Ziel in der Quelle fehlt (Auszüge wie
climate-change), wird übergangen; der Zufall liefert den Pfad nach dem Auflösen der Weiterleitung."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.artikel import ZUFALL_ZUEGE, Artikelleser
from app.bibliothek import EintragFehlt


@dataclass
class _Eintrag:
    path: str


@dataclass
class _Aufgeloest:
    pfad: str


class _Archiv:
    def __init__(self, pfade: list[str]) -> None:
        self._pfade = pfade

    def get_random_entry(self) -> _Eintrag:
        return _Eintrag(self._pfade.pop(0) if len(self._pfade) > 1 else self._pfade[0])


class _Bib:
    """Dämmschaum springt auf Dämmstoff, das im Auszug fehlt; Rotfuchs leitet auf Fuchs weiter."""

    gibt_es = datei = None                    # für die Wege des Lesers, hier nicht gebraucht

    def __init__(self, pfade: list[str]) -> None:
        self._archiv = _Archiv(pfade)

    def archiv(self, kennung: str) -> _Archiv:
        return self._archiv

    async def eintrag(self, kennung: str, pfad: str) -> _Aufgeloest:
        if pfad == "Dämmschaum":
            raise EintragFehlt("Dämmstoff steht nicht in der Quelle")
        return _Aufgeloest("Fuchs" if pfad == "Rotfuchs" else pfad)


async def test_sprungseite_ohne_ziel_wird_uebergangen():
    assert await Artikelleser(_Bib(["Dämmschaum", "Dämmschaum", "Rotfuchs"])).zufall("auszug") == "Fuchs"


async def test_nur_sprungseiten_ist_ein_fehlender_eintrag():
    with pytest.raises(EintragFehlt, match=f"{ZUFALL_ZUEGE} Zügen"):
        await Artikelleser(_Bib(["Dämmschaum"])).zufall("auszug")
