"""Ein Buch der Bibliothek: eine ZIM-Datei mit den Angaben, die sie über sich macht, und dem, was sie kann."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Grundstruktur eines Buchs; danach wählt Nachschlag den Baustein (siehe bausteine/)
Art = Literal["enzyklopaedie", "dokumentation", "frage_antwort", "anleitung", "uebung", "webseite", "sonstiges"]


class Faehigkeiten(BaseModel):
    titelindex: bool                 # Vorschläge beim Tippen
    volltext: bool                   # Index für die Suche
    bilder: bool                     # Medien in der Datei
    lesedesign: bool                 # ein Baustein mit eigenem Lesedesign; sonst Originalansicht


class Archivstand(BaseModel):
    """Eine Quelle im Archiv (WIKI-46): ersetzt durch eine neuere Fassung derselben Quelle oder von Hand archiviert.
    Ohne "mitnutzen" fehlt sie in Suche, Vorschlägen, Stöbern und Startseite, bleibt aber lesbar."""
    grund: Literal["ersetzt", "von_hand"]
    ersetzt_durch: str = Field("", description="Kennung der neueren Fassung (Grund ersetzt)")
    mitnutzen: bool = False


class Buch(BaseModel):
    kennung: str = Field(description="Dateiname ohne .zim; eindeutig in der Bibliothek")
    name: str = Field(description="Name des Buchs ohne Fassung (Angabe Name), etwa wikipedia_de_all")
    titel: str
    beschreibung: str = ""
    sprache: str = Field("", description="Sprache nach ISO 639-3 aus der Datei, etwa deu")
    stand: str = Field("", description="Datum der Fassung aus der Datei (JJJJ-MM-TT)")
    erzeuger: str = Field("", description="Werkzeug, das die Datei erzeugt hat")
    art: Art
    eintraege: int
    artikel: int
    medien: int
    groesse: int = Field(description="Größe der Datei in Bytes")
    faehigkeiten: Faehigkeiten
    startseite: str = Field("", description="Pfad der Startseite im Buch")
    archiv: Archivstand | None = Field(None, description="im Archiv (WIKI-46); leer: aktive Quelle")


class Bibliotheksstand(BaseModel):
    ordner: str
    buecher: list[Buch]
    fehler: list[str] = Field(default_factory=list, description="Dateien, die sich nicht öffnen ließen, mit Grund")
