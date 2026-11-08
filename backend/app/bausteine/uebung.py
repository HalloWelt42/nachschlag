"""Bausteine der Inhaltsart Übungen (freeCodeCamp, fcc2zim; WIKI-66). Das Buch ist eine Skript-Anwendung: jede Aufgabe
hat eine kleine HTML-Seite `index/<kurs>/<block>/<kennung>.html`, die nur auf ihre Route in der Anwendung springt
(`index.html#kurs/block/kennung`). Der Inhalt liegt als Markdown in `content/curriculum/<kurs>/<block>/<kennung>.md`
mit festen Abschnitten (`# --description--`, `# --instructions--`, `# --hints--`, `# --seed--`, `# --solutions--`),
die Gliederung in `content/curriculum/index.json`, deutsche Titel und Einleitungen in `content/locales/intro.json`.

- Uebung: die Seite einer Aufgabe; liest ihr Markdown und zeigt Beschreibung, Anleitung, Prüfpunkte mit Tests,
  Startcode und Lösung, dazu die Nachbarn im Block.
- Uebungsstart: die Startseite (`index.html`); zeigt alle Kurse mit Blöcken und Aufgaben."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from lxml import html as lhtml
from markdown_it import MarkdownIt

from ..bibliothek import Eintrag
from ..modell.buch import Buch
from ..modell.uebung import Aufgabenverweis, Block, Code, Hinweis, Kurs, Kursangaben, Uebungsangaben
from . import html as h
from .basis import Aufbereitet, Wege

AUFGABE = re.compile(r"^index/([^/]+)/([^/]+)/([^/]+)\.html$")
GLIEDERUNG = "content/curriculum/index.json"
EINFUEHRUNG = "content/locales/intro.json"
ABSCHNITT = re.compile(r"^# --([\w-]+)--[ \t]*$", re.M)
UNTERABSCHNITT = re.compile(r"^## --([\w-]+)--[ \t]*$", re.M)
CODEBLOCK = re.compile(r"^```([\w+-]*)[^\n]*\n(.*?)^```[ \t]*$", re.M | re.S)
KOPF = re.compile(r"\A---\n.*?\n---\n", re.S)

_md = MarkdownIt("commonmark", {"html": True})


def pfad_der_aufgabe(kurs: str, block: str, kennung: str) -> str:
    return f"index/{kurs}/{block}/{kennung}.html"


def _json(wege: Wege, buch: Buch, pfad: str) -> dict:
    roh = wege.datei(buch.kennung, pfad)
    try:
        return json.loads(roh) if roh else {}
    except ValueError:
        return {}


def _text(roh: str) -> str:
    """Einleitungen der Quelle sind Text, gelegentlich mit Auszeichnung: nur der Text, gerade gesetzt."""
    return h.gerade(lhtml.fragment_fromstring(roh, create_parent="div").text_content().strip()) if roh else ""


def _html(markdown: str, buch: Buch, pfad: str, wege: Wege) -> str:
    """Markdown als gesäubertes HTML (Verweise und Bilder wie überall auf die Wege der App umgeschrieben)."""
    if not markdown.strip():
        return ""
    wurzel = lhtml.fragment_fromstring(_md.render(markdown), create_parent="div")
    h.verweise_umschreiben(wurzel, buch.kennung, pfad, wege)
    h.bilder_umschreiben(wurzel, buch.kennung, pfad, wege)
    h.saeubern(wurzel)
    return "".join(h.als_html(k) for k in wurzel) if len(wurzel) else ""


def abschnitte(markdown: str) -> dict[str, str]:
    """Die Abschnitte `# --name--` einer Aufgabe (ohne den Kopf mit den Angaben)."""
    text = KOPF.sub("", markdown, count=1)
    teile = ABSCHNITT.split(text)
    return {teile[i]: teile[i + 1].strip("\n") for i in range(1, len(teile) - 1, 2)}


def codebloecke(text: str) -> list[Code]:
    return [Code(sprache=m.group(1) or "", code=m.group(2).rstrip("\n")) for m in CODEBLOCK.finditer(text)]


def hinweise(text: str, buch: Buch, pfad: str, wege: Wege) -> list[Hinweis]:
    """Prüfpunkte: je ein Text, gefolgt vom Codeblock seines Tests."""
    aus, rest = [], 0
    for m in CODEBLOCK.finditer(text):
        vorher = text[rest:m.start()].strip()
        if vorher:
            aus.append(Hinweis(html=_html(vorher, buch, pfad, wege), test=m.group(2).rstrip("\n")))
        elif aus and not aus[-1].test:
            aus[-1].test = m.group(2).rstrip("\n")
        rest = m.end()
    if (nachher := text[rest:].strip()):
        aus.append(Hinweis(html=_html(nachher, buch, pfad, wege)))
    return aus


def startcode(text: str) -> list[Code]:
    """Der Startcode: die Blöcke unter `## --seed-contents--` (Code davor und danach läuft nur im Test)."""
    teile = UNTERABSCHNITT.split(text)
    inhalt = next((teile[i + 1] for i in range(1, len(teile) - 1, 2) if teile[i] == "seed-contents"), text if len(teile) == 1 else "")
    return codebloecke(inhalt)


@lru_cache(maxsize=32)
def _gliederung_zwischen(kennung: str, roh_gliederung: bytes, roh_einfuehrung: bytes) -> Kursangaben:
    try:
        gliederung = json.loads(roh_gliederung) if roh_gliederung else {}
        einfuehrung = json.loads(roh_einfuehrung) if roh_einfuehrung else {}
    except ValueError:
        return Kursangaben()
    kurse = []
    for kurs, bloecke in gliederung.items():
        intro = einfuehrung.get(kurs, {})
        blocktexte = intro.get("blocks", {})
        kurse.append(Kurs(
            kennung=kurs, titel=_text(intro.get("title", "")) or kurs.replace("-", " "),
            einleitung=[t for t in (_text(x) for x in intro.get("intro", [])) if t],
            bloecke=[Block(kennung=b, titel=_text(blocktexte.get(b, {}).get("title", "")) or b.replace("-", " "),
                           einleitung=[t for t in (_text(x) for x in blocktexte.get(b, {}).get("intro", [])) if t],
                           aufgaben=[Aufgabenverweis(pfad=pfad_der_aufgabe(kurs, b, a["slug"]), titel=h.gerade(a["title"]))
                                     for a in aufgaben if a.get("slug")])
                     for b, aufgaben in bloecke.items()]))
    return Kursangaben(kurse=kurse)


def gliederung(buch: Buch, wege: Wege) -> Kursangaben:
    """Kurse, Blöcke und Aufgaben des Buchs, mit deutschen Titeln; je Buch und Fassung einmal gelesen."""
    return _gliederung_zwischen(buch.kennung, wege.datei(buch.kennung, GLIEDERUNG) or b"",
                                wege.datei(buch.kennung, EINFUEHRUNG) or b"")


def _lesetext(titel: str, u: Uebungsangaben) -> str:
    """Für Volltext und Vorlesen: Titel, Beschreibung, Anleitung, Prüfpunkte (ohne Code)."""
    teile = [f"<h1>{h.maskieren(titel)}</h1>", u.beschreibung, u.anleitung,
             *(f"<p>{h.maskieren(lhtml.fragment_fromstring(x.html, create_parent='div').text_content())}</p>" for x in u.hinweise if x.html)]
    return "".join(t for t in teile if t)


class Uebung:
    kennung = "uebung"
    arten = frozenset({"uebung"})
    darstellung = "uebung"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and AUFGABE.match(eintrag.pfad) is not None

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        kurs, block, kennung = AUFGABE.match(eintrag.pfad).groups()
        roh = wege.datei(buch.kennung, f"content/curriculum/{kurs}/{block}/{kennung}.md")
        teile = abschnitte(roh.decode("utf-8", "replace")) if roh else {}
        k = next((x for x in gliederung(buch, wege).kurse if x.kennung == kurs), None)
        b = next((x for x in (k.bloecke if k else []) if x.kennung == block), None)
        liste = b.aufgaben if b else []
        stelle = next((i for i, a in enumerate(liste) if a.pfad == eintrag.pfad), -1)
        pfad = eintrag.pfad
        titel = (liste[stelle].titel if stelle >= 0 else "") or eintrag.titel
        angaben = Uebungsangaben(
            kurs=kurs, kurs_titel=k.titel if k else kurs, block=block, block_titel=b.titel if b else block,
            nr=stelle + 1, anzahl=len(liste),
            beschreibung=_html(teile.get("description", ""), buch, pfad, wege),
            anleitung=_html(teile.get("instructions", ""), buch, pfad, wege),
            hinweise=hinweise(teile.get("hints", ""), buch, pfad, wege),
            startcode=startcode(teile.get("seed", "")), loesungen=codebloecke(teile.get("solutions", "")),
            vorige=liste[stelle - 1] if stelle > 0 else None,
            naechste=liste[stelle + 1] if 0 <= stelle < len(liste) - 1 else None)
        einleitung = lhtml.fragment_fromstring(angaben.beschreibung, create_parent="div").text_content().strip()[:400] \
            if angaben.beschreibung else ""
        return Aufbereitet(titel=titel, html=_lesetext(titel, angaben), einleitung=einleitung,
                           rubrik=f"{angaben.kurs_titel} · {angaben.block_titel}", uebung=angaben)


class Uebungsstart:
    kennung = "uebungsstart"
    arten = frozenset({"uebung"})
    darstellung = "uebungen"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and eintrag.pfad == "index.html"

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        kurse = gliederung(buch, wege)
        zahl = sum(len(b.aufgaben) for k in kurse.kurse for b in k.bloecke)
        einleitung = next((t for k in kurse.kurse for t in k.einleitung), "") or buch.beschreibung
        return Aufbereitet(titel=buch.titel, einleitung=einleitung,
                           html="".join(f"<h2>{h.maskieren(k.titel)}</h2>" + "".join(f"<p>{h.maskieren(t)}</p>" for t in k.einleitung)
                                        for k in kurse.kurse),
                           rubrik=f"{zahl} Aufgaben", kurse=kurse)
