"""Übungen (Inhaltsart uebung, freeCodeCamp, WIKI-66): Programmieraufgaben in Kursen und Blöcken. Je Aufgabe liegt im
Buch eine Markdown-Datei mit festen Abschnitten (Beschreibung, Anleitung, Hinweise mit Tests, Startcode, Lösung); die
Gliederung (Kurs, Block, Aufgaben) steht in `content/curriculum/index.json`. Eine Wahrheit je Seite für Lesen und Index.

Der Kern der Übungen ist das Selbertesten: man schreibt den Code selbst, und jeder Prüfpunkt läuft als Test gegen ihn.
Das Buch bringt dafür seinen Testläufer mit (`pruefer`); die Oberfläche startet ihn und zeigt je Prüfpunkt, ob er
erfüllt ist."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Code(BaseModel):
    sprache: str = Field("", description="js, html, css ... wie im Codeblock angegeben")
    code: str


class Hinweis(BaseModel):
    """Ein Prüfpunkt der Aufgabe: was erfüllt sein muss (Text) und der Test, der es prüft."""
    html: str
    test: str = ""


class Aufgabenverweis(BaseModel):
    pfad: str
    titel: str


class Uebungsangaben(BaseModel):
    kurs: str = Field(description="Kennung des Kurses (rosetta-code)")
    kurs_titel: str
    block: str
    block_titel: str
    nr: int = Field(description="Stelle im Block, ab 1")
    anzahl: int = Field(description="Aufgaben im Block")
    beschreibung: str = Field("", description="HTML, gesäubert")
    anleitung: str = Field("", description="HTML, gesäubert")
    hinweise: list[Hinweis] = Field(default_factory=list)
    startcode: list[Code] = Field(default_factory=list)
    vorher: str = Field("", description="Code, der im Test vor dem eigenen Code läuft (--before-user-code--)")
    nachher: str = Field("", description="Code, der im Test nach dem eigenen Code läuft (--after-user-code--)")
    pruefer: str = Field("", description="Adresse des Testläufers aus dem Buch (Web Worker der Quelle); leer: das Buch "
                                         "bringt keinen mit, dann gibt es nur die Prüfpunkte zum Lesen")
    loesungen: list[Code] = Field(default_factory=list)
    vorige: Aufgabenverweis | None = None
    naechste: Aufgabenverweis | None = None


class Block(BaseModel):
    kennung: str
    titel: str
    einleitung: list[str] = Field(default_factory=list, description="Absätze, wie die Quelle den Block einführt")
    aufgaben: list[Aufgabenverweis] = Field(default_factory=list)


class Kurs(BaseModel):
    kennung: str
    titel: str
    einleitung: list[str] = Field(default_factory=list, description="Absätze, wie die Quelle den Kurs einführt")
    bloecke: list[Block] = Field(default_factory=list)


class Kursangaben(BaseModel):
    """Die Startseite eines Übungsbuchs: alle Kurse mit ihren Blöcken und Aufgaben."""
    kurse: list[Kurs] = Field(default_factory=list)
