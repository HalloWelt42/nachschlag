"""Anleitungen und Geräte (Inhaltsart Anleitung, iFixit, WIKI-64): was der Baustein aus einer Seite liest und was Lesen,
Werkstatt, Geräteseite und Index gemeinsam nutzen (eine Wahrheit je Seite)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Marke = Literal["", "hinweis", "vorsicht", "erinnerung"]


class Zeile(BaseModel):
    """Eine Zeile eines Schritts. `farbe`: Farbpunkt, der zu einer Markierung im Bild gehört (rot, orange, ...)."""
    stufe: int = Field(0, ge=0, le=3, description="Einrückung 0 bis 2")
    marke: Marke = Field("", description="Hinweis, Vorsicht oder Erinnerung; leer: gewöhnliche Zeile")
    farbe: str = Field("", description="Farbe des Punkts (red, orange, yellow, green, blue, light_blue, violet, pink); leer: schwarz")
    text: str


class Schritt(BaseModel):
    nr: int
    titel: str = Field("", description="Titel des Schritts, soweit die Quelle einen nennt (selten)")
    bilder: list[str] = Field(default_factory=list, description="Adressen der Bilder, das erste ist das Hauptbild")
    zeilen: list[Zeile] = Field(default_factory=list)


class Werkzeug(BaseModel):
    """Ein Werkzeug oder Ersatzteil einer Anleitung."""
    name: str
    bild: str = ""


class Anleitungsangaben(BaseModel):
    """Eine Anleitung (oder Zerlegung) mit allem, was Lesen, Werkstatt und Index brauchen."""
    art: Literal["anleitung", "zerlegung"] = "anleitung"
    sprache: str = Field("", description="de oder en, aus dem Text bestimmt (die Seiten tragen keine verlässliche Angabe)")
    autor: str = ""
    schwierigkeit: int = Field(0, ge=0, le=5, description="1 sehr einfach bis 5 sehr schwierig; 0 unbekannt")
    schwierigkeit_text: str = ""
    zeit: str = Field("", description="Zeitaufwand, wie die Quelle ihn nennt (1 - 2 Stunden)")
    zeit_von: int | None = Field(None, description="Zeitaufwand von, in Minuten; leer: keine Schätzung")
    zeit_bis: int | None = Field(None, description="Zeitaufwand bis, in Minuten")
    einleitung: str = ""
    hauptbild: str = ""
    werkzeuge: list[Werkzeug] = Field(default_factory=list)
    teile: list[Werkzeug] = Field(default_factory=list)
    schritte: list[Schritt] = Field(default_factory=list)
    abschluss: str = ""


class Geraeteeintrag(BaseModel):
    """Eine Unterkategorie oder Anleitung auf einer Geräteseite."""
    pfad: str
    titel: str
    kurz: str = ""
    bild: str = ""
    empfohlen: bool = False
    bauteil: str = Field("", description="Anleitung: das Bauteil, wie die Geräteseite sie einordnet (Akku, Rückkamera); "
                                         "der Titel in ihrer Liste, sonst der hervorgehobene Titel")


class Geraeteangaben(BaseModel):
    """Eine Geräteseite. Mit Unterkategorien ist sie eine Kategorie (Smartphones, iPad), sonst ein Gerät mit Anleitungen."""
    kurz: str = ""
    bild: str = ""
    unterkategorien: list[Geraeteeintrag] = Field(default_factory=list)
    anleitungen: list[Geraeteeintrag] = Field(default_factory=list)
    werkzeuge: list[str] = Field(default_factory=list)
