"""Suchergebnisse: jeder Treffer sagt, welcher Weg ihn fand; die Antwort sagt, ob nur der Index antwortete."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Weg = Literal["bedeutung", "index"]


class Fragezahlen(BaseModel):
    """Was eine Trefferkarte einer Frage zeigt (Frage und Antwort): Stimmen, Antworten, Haken, Schlagwörter."""
    stimmen: int = 0
    antworten: int = 0
    akzeptiert: bool = False
    schlagwoerter: list[str] = Field(default_factory=list)


class Treffer(BaseModel):
    buch: str
    pfad: str
    titel: str
    abschnitt: str = Field("", description="Überschrift des gefundenen Abschnitts (Bedeutungssuche)")
    anker: str = Field("", description="Sprungziel im Artikel")
    ausschnitt: str = Field("", description="Stelle als reiner Text; Fundstellen in <em>")
    wege: list[Weg]
    rang: float = Field(description="gemischter Rang (RRF), größer ist besser")
    bild: str = ""
    frage: Fragezahlen | None = Field(None, description="Zahlen der Frage, wenn der Treffer eine ist (eigener Index)")


class Zeiten(BaseModel):
    index_ms: int
    bedeutung_ms: int | None = None


class Suchergebnis(BaseModel):
    frage: str
    treffer: list[Treffer]
    beste_stelle: Treffer | None = Field(None, description="die Stelle, die die Frage am besten beantwortet (nur mit Bedeutung)")
    nur_index: bool = Field(description="die Bedeutungssuche antwortete nicht oder ist nicht angebunden")
    hinweis: str = Field("", description="warum nur der Index antwortete, in Worten")
    bedeutung_angebunden: bool = Field(False, description="eine Bedeutungssuche ist eingerichtet (ohne ist nur Index der gewollte Betrieb)")
    zeiten: Zeiten
    index_gesamt: int = Field(0, description="geschätzte Zahl der Treffer im Index")


class Vorschlag(BaseModel):
    buch: str
    pfad: str
    titel: str
    weiterleitung: str = Field("", description="Ziel, wenn der Titel eine Weiterleitung ist (etwa auf einen Abschnitt)")
    kurztext: str = Field("", description="Anfang der Einleitung")
    bild: str = ""
