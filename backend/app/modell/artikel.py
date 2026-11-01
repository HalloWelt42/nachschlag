"""Ein Artikel, wie ein Baustein ihn aufbereitet: gesäubertes HTML, Gliederung und Steckbrief für die Oberfläche."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Abschnitt(BaseModel):
    anker: str = Field(description="Kennung im HTML (id), Ziel für Sprünge")
    titel: str
    ebene: int = Field(ge=2, le=4, description="2 Hauptabschnitt, 3 Unterabschnitt")


class Steckbrief(BaseModel):
    """Infobox oder Taxobox der Quelle, neu gesetzt (eigenes Lesedesign); `html` ist bereits gesäubert."""
    titel: str
    html: str


class Verweiszahlen(BaseModel):
    intern: int = 0                  # Verweise auf Artikel im selben Buch
    ohne_ziel: int = 0               # zu reinem Text gemacht (Artikel fehlt im Buch)
    koordinaten: int = 0             # Orte (geo:), als Ort gekennzeichnet
    online: int = 0                  # Verweise ins Netz, aus dem Text herausgenommen


#: Wie eine Seite gezeigt wird: Lesedesign (Text mit Inhalt und Steckbrief), Übersicht (Kacheln mit Bild, etwa die
#: Startseite eines Buchs) oder die Seite unverändert
Darstellung = Literal["lesedesign", "uebersicht", "original"]


class Kachel(BaseModel):
    """Ein Eintrag einer Übersicht: Artikel mit Bild."""
    pfad: str
    titel: str
    bild: str = ""


class Artikel(BaseModel):
    buch: str
    pfad: str = Field(description="Pfad im Buch nach dem Auflösen von Weiterleitungen")
    angefragt: str = Field(description="Pfad, wie er angefragt wurde")
    anker: str = Field("", description="Abschnitt, auf den eine Weiterleitung zeigt")
    titel: str
    darstellung: Darstellung
    baustein: str
    html: str = Field(description="Inhalt für das Lesedesign; bei der Originalansicht leer")
    einleitung: str = Field("", description="Einleitung als reiner Text (Vorschau, Vorlesen)")
    abschnitte: list[Abschnitt] = Field(default_factory=list)
    steckbrief: Steckbrief | None = None
    bild: str = Field("", description="Adresse des ersten Bilds (Vorschau in Listen)")
    verweise: Verweiszahlen = Field(default_factory=Verweiszahlen)
    online: list[str] = Field(default_factory=list, description="Online-Verweise (Belege, Weblinks) für 'Über diesen Artikel'")
    original: str = Field(description="Adresse der unveränderten Seite (Originalansicht)")
    kacheln: list[Kachel] = Field(default_factory=list, description="Einträge der Übersicht (nur Darstellung uebersicht)")
