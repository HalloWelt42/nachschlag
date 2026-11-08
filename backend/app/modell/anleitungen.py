"""Anleitungen finden (iFixit, WIKI-64): Frage mit Filtern, Treffer, Facetten und Einordnung im Gerätebaum. Alles kommt
aus dem eigenen Index des Buchs (Tabellen anleitungen, werkzeuge, geraete, geraet_kind, geraet_anleitung und das
Register der Einordnung)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Suchart = Literal["anleitung", "zerlegung", "geraet"]
Reihenfolge = Literal["passend", "einfach", "schnell", "titel"]


class Anleitungsfrage(BaseModel):
    text: str = Field("", description="Gerät, Bauteil oder Fehler; leer: alle")
    art: Suchart = Field("anleitung", description="Anleitungen, Zerlegungen oder Geräte")
    sprachen: list[str] = Field(default_factory=lambda: ["de"], description="de, en; vorerst nur Deutsch")
    schwierigkeit: list[int] = Field(default_factory=list, description="Stufen 1 (sehr einfach) bis 5; leer: alle")
    zeit_bis: int | None = Field(None, ge=1, description="Zeitaufwand höchstens so viele Minuten (obere Schätzung)")
    werkzeuge: list[str] = Field(default_factory=list, description="Ich habe: nur Anleitungen, für die diese Werkzeuge reichen")
    mehr_noetig: bool = Field(False, description="mit Ich habe auch die Anleitungen, die mehr Werkzeug brauchen (fehlende stehen dabei)")
    geraet: str = Field("", description="Pfad einer Geräteseite oder Kategorie: nur ihr ganzer Ast")
    bauteil: str = ""
    reihenfolge: Reihenfolge = "passend"
    ab: int = Field(0, ge=0)
    anzahl: int = Field(30, ge=1, le=100)


class Anleitungstreffer(BaseModel):
    pfad: str
    titel: str
    art: str
    sprache: str
    schwierigkeit: int
    schwierigkeit_text: str
    zeit: str
    schritte: int
    bild: str = Field("", description="Adresse des Bilds")
    werkzeuge: list[str] = Field(default_factory=list)
    fehlt: list[str] = Field(default_factory=list, description="mit Ich habe: Werkzeuge, die mir dafür fehlen")
    geraet: str = Field("", description="Titel des Geräts, das die Anleitung aufführt")
    bauteil: str = ""


class Geraetetreffer(BaseModel):
    pfad: str
    titel: str
    bild: str = ""
    kurz: str = ""
    anleitungen: int = Field(0, description="Anleitungen im ganzen Ast in den gewählten Sprachen")


class Facette(BaseModel):
    wert: str
    titel: str
    zahl: int


class Einordnungsschritt(BaseModel):
    pfad: str
    titel: str


class Anleitungsfunde(BaseModel):
    index: bool = Field(True, description="falsch: das Buch hat noch keinen eigenen Index (er entsteht als Auftrag)")
    anleitungen: list[Anleitungstreffer] = Field(default_factory=list)
    geraete: list[Geraetetreffer] = Field(default_factory=list)
    gesamt: int = 0
    brauchen_mehr: int = Field(0, description="mit Ich habe: so viele weitere passen, brauchen aber mehr Werkzeug")
    unter: list[Facette] = Field(default_factory=list, description="Unterkategorien oder Geräte des gewählten Knotens mit Zahl")
    bauteile: list[Facette] = Field(default_factory=list)
    einordnung: list[Einordnungsschritt] = Field(default_factory=list, description="Weg von der Startseite zum gewählten Gerät")


class Werkzeugeintrag(BaseModel):
    wort: str
    anleitungen: int


class Einordnung(BaseModel):
    """Wo eine Seite im Gerätebaum steht; bei einer Anleitung über das Gerät, das sie aufführt, samt Bauteil."""
    weg: list[Einordnungsschritt] = Field(default_factory=list)
    bauteil: str = ""
