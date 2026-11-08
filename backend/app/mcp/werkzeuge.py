"""Die MCP-Werkzeuge von Nachschlag. Jedes nennt Namen, Beschreibung (für die KI, was es kann und wann es passt), sein
Eingabemodell und eine Arbeit, die Text liefert. Text statt JSON, weil Modelle ihn am besten weiterverwenden; jede
Antwort nennt Buch und Pfad, damit die KI weiterlesen und belegen kann."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from lxml import html as lhtml
from pydantic import BaseModel, Field

from ..artikel import Artikelleser
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..suche import Suche

#: so viel Text eines Artikels geht höchstens an die KI (lange Artikel tragen ihr Thema vorn)
LESEN_HOECHSTENS = 20_000


@dataclass(frozen=True)
class Werkzeug:
    name: str
    beschreibung: str
    eingabe: type[BaseModel]
    arbeit: Callable[[BaseModel], Awaitable[str]]


class BuecherEingabe(BaseModel):
    art: str = Field("", description="nur Bücher dieser Art: enzyklopaedie, dokumentation, frage_antwort, anleitung, uebung; leer: alle")


class SuchenEingabe(BaseModel):
    frage: str = Field(min_length=1, max_length=400, description="Begriff, Name oder Frage in eigenen Worten")
    buecher: list[str] = Field(default_factory=list, description="Kennungen der Bücher (aus nachschlag_buecher); leer: alle")
    anzahl: int = Field(10, ge=1, le=30, description="so viele Treffer höchstens")


class LesenEingabe(BaseModel):
    buch: str = Field(description="Kennung des Buchs, wie sie ein Treffer nennt")
    pfad: str = Field(description="Pfad der Seite im Buch, wie ihn ein Treffer nennt")


def _text(html: str) -> str:
    if not html:
        return ""
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    for el in wurzel.iter("p", "li", "h1", "h2", "h3", "h4", "tr", "pre", "dd", "dt", "br"):
        el.tail = "\n" + (el.tail or "")
    return "\n".join(z.strip() for z in wurzel.text_content().splitlines() if z.strip())


def werkzeuge(bibliothek: Bibliothek, suche: Suche, leser: Artikelleser) -> list[Werkzeug]:
    async def buecher(e: BuecherEingabe) -> str:
        stand = await bibliothek.stand()
        liste = [b for b in stand.buecher if not b.archiv and (not e.art or b.art == e.art)]
        if not liste:
            return "Keine Bücher" + (f" der Art {e.art}" if e.art else "") + " in der Bibliothek."
        return "\n".join(f"{b.kennung}: {b.titel} ({b.art}, Sprache {b.sprache}, {b.artikel} Artikel, Stand {b.stand})" for b in liste)

    async def suchen(e: SuchenEingabe) -> str:
        ergebnis = await suche.suchen(e.frage, e.buecher, e.anzahl)
        if not ergebnis.treffer:
            return f"Nichts gefunden zu: {e.frage}"
        zeilen = [f"{len(ergebnis.treffer)} Treffer zu: {e.frage}" + (f" ({ergebnis.hinweis})" if ergebnis.hinweis else "")]
        for t in ergebnis.treffer:
            stelle = f" · Abschnitt {t.abschnitt}" if t.abschnitt else ""
            ausschnitt = _text(t.ausschnitt.replace("<em>", "").replace("</em>", ""))
            zeilen.append(f"- {t.titel}{stelle} [buch={t.buch} pfad={t.pfad}]" + (f"\n  {ausschnitt}" if ausschnitt else ""))
        return "\n".join(zeilen)

    async def lesen(e: LesenEingabe) -> str:
        try:
            a = await leser.lesen(e.buch, e.pfad)
        except (BuchFehlt, EintragFehlt) as f:
            return f"Nicht gefunden: {f}"
        text = _text(a.html) or a.einleitung
        gekuerzt = len(text) > LESEN_HOECHSTENS
        return (f"{a.titel} [buch={a.buch} pfad={a.pfad}]\n" + (f"Rubrik: {a.rubrik}\n" if a.rubrik else "")
                + text[:LESEN_HOECHSTENS] + ("\n[gekürzt]" if gekuerzt else ""))

    return [
        Werkzeug("nachschlag_buecher", "Listet die Bücher der Bibliothek (Lexika, Handbücher, Frage und Antwort, Anleitungen, "
                 "Übungen) mit Kennung, Art und Sprache. Zuerst rufen, um Bücher für die Suche zu wählen.", BuecherEingabe, buecher),
        Werkzeug("nachschlag_suchen", "Sucht in allen oder ausgewählten Büchern nach Begriff, Name oder Frage; liefert Treffer mit "
                 "Titel, Ausschnitt, Buch und Pfad. Danach mit nachschlag_lesen die Seite lesen.", SuchenEingabe, suchen),
        Werkzeug("nachschlag_lesen", "Liest eine Seite eines Buchs als Text (Titel, Rubrik, Inhalt), etwa einen Treffer der Suche. "
                 "Buch und Pfad in der Antwort taugen als Beleg.", LesenEingabe, lesen),
    ]
