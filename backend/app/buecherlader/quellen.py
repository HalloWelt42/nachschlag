"""Quellen des Bücherladers (WIKI-62): jede Quelle sagt, welche Bücher sie in welcher Fassung hat, von wo sie zu laden
sind und was sie über sie weiß. Arten hinter einer Schnittstelle: Verzeichnis (Dateiliste eines Spiegels, Ordner je
Bereich) und Katalog (Bücher mit Angaben und Ladedatei). Aus allen Quellen entsteht eine Vereinigungsmenge: je Buch und
Stand ein Eintrag mit allen Bezugsquellen und den zusammengeführten Angaben.

Netz nur über den übergebenen Client; jede Quelle meldet ihren Fortschritt und was nicht ging, ohne den Durchgang
anzuhalten (eine Quelle, die nicht antwortet, fehlt eben in der Vereinigung)."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urljoin, urlparse

import httpx

from ..modell.buecherlader import Angaben
from .katalog import KATALOGSPRACHE, eintraege_aus
from .verzeichnis import dateien_aus, ordner_aus, zerlegen

Art = Literal["verzeichnis", "katalog", "ordner"]
Melden = Callable[[str], Awaitable[None]]
#: so viele Bereiche eines Spiegels zugleich (mehr nehmen manche übel: 429)
BEREICHE_GLEICHZEITIG = 2


@dataclass(frozen=True)
class Fund:
    """Eine Datei, wie eine Quelle sie kennt."""
    ordner: str
    datei: str
    stamm: str
    sprache: str
    stand: str
    groesse: int              # 0: unbekannt
    adresse: str              # von hier zu laden
    ladedatei: str = ""       # meta4 mit Prüfsumme und Spiegeln, wenn die Quelle sie nennt
    angaben: Angaben | None = None


@dataclass
class Ergebnis:
    funde: list[Fund] = field(default_factory=list)
    bereiche: int = 0
    hinweise: list[str] = field(default_factory=list)


class Quelle(Protocol):
    nr: int
    art: Art
    name: str

    async def durchsehen(self, c: httpx.AsyncClient, sprachen: frozenset[str], melden: Melden) -> Ergebnis: ...


#: Wartezeiten, wenn ein Spiegel um Geduld bittet (429, 503), bevor der Bereich als nicht lesbar gilt
GEDULD_S = (2.0, 5.0, 10.0)


async def _text(c: httpx.AsyncClient, adresse: str, geduld: tuple[float, ...] = GEDULD_S) -> str:
    """Eine Seite lesen; bittet der Server um Geduld (429, 503), so lange warten, wie er sagt (Retry-After), sonst
    nach der Liste, und erneut fragen."""
    for warten in (*geduld, None):
        antwort = await c.get(adresse)
        if antwort.status_code not in (429, 503) or warten is None:
            antwort.raise_for_status()
            return antwort.text
        sagt = antwort.headers.get("retry-after", "")
        await asyncio.sleep(min(float(sagt), 30.0) if sagt.isdigit() else warten)
    raise AssertionError("unerreichbar")


@dataclass
class Verzeichnisquelle:
    """Ein Spiegel mit lesbarem Verzeichnis: Ordner je Bereich, darin die Dateien aller Fassungen."""
    nr: int
    name: str
    adresse: str
    art: Art = "verzeichnis"

    async def durchsehen(self, c: httpx.AsyncClient, sprachen: frozenset[str], melden: Melden) -> Ergebnis:
        basis = self.adresse if self.adresse.endswith("/") else self.adresse + "/"
        bereiche = ordner_aus(await _text(c, basis))
        if not bereiche:
            raise ValueError("im Verzeichnis stehen keine Bereiche; stimmt die Adresse?")
        ergebnis, sperre, fertig = Ergebnis(bereiche=len(bereiche)), asyncio.Semaphore(BEREICHE_GLEICHZEITIG), 0

        async def bereich(name: str) -> None:
            nonlocal fertig
            async with sperre:
                try:
                    html = await _text(c, urljoin(basis, f"{name}/"))
                except httpx.HTTPError as f:
                    ergebnis.hinweise.append(f"{self.name}, Bereich {name}: {f}")
                    html = ""
            fertig += 1
            await melden(f"{self.name}: Bereich {fertig} von {len(bereiche)}")
            ergebnis.funde.extend(Fund(d.ordner, d.datei, d.stamm, d.sprache, d.stand, d.groesse,
                                       urljoin(basis, f"{d.ordner}/{d.datei}"))
                                  for d in dateien_aus(name, html) if d.sprache in sprachen)

        await asyncio.gather(*(bereich(b) for b in bereiche))
        return ergebnis


@dataclass
class Katalogquelle:
    """Ein Katalog der Bücher (Atom-Feed): je Buch die neueste Fassung mit Angaben und Ladedatei."""
    nr: int
    name: str
    adresse: str
    art: Art = "katalog"

    async def durchsehen(self, c: httpx.AsyncClient, sprachen: frozenset[str], melden: Melden) -> Ergebnis:
        ergebnis = Ergebnis()
        for sprache in sorted(sprachen):
            await melden(f"{self.name}: Sprache {sprache}")
            adresse = f"{self.adresse.rstrip('/')}/entries?lang={KATALOGSPRACHE.get(sprache, sprache)}&count=-1"
            try:
                eintraege = eintraege_aus((await c.get(adresse)).raise_for_status().content)
            except (httpx.HTTPError, ET.ParseError) as f:
                ergebnis.hinweise.append(f"{self.name} ({sprache}): {f}")
                continue
            ergebnis.funde.extend(Fund(e.ordner, e.datei, e.stamm, e.sprache, e.stand, e.groesse,
                                       e.ladedatei.removesuffix(".meta4"), e.ladedatei, e.angaben)
                                  for e in eintraege if e.sprache in sprachen)
        ergebnis.bereiche = len({f.ordner for f in ergebnis.funde})
        return ergebnis


#: Bezug aus einem Ordner auf dem Rechner der App: datei:<Pfad>
DATEI = "datei:"


@dataclass
class Ordnerquelle:
    """Eigene Bücher in einem Ordner auf dem Rechner der App (WIKI-87): Unterordner je Bereich, darin die ZIM-Dateien,
    je Datei die Prüfsumme daneben (<datei>.sha256). Ein anderes Programm legt neue Fassungen hinein (etwa das Buch der
    Dateiformate); der Bücherlader führt sie wie jedes andere Buch (Abo, Fassungen, Umschalten, Rückfall)."""
    nr: int
    name: str
    adresse: str
    art: Art = "ordner"

    async def durchsehen(self, c: httpx.AsyncClient, sprachen: frozenset[str], melden: Melden) -> Ergebnis:
        wurzel = Path(self.adresse)
        if not wurzel.is_dir():
            raise ValueError(f"Den Ordner {self.adresse} gibt es nicht")
        bereiche = sorted(p for p in wurzel.iterdir() if p.is_dir() and not p.name.startswith("."))
        ergebnis = Ergebnis(bereiche=len(bereiche))
        for bereich in bereiche:
            await melden(f"{self.name}: Bereich {bereich.name}")
            for datei in sorted(bereich.glob("*.zim")):
                name = zerlegen(datei.name)
                if name is None or name.sprache not in sprachen:
                    continue
                ergebnis.funde.append(Fund(bereich.name, datei.name, name.stamm, name.sprache, name.stand,
                                           datei.stat().st_size, f"{DATEI}{datei}"))
        return ergebnis


def quelle_aus(nr: int, art: Art, name: str, adresse: str) -> Quelle:
    klasse = {"katalog": Katalogquelle, "ordner": Ordnerquelle}.get(art, Verzeichnisquelle)
    return klasse(nr=nr, name=name, adresse=adresse)


def rechnername(adresse: str) -> str:
    if adresse.startswith(DATEI) or adresse.startswith("/"):
        return "eigener Ordner"
    return urlparse(adresse).hostname or adresse


# ----- Vereinigung ---------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Bezug:
    quelle: int
    adresse: str
    ladedatei: str = ""


@dataclass
class Vereint:
    """Ein Buch in einem Stand aus allen Quellen: wo es zu laden ist und was über es bekannt ist."""
    ordner: str
    datei: str
    stamm: str
    sprache: str
    stand: str
    groesse: int
    angaben: Angaben | None
    bezuege: list[Bezug]


def _zusammen(alt: Angaben | None, neu: Angaben | None) -> Angaben | None:
    """Angaben zusammenführen: was die erste Quelle (der Katalog zuerst) weiß, gilt; Lücken füllt die nächste."""
    if alt is None or neu is None:
        return alt or neu
    werte = alt.model_dump()
    for schluessel, wert in neu.model_dump().items():
        if werte[schluessel] in ("", 0, None, []):
            werte[schluessel] = wert
    return Angaben(**werte)


def vereinigen(ergebnisse: list[tuple[Quelle, Ergebnis]]) -> list[Vereint]:
    """Die Vereinigungsmenge: je (Stamm, Stand) ein Eintrag mit den Bezügen aller Quellen in ihrer Reihenfolge. Kataloge
    zuerst, damit ihre Angaben und ihr Bereich gelten; die Größe ist die größte bekannte (Verzeichnisse runden)."""
    vereint: dict[tuple[str, str], Vereint] = {}
    for quelle, ergebnis in sorted(ergebnisse, key=lambda qe: qe[0].art != "katalog"):
        for f in ergebnis.funde:
            v = vereint.get((f.stamm, f.stand))
            bezug = Bezug(quelle.nr, f.adresse, f.ladedatei)
            if v is None:
                vereint[(f.stamm, f.stand)] = Vereint(f.ordner, f.datei, f.stamm, f.sprache, f.stand, f.groesse, f.angaben,
                                                      [bezug])
                continue
            v.groesse = max(v.groesse, f.groesse)
            v.angaben = _zusammen(v.angaben, f.angaben)
            if all(b.quelle != quelle.nr for b in v.bezuege):
                v.bezuege.append(bezug)
    return list(vereint.values())
