"""Themen eines Kontos: Sammlungen von Artikeln aus allen Büchern, gegliedert in Bereiche. Ein Thema kann mit einer
gespeicherten Suche wachsen: neue Treffer kommen als Angebot, nie von selbst; abgelehnte kommen nicht wieder. Artikel
zeigen wie in Meins auf den Namen des Buchs ohne Datum (`buch_name`), damit sie neue Fassungen überstehen."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ThemaNeu(BaseModel):
    titel: str = Field(min_length=1, max_length=120)
    beschreibung: str = Field("", max_length=1000)
    regel: str = Field("", max_length=400, description="Suche, mit der das Thema wächst; leer: nur von Hand")
    regel_buch: str = Field("", description="Kennung des Buchs, auf das die Suche beschränkt ist; leer: alle Bücher")


class ThemaAenderung(BaseModel):
    """Nur gesetzte Felder ändern sich."""
    titel: str | None = Field(None, min_length=1, max_length=120)
    beschreibung: str | None = Field(None, max_length=1000)
    regel: str | None = Field(None, max_length=400)
    regel_buch: str | None = None


class Bereich(BaseModel):
    id: str
    titel: str
    platz: int


class BereichNeu(BaseModel):
    titel: str = Field(min_length=1, max_length=120)


class BereichAenderung(BaseModel):
    titel: str | None = Field(None, min_length=1, max_length=120)
    platz: int | None = Field(None, ge=0, description="neue Stelle unter den Bereichen (ab 0)")


class Themeneintrag(BaseModel):
    id: str
    bereich: str = Field("", description="Kennung des Bereichs; leer: ohne Bereich")
    buch_name: str
    buch: str = Field(description="Kennung des Buchs, das heute zum Namen gehört; leer, wenn es keins gibt")
    pfad: str
    titel: str
    bild: str = ""
    platz: int
    anteil: float = Field(0, description="gelesener Anteil laut Verlauf (0 bis 1)")
    gelesen_je: bool = Field(False, description="steht im Verlauf (schon einmal geöffnet)")
    notizen: int = 0


class EintragNeu(BaseModel):
    buch: str = Field(description="Kennung des Buchs")
    pfad: str
    titel: str = Field(max_length=500)
    bild: str = ""
    bereich: str = ""


class Verschieben(BaseModel):
    bereich: str = Field("", description="Ziel; leer: ohne Bereich")
    platz: int = Field(ge=0, description="Stelle im Zielbereich (ab 0); größer als die Zahl der Einträge: ans Ende")


class Thema(BaseModel):
    id: str
    titel: str
    beschreibung: str = ""
    regel: str = ""
    regel_buch: str = Field("", description="Kennung des Buchs der Suche (heute); leer: alle Bücher")
    angelegt: str
    bereiche: list[Bereich] = []
    eintraege: list[Themeneintrag] = []


class Themenkopf(BaseModel):
    """Ein Thema in der Liste: Zahlen und bis zu vier Bilder."""
    id: str
    titel: str
    eintraege: int
    bereiche: int
    buecher: int
    regel: str = ""
    bilder: list[str] = []


class Zuordnung(BaseModel):
    """Ein Artikel in einem Thema (für Artikelkopf und Notizen: in welchen Themen steht er)."""
    thema: str
    titel: str
    buch_name: str
    pfad: str


class Angebot(BaseModel):
    """Ein Treffer der gespeicherten Suche, der noch nicht im Thema steht und nicht abgelehnt ist."""
    buch: str
    pfad: str
    titel: str
    bild: str = ""
    auszug: str = Field("", description="Stelle als reiner Text; Fundstellen in <em>")


class Ablehnung(BaseModel):
    buch: str
    pfad: str
