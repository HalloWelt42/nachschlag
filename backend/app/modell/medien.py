"""Medien: die Bilder der Artikel mit Unterschrift, für die Mediensuche und die große Bildansicht."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class Medienergebnis(BaseModel):
    frage: str
    medien: list[Medium]
    artikel: int = Field(description="aus wie vielen Artikeln")
    passend: int = Field(description="wie viele davon die Frage in der Unterschrift tragen")
