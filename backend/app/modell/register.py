"""Register (WIKI-39, docs/SUCHE.md Punkt 10): Schlagwörter und Autoren der Frage-Antwort-Bücher, über alle Bücher oder
eines, seitenweise. `ohne_index` nennt die Bücher, deren Register erst mit ihrem eigenen Index entsteht."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .artikel import Fragekarte

Sortierung = Literal["stimmen", "neueste"]


class SchlagwortEintrag(BaseModel):
    wort: str
    fragen: int
    stimmen: int
    buecher: list[str] = Field(description="Bücher, in denen das Schlagwort vorkommt")


class SchlagwortSeite(BaseModel):
    eintraege: list[SchlagwortEintrag]
    gesamt: int
    ohne_index: list[str] = Field(default_factory=list)


class RegisterFrage(Fragekarte):
    buch: str


class FragenSeite(BaseModel):
    wort: str
    eintraege: list[RegisterFrage]
    gesamt: int
    ohne_index: list[str] = Field(default_factory=list)


class AutorEintrag(BaseModel):
    buch: str
    schluessel: str = Field(description="Kontonummer im Buch, sonst name:<Name>")
    autor: str
    beitraege: int
    fragen: int
    antworten: int
    akzeptiert: int = Field(description="akzeptierte Antworten")
    stimmen: int
    von: str = Field("", description="erster Beitrag, JJJJ-MM-TT")
    bis: str = Field("", description="letzter Beitrag, JJJJ-MM-TT")


class AutorenSeite(BaseModel):
    eintraege: list[AutorEintrag]
    gesamt: int
    ohne_index: list[str] = Field(default_factory=list)


class AutorBeitrag(BaseModel):
    pfad: str
    titel: str
    art: Literal["frage", "antwort"]
    stimmen: int
    datum: str = ""
    akzeptiert: bool = False


class AutorSeite(BaseModel):
    autor: AutorEintrag
    beitraege: list[AutorBeitrag]
    gesamt: int
