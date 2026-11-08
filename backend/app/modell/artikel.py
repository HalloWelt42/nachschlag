"""Ein Artikel, wie ein Baustein ihn aufbereitet: gesäubertes HTML, Gliederung und Steckbrief für die Oberfläche."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .anleitung import Anleitungsangaben, Geraeteangaben
from .uebung import Kursangaben, Uebungsangaben


class Abschnitt(BaseModel):
    anker: str = Field(description="Kennung im HTML (id), Ziel für Sprünge")
    titel: str
    ebene: int = Field(ge=2, le=4, description="2 Hauptabschnitt, 3 Unterabschnitt")


class Steckbrief(BaseModel):
    """Infobox oder Taxobox der Quelle, neu gesetzt (eigenes Lesedesign); `html` ist bereits gesäubert."""
    titel: str
    html: str
    code: bool = Field(False, description="der Titel ist ein Name aus dem Code (in Schrift des Editors)")


class Verweiszahlen(BaseModel):
    intern: int = 0                  # Verweise auf Artikel im selben Buch
    ohne_ziel: int = 0               # zu reinem Text gemacht (Artikel fehlt im Buch)
    koordinaten: int = 0             # Orte (geo:), als Ort gekennzeichnet
    online: int = 0                  # Verweise ins Netz, aus dem Text herausgenommen


#: Wie eine Seite gezeigt wird: Lesedesign (Text mit Inhalt und Steckbrief), Übersicht (Kacheln mit Bild, etwa die
#: Startseite eines Buchs) oder die Seite unverändert
#: anleitung, geraet und anleitungen (Startseite: Anleitungen finden) gehören zur Inhaltsart Anleitung (WIKI-64)
class Kategorieverweis(BaseModel):
    """Eine Kategorie (oder eine Seite in ihr) eines Buchs mit Kategorien (WIKI-75)."""
    pfad: str
    titel: str


class Kategorieangaben(BaseModel):
    """Eine Kategorieseite: ihre Oberkategorien, Unterkategorien und alle Seiten darin (auch die, die die Quelle nur
    über nachgeladene Teile zeigt)."""
    ober: list[Kategorieverweis] = Field(default_factory=list)
    unter: list[Kategorieverweis] = Field(default_factory=list)
    seiten: list[Kategorieverweis] = Field(default_factory=list)


Darstellung = Literal["lesedesign", "uebersicht", "original", "anleitung", "geraet", "anleitungen", "uebung", "uebungen", "kategorie"]


class Nachbar(BaseModel):
    """Eine Seite in einer Liste (Nachbarn in der Rubrik, Einträge einer Rubrik)."""
    pfad: str
    titel: str


class Rueckverweise(BaseModel):
    """Seiten, die auf eine Seite verweisen (WIKI-20), aus dem eigenen Index des Buchs."""
    bekannt: bool = Field(description="falsch: das Buch hat keinen eigenen Index mit Verweisen (dann weiß es das nicht)")
    gesamt: int = 0
    seiten: list[Nachbar] = Field(default_factory=list)


class Gruppe(BaseModel):
    """Eine Rubrik eines Buchs mit ihren Seiten (Gliederung einer Dokumentation)."""
    titel: str
    eintraege: list[Nachbar]


class Fragekarte(BaseModel):
    """Eine Frage in einer Fragenliste (Startseite und Schlagwortseiten eines Frage-Antwort-Buchs)."""
    pfad: str
    titel: str
    auszug: str = ""
    stimmen: int = 0
    antworten: int = 0
    akzeptiert: bool = False
    schlagwoerter: list[str] = Field(default_factory=list)
    gefragt: str = ""


class Beleg(BaseModel):
    """Ein Einzelnachweis eines Artikels (WIKI-31, in der Oberfläche "Beleg"): Nummer wie in der Quelle, Text, Verweis."""
    nummer: int
    text: str
    url: str = ""


class Beitrag(BaseModel):
    """Ein Beitrag einer Frage-Antwort-Seite, wie ihn Register und Autorenseite brauchen (WIKI-39)."""
    art: Literal["frage", "antwort"]
    autor: str = Field("", description="Name, wie er im Buch steht")
    autor_nr: str = Field("", description="Nummer des Kontos im Buch (users/13055/...); unterscheidet gleiche Namen")
    stimmen: int = 0
    datum: str = Field("", description="JJJJ-MM-TT; leer, wenn das Jahr nicht dasteht")
    akzeptiert: bool = False


class FrageAngaben(BaseModel):
    """Metadaten einer Frage (Inhaltsart Frage und Antwort) für Index, Register und Trefferkarte (docs/SUCHE.md,
    Punkt 11). Der Baustein liest sie einmal; Lesen und Index nutzen dieselben Werte."""
    stimmen: int = 0
    antworten: int = 0
    akzeptiert: bool = False
    gefragt: str = Field("", description="JJJJ-MM-TT")
    schlagwoerter: list[str] = Field(default_factory=list)
    beitraege: list[Beitrag] = Field(default_factory=list)


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
    belege: list[Beleg] = Field(default_factory=list, description="Einzelnachweise; im Text stehen sie als span.beleg[data-beleg]")
    quelle_url: str = Field("", description="Der Artikel im Netz (etwa in der Wikipedia), für Belege und Zitate")
    autor: str = Field("", description="Wer die Seite verfasst hat, soweit die Quelle es nennt (Frage und Antwort: wer fragte)")
    datum: str = Field("", description="Wann (JJJJ-MM-TT; Frage und Antwort: gefragt am), für Zitate")
    original: str = Field(description="Adresse der unveränderten Seite (Originalansicht)")
    kacheln: list[Kachel] = Field(default_factory=list, description="Einträge der Übersicht (nur Darstellung uebersicht)")
    gruppen: list[Gruppe] = Field(default_factory=list, description="Rubriken der Übersicht eines Handbuchs (nur Darstellung uebersicht)")
    rubrik: str = Field("", description="Rubrik der Seite im Buch (Dokumentation), für den Pfad")
    rubrik_pfad: str = Field("", description="Seite der Rubrik, wenn das Buch eine hat; sonst filtert die Startseite nach ihr")
    nachbarn: list[Nachbar] = Field(default_factory=list, description="die Seiten derselben Rubrik")
    titelart: Literal["text", "code"] = Field("text", description="code: der Titel ist ein Name aus dem Code (Funktion, Klasse)")
    fragen: list[Fragekarte] = Field(default_factory=list, description="Fragen einer Fragenliste (nur Darstellung uebersicht)")
    zurueck: str = Field("", description="Pfad der vorigen Seite einer Liste, leer auf der ersten")
    weiter: str = Field("", description="Pfad der nächsten Seite einer Liste, leer auf der letzten")
    anleitung: Anleitungsangaben | None = Field(None, description="Anleitung oder Zerlegung (Darstellung anleitung)")
    geraet: Geraeteangaben | None = Field(None, description="Gerät oder Kategorie (Darstellung geraet, anleitungen)")
    uebung: Uebungsangaben | None = Field(None, description="Aufgabe eines Übungsbuchs (Darstellung uebung)")
    kurse: Kursangaben | None = Field(None, description="Kurse eines Übungsbuchs (Darstellung uebungen)")
    kategorien: list[Kategorieverweis] = Field(default_factory=list, description="Kategorien der Seite, wie das Buch sie nennt (WIKI-75)")
    kategorie: Kategorieangaben | None = Field(None, description="Eine Kategorieseite (Darstellung kategorie)")
