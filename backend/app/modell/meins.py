"""Was einem Konto gehört (Meins): Merkzettel, Notizen, eigene Beispiele, Verlauf mit Lesestand, Vorlieben (etwa die
Fassung je Buch). Gilt auf allen Geräten des Kontos. Einträge zeigen auf ein Buch über seinen Namen ohne Datum
(`buch_name`); so überstehen sie neue Fassungen des Buchs. `buch` ist die Kennung der Datei, die gerade zu diesem Namen gehört (leer, wenn es keine
mehr gibt)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .artikel import Beleg


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
    belege: list[Beleg] = Field(default_factory=list, max_length=200, description="Recherchemodus: Belege der Stelle")
    quelle_url: str = Field("", max_length=2000, description="Recherchemodus: der Artikel im Netz")


class NotizAenderung(BaseModel):
    text: str = Field(max_length=20000)


class Notizbild(BaseModel):
    """Ein Bild an einer Notiz (WIKI-51): liegt in der Kellerwolke (Knoten), die Notiz merkt sich Name und Art."""
    id: str
    knoten: str = Field(description="Knoten der Datei in der Kellerwolke")
    name: str = Field(description="Dateiname, wie er hochkam (oder aus der Zwischenablage benannt)")
    typ: str = Field(description="Art des Bilds, etwa image/png")
    groesse: int = 0
    angelegt: str


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
    belege: list[Beleg] = Field(default_factory=list)
    quelle_url: str = ""
    bilder: list[Notizbild] = Field(default_factory=list, description="Bilder an der Notiz, in der Reihenfolge des Anlegens")
    angelegt: str
    geaendert: str


#: Sprachen eigener Beispiele: die von Ausprobieren (Bauplan docs/AUSPROBIEREN.md)
Codesprache = Literal["php", "python", "javascript"]


class BeispielNeu(BaseModel):
    """Eigenes Beispiel (WIKI-48): die Kopie aus Ausprobieren, behalten am Artikel, unter dem Code, aus dem sie stammt."""
    buch: str = Field(description="Kennung des Buchs, in dem das Beispiel steht")
    pfad: str
    titel: str = Field(min_length=1, max_length=200)
    sprache: Codesprache
    code: str = Field(min_length=1, max_length=20_000)
    vorlage: str = Field("", max_length=300, description="Titel des Beispiels im Artikel, aus dem es stammt")
    block: int = Field(-1, ge=-1, le=10_000, description="Codeblock im Artikel (ab 0), hinter dem es steht; -1: am Ende")
    fassung: str = Field("", max_length=10, description="Fassung der Sprache, in der es lief (PHP, WIKI-52); leer: keine Wahl")


class BeispielAenderung(BaseModel):
    titel: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=20_000)
    fassung: str = Field("", max_length=10)


class Beispiel(BaseModel):
    id: str
    buch_name: str
    buch: str = Field(description="Kennung des Buchs, das heute zum Namen gehört; leer, wenn es keins gibt")
    pfad: str
    titel: str
    sprache: Codesprache
    code: str
    vorlage: str = ""
    block: int = -1
    fassung: str = ""
    angelegt: str
    geaendert: str


class BewertungNeu(BaseModel):
    """Eingabe: eine Seite bewerten (WIKI-71), etwa eine Anleitung, die man gemacht hat; 0 Sterne nimmt die Bewertung weg."""
    buch: str = Field(description="Kennung des Buchs")
    pfad: str
    sterne: int = Field(ge=0, le=5)


class Bewertung(BaseModel):
    buch_name: str = Field(description="Name des Buchs ohne Stand: die Bewertung gilt über neue Fassungen hinweg")
    pfad: str
    sterne: int = Field(ge=1, le=5)
    geaendert: str
