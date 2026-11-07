"""Was der Bücherlader nach außen gibt (WIKI-57): das Verzeichnis der Bücher in den gewählten Sprachen, was seit dem
letzten Durchgang neu ist, die Abos mit dem Vergleich zur eigenen Bibliothek und der Platz auf dem Datenträger."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Wie ein Buch zur eigenen Bibliothek steht
Zustand = Literal["nicht_da", "aktuell", "neuer_da", "laedt", "wartet_auf_umschalten"]
Neuheit = Literal["", "buch", "fassung"]


class Variante(BaseModel):
    """Eine Ausgabe eines Buchs im Verzeichnis, etwa mit Bildern (maxi), ohne Bilder (nopic) oder klein (mini)."""
    stamm: str = Field(description="Dateiname ohne Stand, etwa wikipedia_de_all_maxi; Kennung für Abos")
    ausgabe: str = Field(description="maxi, nopic, mini; leer, wenn das Buch nur eine Ausgabe hat")
    stand: str = Field(description="jüngster Stand im Verzeichnis (JJJJ-MM)")
    groesse: int = Field(description="Größe der jüngsten Datei in Bytes, laut Verzeichnis gerundet")
    neu: Neuheit = Field(description="seit dem letzten Durchgang neu: das ganze Buch oder eine Fassung; leer: nicht neu")
    abonniert: bool
    lokal_stand: str = Field("", description="Stand in der eigenen Bibliothek; leer: nicht da")
    zustand: Zustand


class Verzeichnisbuch(BaseModel):
    """Ein Buch des Verzeichnisses mit seinen Ausgaben."""
    basis: str = Field(description="Stamm ohne Ausgabe, etwa wikipedia_de_all")
    ordner: str = Field(description="Bereich im Verzeichnis, etwa wikipedia oder stack_exchange")
    sprache: str = Field(description="Sprache aus dem Namen: de, en, mul")
    titel: str = Field(description="aus dem Katalog der Bücher; ohne Katalog der Stamm")
    beschreibung: str = ""
    eintraege: int = Field(0, description="Zahl der Artikel laut Katalog; 0: unbekannt")
    varianten: list[Variante]


class Verzeichnisseite(BaseModel):
    eintraege: list[Verzeichnisbuch]
    gesamt: int = Field(description="Zahl der Bücher, die zur Abfrage passen")
    bereiche: list[str] = Field(description="alle Bereiche des Verzeichnisses in den gewählten Sprachen (für den Filter)")


class Durchgang(BaseModel):
    """Ein Durchgang durch das ganze Verzeichnis."""
    begonnen: str
    beendet: str
    ordner: int = Field(description="durchgesehene Bereiche")
    dateien: int = Field(description="Dateien in den gewählten Sprachen, alle Stände")
    buecher: int = Field(description="Bücher (Stämme) in den gewählten Sprachen")
    neue_buecher: int
    neue_fassungen: int
    erstaufnahme: bool = Field(description="erster Durchgang: alles ist bekannt, nichts gilt als neu")
    hinweise: list[str] = Field(default_factory=list, description="Teile, die nicht antworteten (etwa der Katalog)")


class Rueckfall(BaseModel):
    """Die vorige Fassung nach dem Umschalten, bis sie entfernt wird."""
    kennung: str
    entfernt_ab: str = Field(description="Datum, ab dem sie entfernt wird (JJJJ-MM-TT)")


class Abo(BaseModel):
    stamm: str
    titel: str
    seit: str
    lokal_stand: str = Field("", description="aktive Fassung in der Bibliothek; leer: noch nicht da")
    neuester_stand: str = Field("", description="jüngster Stand im Verzeichnis; leer: noch nicht durchgesehen")
    neueste_groesse: int = 0
    zustand: Zustand
    wartet: str = Field("", description="geladene, geprüfte Fassung, die aufs Umschalten wartet (Kennung)")
    rueckfall: Rueckfall | None = None
    hinweis: str = Field("", description="warum eine neuere Fassung nicht lädt (Platz, nur melden)")


class Platz(BaseModel):
    ordner: str
    frei: int = Field(description="frei auf dem Datenträger der Bücher, Bytes")
    gesamt: int
    reserve: int = Field(description="so viel bleibt immer frei; darunter lädt nichts")
    buecher: int = Field(description="belegt von Büchern der Bibliothek und wartenden Fassungen")
    im_laden: int = Field(description="belegt von angefangenen Dateien")
    hoechstens: int = Field(description="Grenze für Bücher; 0: keine")


class Regeln(BaseModel):
    """Die Regeln aus den Einstellungen, zusammengefasst für die Anzeige (geändert werden sie dort)."""
    sprachen: list[str]
    durchsicht: str = Field(description="taeglich, woechentlich, monatlich")
    neue_fassung: str = Field(description="laden oder melden")
    laden_wann: str = Field(description="immer oder nachts")
    vorige_tage: int


class Laderstand(BaseModel):
    bereit: bool = Field(description="Verzeichnis eingestellt und Ordner der Bücher beschreibbar")
    grund: str = Field("", description="warum nicht bereit")
    regeln: Regeln
    letzter_durchgang: Durchgang | None = None
    naechster_durchgang: str = Field("", description="wann der Zeitplan wieder durchsieht (ISO); leer: gleich")
    neu_ungesehen: int = Field(description="neue Bücher und Fassungen seit dem letzten Blick in die Liste")
    abos: list[Abo]
    platz: Platz | None = None
