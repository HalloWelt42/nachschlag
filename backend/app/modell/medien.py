"""Medien: die Bilder der Artikel mit Unterschrift, für die Mediensuche und die große Bildansicht."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Medienart = Literal["bild", "karte", "ton"]


class Medium(BaseModel):
    buch: str
    pfad: str = Field(description="Artikel, in dem das Bild steht")
    artikel: str = Field(description="Titel des Artikels")
    abschnitt: str = Field("", description="Überschrift des Abschnitts, in dem das Bild steht; leer: Einleitung oder Steckbrief")
    bild: str = Field(description="Adresse des Bilds in der App")
    breite: int = Field(0, description="Breite im Buch in Pixeln (meist ein Vorschaubild); 0: unbekannt")
    hoehe: int = 0
    unterschrift: str = Field("", description="Bildunterschrift oder Alternativtext als reiner Text")
    datei: str = Field("", description="Dateiname des Bilds")
    art: Medienart = Field("bild", description="bild, karte (Landkarte, Lageplan) oder ton (Hörbeispiel; `bild` ist dann die Adresse des Tons)")
    gross: bool = Field(False, description="der Bildholer hat das große Bild schon geholt (WIKI-80)")


class Medienergebnis(BaseModel):
    frage: str
    medien: list[Medium]
    artikel: int = Field(description="aus wie vielen Artikeln")
    passend: int = Field(description="wie viele davon die Frage in der Unterschrift tragen")
