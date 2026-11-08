"""Was der Bücherlader nach außen gibt (WIKI-57): das Verzeichnis der Bücher in den gewählten Sprachen, was seit dem
letzten Durchgang neu ist, die Abos mit dem Vergleich zur eigenen Bibliothek und der Platz auf dem Datenträger."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Wie ein Buch zur eigenen Bibliothek steht
Zustand = Literal["nicht_da", "aktuell", "neuer_da", "laedt", "wartet_auf_umschalten"]
Neuheit = Literal["", "buch", "fassung"]


class Angaben(BaseModel):
    """Was eine Quelle über ein Buch weiß (WIKI-62), zusammengeführt aus allen Quellen (der Katalog vor dem Verzeichnis).
    Vorschaubilder fremder Seiten werden nicht übernommen."""
    titel: str = ""
    beschreibung: str = ""
    artikel: int = Field(0, description="Zahl der Artikel; 0: unbekannt")
    medien: int = Field(0, description="Zahl der Bilder und anderen Medien; 0: unbekannt")
    autor: str = Field("", description="wer den Inhalt erstellt (etwa Wikipedia, Stack Exchange)")
    herausgeber: str = Field("", description="wer die ZIM-Datei erstellt (etwa openZIM)")
    kategorie: str = Field("", description="Kategorie laut Katalog (etwa wikipedia, stack_exchange, other)")
    schlagworte: list[str] = Field(default_factory=list, description="Schlagworte laut Katalog, ohne die technischen")
    bilder: bool | None = Field(None, description="mit Bildern; leer: unbekannt")
    videos: bool | None = Field(None, description="mit Videos; leer: unbekannt")
    volltext: bool | None = Field(None, description="mit eingebautem Volltextindex; leer: unbekannt")
    datum: str = Field("", description="Datum der Fassung laut Katalog (JJJJ-MM-TT)")


class Quellstand(BaseModel):
    """Eine Quelle des Bücherladers mit dem Ergebnis ihres letzten Durchgangs."""
    nr: int
    art: Literal["verzeichnis", "katalog"]
    name: str
    adresse: str
    an: bool
    rang: int = Field(description="Reihenfolge beim Laden: kleiner zuerst")
    zuletzt: str = Field("", description="wann zuletzt durchgesehen (ISO)")
    funde: int = Field(0, description="Dateien in den gewählten Sprachen beim letzten Durchgang")
    meldung: str = Field("", description="was beim letzten Durchgang nicht ging")


class NeueQuelle(BaseModel):
    art: Literal["verzeichnis", "katalog"] = Field(description="Verzeichnis eines Spiegels (Ordner je Bereich) oder Katalog")
    adresse: str = Field(min_length=8, max_length=300, pattern=r"^https?://", description="Adresse, mit / am Ende")
    name: str = Field("", max_length=80, description="leer: der Rechner aus der Adresse")


class QuellAenderung(BaseModel):
    an: bool | None = None
    rang: int | None = Field(None, ge=0)
    name: str | None = Field(None, max_length=80)


class Quellvorschlag(BaseModel):
    """Ein Spiegel aus der offiziellen Ladedatei, der noch keine Quelle ist."""
    name: str
    adresse: str
    land: str = ""


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
    quellen: int = Field(0, description="aus so vielen Quellen ladbar (Spiegel und Katalog)")


class Verzeichnisbuch(BaseModel):
    """Ein Buch des Verzeichnisses mit seinen Ausgaben."""
    basis: str = Field(description="Stamm ohne Ausgabe, etwa wikipedia_de_all")
    ordner: str = Field(description="Bereich im Verzeichnis, etwa wikipedia oder stack_exchange")
    sprache: str = Field(description="Sprache aus dem Namen: de, en, mul")
    titel: str = Field(description="aus dem Katalog der Bücher; ohne Katalog der Stamm")
    beschreibung: str = ""
    eintraege: int = Field(0, description="Zahl der Artikel laut Katalog; 0: unbekannt")
    angaben: Angaben = Field(default_factory=Angaben, description="was die Quellen über das Buch wissen")
    varianten: list[Variante]


Sortierung = Literal["titel", "neueste", "groesste", "kleinste"]


class Katalogfilter(BaseModel):
    """Was im Katalog gezeigt wird (WIKI-61). Ausgabe und Größe gelten je Ausgabe: ein Buch zeigt nur die passenden."""
    suche: str = Field("", description="Wort in Titel, Name oder Beschreibung")
    bereich: str = Field("", description="nur dieser Bereich, etwa wikipedia")
    sprache: str = Field("", description="nur diese Sprache (de, en, mul); leer: alle gewählten")
    ausgabe: Literal["", "maxi", "nopic", "mini", "einzeln"] = Field(
        "", description="mit Bildern, ohne Bilder, klein, oder Bücher mit nur einer Ausgabe; leer: alle")
    groesse_bis: int = Field(0, ge=0, description="höchstens so viele Bytes; 0: jede Größe")
    bibliothek: Literal["", "da", "nicht_da", "neuer_da"] = Field(
        "", description="in der eigenen Bibliothek, nicht da, oder es gibt eine neuere Fassung; leer: alle")
    nur_neu: bool = Field(False, description="nur, was seit dem letzten Durchgang neu ist")
    nur_abonniert: bool = Field(False, description="nur abonnierte Ausgaben")
    kategorie: str = Field("", description="nur diese Kategorie laut Katalog; leer: alle")
    sortierung: Sortierung = Field("titel", description="Neues steht immer vorn, danach so sortiert")


class Verzeichnisseite(BaseModel):
    eintraege: list[Verzeichnisbuch]
    gesamt: int = Field(description="Zahl der Bücher, die zur Abfrage passen")
    bereiche: list[str] = Field(description="alle Bereiche des Verzeichnisses in den gewählten Sprachen (für den Filter)")
    sprachen: list[str] = Field(default_factory=list, description="die Sprachen, die es im Verzeichnis gibt (für den Filter)")
    kategorien: list[str] = Field(default_factory=list, description="die Kategorien laut Katalog (für den Filter)")


class Durchgang(BaseModel):
    """Ein Durchgang durch das ganze Verzeichnis."""
    begonnen: str
    beendet: str
    ordner: int = Field(description="durchgesehene Bereiche")
    quellen: int = Field(1, description="durchgesehene Quellen")
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
    bleibt: str = Field("", description="warum sie nach der Frist noch da ist (etwa: die Bedeutungssuche liest sie noch ein)")


class Ladefortschritt(BaseModel):
    """Der Auftrag, der ein Buch gerade lädt (live nachgeführt über die Ereignisse der Aufträge)."""
    auftrag: str
    zustand: Literal["wartet", "laeuft"]
    fortschritt: float | None = Field(None, description="0 bis 1; leer: unbestimmt")
    schritt: str = Field("", description="was gerade geschieht, etwa '12,4 GB von 45,3 GB · 11 MB/s · noch etwa 50 Minuten'")
    zurueckgestellt: str = Field("", description="warum er noch wartet (etwa nur nachts)")


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
    laden: Ladefortschritt | None = Field(None, description="Stand des Ladens, solange ein Auftrag dafür offen ist")


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
    bereit: bool = Field(description="eine Quelle eingeschaltet und Ordner der Bücher beschreibbar")
    grund: str = Field("", description="warum nicht bereit")
    regeln: Regeln
    letzter_durchgang: Durchgang | None = None
    naechster_durchgang: str = Field("", description="wann der Zeitplan wieder durchsieht (ISO); leer: gleich")
    neu_ungesehen: int = Field(description="neue Bücher und Fassungen seit dem letzten Blick in die Liste")
    abos: list[Abo]
    platz: Platz | None = None
    quellen: list[Quellstand] = Field(default_factory=list)


class Geloescht(BaseModel):
    """Ein Buch, das ganz aus der Bibliothek genommen wurde (WIKI-77)."""
    kennung: str
    groesse: int = Field(description="so viele Bytes sind frei geworden")
    abo_beendet: bool = Field(description="das Abo endete mit, weil keine Fassung des Buchs mehr da ist")
