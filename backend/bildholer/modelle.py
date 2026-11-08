"""Die Verträge zwischen Nachschlag und Bildholer: Regeln, Vormerkung, Stand. Nachschlag hält die Regeln in seinen
Einstellungen und schickt sie bei jedem Start und jeder Änderung; der Bildholer merkt sich die zuletzt geschickten, damit
er nach einem Neustart allein weiterarbeitet."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

#: Breiten, die die Bildquelle als Vorschaubild vorrätig hält; andere rechnet sie neu und drosselt dann schnell
BREITEN = (960, 1280, 1920)

#: Vorrang einer Vormerkung: 0 gerade geöffnet, 1 gelesen, gemerkt oder in einem Thema, 2 Steckbriefbild eines
#: beliebigen Artikels (nachts nach und nach, WIKI-81)
Vorrang = Literal[0, 1, 2]


class Regeln(BaseModel):
    an: bool = Field(True, description="aus: holt nichts, nimmt aber Vormerkungen an")
    abstand_s: float = Field(3.0, ge=1, le=3600, description="Pause zwischen zwei Bildern")
    wann: Literal["immer", "nachts"] = "immer"
    nacht_von: int = Field(1, ge=0, le=23, description="Beginn der Nacht (Stunde, Ortszeit)")
    nacht_bis: int = Field(6, ge=0, le=23, description="Ende der Nacht (Stunde, Ortszeit)")
    breite: Literal[960, 1280, 1920] = 1280
    platz_gb: float = Field(200, ge=1, description="so viel Platz dürfen die Bilder höchstens belegen")
    bei_drosselung: Literal["langsamer", "anhalten"] = "langsamer"
    absender: str = Field("Nachschlag-Bildholer/1.0 (https://github.com/HalloWelt42/nachschlag)", min_length=8, max_length=200,
                          description="Kennung bei der Bildquelle mit Kontakt (Webseite oder E-Mail); ohne sperrt sie")


class Vormerkung(BaseModel):
    quelle: str = Field(pattern=r"^[a-z0-9.-]+\.org$", description="Wiki, aus dem die Bilder stammen, etwa de.wikipedia.org")
    namen: list[str] = Field(max_length=2000, description="Dateinamen wie im Buch (ohne Präfix Datei:)")
    vorrang: Vorrang = 1


class Bildzeile(BaseModel):
    quelle: str
    name: str
    breite: int
    original: int = Field(description="Breite des Originals in der Bildquelle")
    am: str


class Stand(BaseModel):
    zustand: Literal["laeuft", "wartet", "ruht", "angehalten", "voll", "aus"]
    grund: str = Field("", description="warum er gerade nichts holt")
    abstand_s: float
    geladen: int
    heute: int
    belegt_bytes: int
    platz_bytes: int
    fehlgeschlagen: int
    offen: dict[str, int] = Field(default_factory=dict, description="vorgemerkt und noch nicht geholt, je Vorrang")
    zuletzt: list[Bildzeile] = Field(default_factory=list)
