"""Was einem Konto gehört (Meins): Merkzettel, Notizen, Verlauf mit Lesestand, Vorlieben (etwa die Fassung je Buch). Gilt auf
allen Geräten des Kontos. Einträge zeigen auf ein Buch über seinen Namen ohne Datum (`buch_name`); so überstehen sie
neue Fassungen des Buchs. `buch` ist die Kennung der Datei, die gerade zu diesem Namen gehört (leer, wenn es keine
mehr gibt)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Merken(BaseModel):
    """Eingabe: eine Seite (oder Stelle) merken."""
    buch: str = Field(description="Kennung des Buchs, aus dem gemerkt wird")
    pfad: str
    titel: str = Field(max_length=500)
    bild: str = ""
    abschnitt: str = Field("", max_length=300, description="gemerkte Stelle (Abschnitt); leer: die ganze Seite")


class Merkeintrag(BaseModel):
    id: str
    buch_name: str
    buch: str = Field(description="Kennung des Buchs, das heute zum Namen gehört; leer, wenn es keins gibt")
    pfad: str
    titel: str
    bild: str = ""
    abschnitt: str = ""
    angelegt: str
    anteil: float = Field(0, description="gelesener Anteil laut Verlauf (0 bis 1)")


class Lesestand(BaseModel):
    """Eingabe: wo das Lesen einer Seite gerade steht (die Oberfläche meldet ihn beim Lesen gedrosselt)."""
    buch: str
    pfad: str
    titel: str = Field(max_length=500)
    bild: str = ""
    abschnitt: str = Field("", max_length=300)
    anteil: float = Field(0, ge=0, le=1)
    sekunden: int = Field(0, ge=0, le=86400, description="Lesezeit seit der letzten Meldung")


class Suchmeldung(BaseModel):
    frage: str = Field(min_length=1, max_length=400)
    treffer: int = 0


class Verlaufseintrag(BaseModel):
    id: str
    art: Literal["artikel", "suche"]
    buch_name: str = ""
    buch: str = ""
    pfad: str = ""
    titel: str = ""
    bild: str = ""
    abschnitt: str = ""
    anteil: float = 0
    sekunden: int = 0
    frage: str = ""
    treffer: int = 0
    zuletzt: str


class Vorliebe(BaseModel):
    wert: str = Field(max_length=200)


class NotizNeu(BaseModel):
    """Eingabe: eine Notiz am ganzen Artikel (ohne Zitat) oder an einer markierten Stelle (mit Zitat). Ohne Text ist
    sie eine Markierung."""
    buch: str = Field(description="Kennung des Buchs, in dem notiert wird")
    pfad: str
    titel: str = Field(max_length=500)
    bild: str = ""
    abschnitt: str = Field("", max_length=300, description="Abschnitt, in dem die Stelle steht")
    zitat: str = Field("", max_length=4000, description="markierter Text; leer: Notiz am ganzen Artikel")
    davor: str = Field("", max_length=200, description="Text unmittelbar vor dem Zitat, damit sich gleiche Stellen unterscheiden")
    text: str = Field("", max_length=20000)


class NotizAenderung(BaseModel):
    text: str = Field(max_length=20000)


class Notiz(BaseModel):
    id: str
    buch_name: str
    buch: str = Field(description="Kennung des Buchs, das heute zum Namen gehört; leer, wenn es keins gibt")
    pfad: str
    titel: str
    bild: str = ""
    abschnitt: str = ""
    zitat: str = ""
    davor: str = ""
    text: str = ""
    angelegt: str
    geaendert: str
