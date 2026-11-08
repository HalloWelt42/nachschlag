"""Stöbern: Zufallsfund, Entdeckungspfad (von einem Artikel weiter) und Blättern in der Reihenfolge des Buchs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Fund(BaseModel):
    """Ein Artikel zum Zeigen beim Stöbern: Titel, Bild und der erste Absatz."""
    buch: str
    pfad: str
    titel: str
    bild: str = ""
    auszug: str = Field("", description="erster Absatz als reiner Text, gekürzt")


class Nachbar(BaseModel):
    """Ein Schritt, der vom Artikel aus möglich ist."""
    pfad: str
    titel: str
    hinweis: str = Field("", description="wo oder warum, als reiner Text (etwa: im Abschnitt Lebensraum)")


class Pfadschritt(BaseModel):
    """Ein Artikel im Entdeckungspfad und wohin es von ihm aus weitergeht."""
    fund: Fund
    von_hier: list[Nachbar] = Field(description="Verweise im Text, in ihrer Reihenfolge")
    erwaehnt_in: list[Nachbar] = Field(description="Artikel, die auf ihn verweisen (eigener Index) oder ihn im Text nennen (Volltext)")
    verweist_hierher: bool = Field(False, description="erwaehnt_in sind echte Rückverweise aus dem eigenen Index (WIKI-20)")
    aehnlich: list[Nachbar] = Field(description="ähnlich nach Bedeutung (Fundus); leer, wenn nicht angebunden")


class Blatteintrag(BaseModel):
    pfad: str
    titel: str


class Buchseite(BaseModel):
    """Eine Seite Titel in der Reihenfolge des Buchs (ohne Weiterleitungen, Bilder und Beiwerk)."""
    eintraege: list[Blatteintrag]
    erste: int = Field(description="Stelle des ersten Eintrags in der Datei (für die Seite davor)")
    naechste: int = Field(description="Stelle nach dem letzten Eintrag (für die Seite danach); -1: Ende des Buchs")
    hier: str = Field("", description="Pfad, um den die Seite steht")


Richtung = Literal["vor", "zurueck"]
