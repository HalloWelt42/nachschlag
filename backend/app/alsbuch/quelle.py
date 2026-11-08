"""Der Text eines Artikels als Quelle fürs Buch (WIKI-45): Blöcke in der Reihenfolge des Artikels (Überschriften,
Absätze, Punkte, Zitate, Tabellen, Code), jeder Textblock mit einer Nummer (darauf zeigen die Belege), die Bilder an
ihrer Stelle, dazu bereinigtes XHTML für den Text wie im Buch. Ans Modell geht der Text in Stücken, die an Überschriften
enden (`stuecke`). Reine Umformung ohne Ein- und Ausgabe."""

from __future__ import annotations

import re
from html import escape
from typing import Literal

from lxml import html as lhtml
from pydantic import BaseModel, Field

from ..modell.alsbuch import Bild

#: Klassen, deren Inhalt nicht zum Text gehört (Steckbrief kommt eigens, Beispiele und Fußzeilen gar nicht)
OHNE_KLASSEN = {"steckbrief", "beispiel", "beitrag-fuss", "schlagwoerter", "qa-stimmen", "signatur", "beleg"}
OHNE_TAGS = {"script", "style", "nav", "aside", "noscript", "button", "form", "input", "select", "textarea", "audio", "video"}
#: Auszeichnungen im Fließtext, die das Buch behält (ohne Attribute)
INLINE = {"b", "strong", "i", "em", "sub", "sup", "br", "code", "small", "s", "u", "mark", "q", "cite", "var", "kbd"}
TABELLE = {"table", "caption", "thead", "tbody", "tfoot", "tr", "th", "td"}
STECKBRIEF = INLINE | TABELLE | {"dl", "dt", "dd", "p", "ul", "ol", "li"}
#: so lang wird ein Stück fürs Modell höchstens (Zeichen des Originals); an Überschriften wird früher geteilt
STUECK_ZEICHEN = 10_000

Blockart = Literal["absatz", "punkt", "ueberschrift", "tabelle", "zitat", "code"]


class Quellblock(BaseModel):
    """Ein Block des Originals."""
    art: Blockart = Field(description="Art des Blocks")
    text: str = Field(description="Reiner Text")
    html: str = Field("", description="Bereinigtes XHTML des Inhalts (Text wie im Buch)")
    nr: int = Field(0, description="Nummer der Textblöcke (Beleg); 0 bei Überschriften, Tabellen und Code")
    ebene: int = Field(0, description="Bei Überschriften: 2 bis 4")
    liste: int = Field(0, description="Bei Punkten: Kennung der Liste")
    geordnet: bool = Field(False, description="Bei Punkten: nummerierte Liste")
    bilder: list[Bild] = Field(default_factory=list, description="Bilder, die nach diesem Block stehen")


class Quelltext(BaseModel):
    """Ein Artikel als Quelle: Titel, Sprache und Blöcke."""
    titel: str = Field(description="Titel")
    sprache: str = Field("de", description="Sprache des Texts (ISO 639-1)")
    bloecke: list[Quellblock] = Field(default_factory=list, description="Die Blöcke in ihrer Reihenfolge")

    @property
    def absaetze(self) -> list[Quellblock]:
        return [b for b in self.bloecke if b.nr]

    @property
    def zeichen(self) -> int:
        return sum(len(b.text) for b in self.absaetze)

    @property
    def bilder(self) -> list[Bild]:
        return [x for b in self.bloecke for x in b.bilder]


def _leer(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _klassen(el) -> set[str]:
    return set((el.get("class") or "").split())


def _weg(el) -> bool:
    return not isinstance(el.tag, str) or el.tag in OHNE_TAGS or bool(_klassen(el) & OHNE_KLASSEN)


def _text(el) -> str:
    """Reiner Text eines Elements ohne Belegmarken und Ausgelassenes."""
    teile: list[str] = []

    def gehen(e) -> None:
        if _weg(e):
            if e.tail:
                teile.append(e.tail)
            return
        if e.tag == "br":
            teile.append(" ")
        if e.text:
            teile.append(e.text)
        for kind in e:
            gehen(kind)
        if e.tail and e is not el:
            teile.append(e.tail)

    gehen(el)
    return _leer("".join(teile))


def xhtml(el, erlaubt: set[str]) -> str:
    """Inhalt eines Elements als bereinigtes XHTML: erlaubte Tags ohne Attribute (Zellen behalten colspan und rowspan),
    alles andere ausgepackt, Ausgelassenes entfernt, Text maskiert."""
    teile: list[str] = []

    def kinder(e) -> None:
        if e.text:
            teile.append(escape(e.text, quote=False))
        for k in e:
            if _weg(k):
                pass
            elif k.tag == "br" and "br" in erlaubt:
                teile.append("<br/>")
            elif k.tag in erlaubt:
                attr = "".join(f' {a}="{escape(k.get(a), quote=True)}"' for a in ("colspan", "rowspan")
                               if k.tag in ("td", "th") and (k.get(a) or "").isdigit())
                teile.append(f"<{k.tag}{attr}>")
                kinder(k)
                teile.append(f"</{k.tag}>")
            elif k.tag != "img":
                kinder(k)
            if k.tail:
                teile.append(escape(k.tail, quote=False))

    kinder(el)
    return re.sub(r"\s+", " ", "".join(teile)).strip()


def _bild(img, unterschrift: str = "") -> Bild | None:
    adresse = img.get("src") or ""
    if not adresse or adresse.startswith("data:"):
        return None
    return Bild(adresse=adresse, unterschrift=unterschrift or _leer(img.get("alt") or ""))


def lesen(titel: str, html: str, sprache: str = "de") -> Quelltext:
    """Ein Artikel (HTML, wie der Baustein ihn aufbereitet) als Blöcke mit Nummern."""
    q = Quelltext(titel=titel, sprache=sprache or "de")
    if not html.strip():
        return q
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    zaehler = {"nr": 0, "liste": 0}
    offen: list[Bild] = []                 # Bilder vor dem ersten Block

    def anfuegen(block: Quellblock) -> None:
        if block.art in ("absatz", "punkt", "zitat"):
            if not block.text:
                return
            zaehler["nr"] += 1
            block.nr = zaehler["nr"]
        q.bloecke.append(block)
        if offen and block.nr:
            block.bilder.extend(offen)
            offen.clear()

    def bild_anhaengen(b: Bild | None) -> None:
        if b is None:
            return
        if q.bloecke:
            q.bloecke[-1].bilder.append(b)
        else:
            offen.append(b)

    def gehen(el) -> None:
        for k in el:
            if _weg(k):
                continue
            tag = k.tag
            if tag in ("h2", "h3", "h4", "h5", "h6"):
                text = _text(k)
                if text:
                    anfuegen(Quellblock(art="ueberschrift", text=text, ebene=min(int(tag[1]), 4)))
            elif tag in ("p", "dd", "dt"):
                anfuegen(Quellblock(art="absatz", text=_text(k), html=xhtml(k, INLINE)))
                for img in k.iter("img"):
                    bild_anhaengen(_bild(img))
            elif tag == "blockquote":
                anfuegen(Quellblock(art="zitat", text=_text(k), html=xhtml(k, INLINE)))
            elif tag in ("ul", "ol"):
                zaehler["liste"] += 1
                galerie = next(k.iter("img"), None) is not None      # Galerie: Bilder mit Unterschrift, keine Punkte
                for li in k:
                    if not (isinstance(li.tag, str) and li.tag == "li") or _weg(li):
                        continue
                    if galerie:
                        if (img := next(li.iter("img"), None)) is not None:
                            bild_anhaengen(_bild(img, _text(li)))
                        continue
                    anfuegen(Quellblock(art="punkt", text=_text(li), html=xhtml(li, INLINE), liste=zaehler["liste"],
                                        geordnet=tag == "ol"))
            elif tag == "table":
                if _text(k):
                    q.bloecke.append(Quellblock(art="tabelle", text=_text(k), html=f"<table>{xhtml(k, TABELLE | INLINE)}</table>"))
            elif tag == "pre":
                q.bloecke.append(Quellblock(art="code", text=k.text_content(), html=escape(k.text_content(), quote=False)))
            elif tag == "figure":
                img = next(k.iter("img"), None)
                caption = next(k.iter("figcaption"), None)
                if img is not None:
                    bild_anhaengen(_bild(img, _text(caption) if caption is not None else ""))
            elif tag == "img":
                bild_anhaengen(_bild(k))
            else:
                gehen(k)                       # div, section, span ...: hinein

    gehen(wurzel)
    if offen and q.bloecke:
        q.bloecke[0].bilder[:0] = offen
    return q


def steckbrief(html: str) -> str:
    """Ein Steckbrief als bereinigtes XHTML (Tabellen und Wertlisten); leer, wenn nichts bleibt."""
    if not html.strip():
        return ""
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    for div in wurzel.iter("div"):
        div.tag = "p"                          # Gruppen eines Steckbriefs werden Absätze
    return xhtml(wurzel, STECKBRIEF)


def stuecke(q: Quelltext, hoechstens: int = STUECK_ZEICHEN) -> list[list[Quellblock]]:
    """Die Textblöcke (mit Überschriften) in Stücken fürs Modell: höchstens `hoechstens` Zeichen, an einer Überschrift
    geteilt, sobald das Stück die Hälfte erreicht hat. Ein einzelner sehr langer Absatz bleibt ganz."""
    stuecke: list[list[Quellblock]] = []
    jetzt: list[Quellblock] = []
    laenge = 0
    for b in q.bloecke:
        if b.art not in ("ueberschrift", "absatz", "punkt", "zitat"):
            continue
        teilen = jetzt and ((b.art == "ueberschrift" and laenge >= hoechstens // 2) or laenge + len(b.text) > hoechstens)
        if teilen and any(x.nr for x in jetzt):
            stuecke.append(jetzt)
            jetzt, laenge = [], 0
        jetzt.append(b)
        laenge += len(b.text)
    if any(x.nr for x in jetzt):
        stuecke.append(jetzt)
    return stuecke


def als_eingabe(bloecke: list[Quellblock]) -> str:
    """Blöcke so, wie das Modell sie liest: Überschriften mit ##, Textblöcke mit ihrer Nummer in eckigen Klammern."""
    zeilen = []
    for b in bloecke:
        if b.art == "ueberschrift":
            zeilen.append(f"{'#' * b.ebene} {b.text}")
        elif b.nr:
            zeilen.append(f"[{b.nr}] {'- ' if b.art == 'punkt' else ''}{b.text}")
    return "\n".join(zeilen)


def stelle_von(q: Quelltext, zitat: str) -> int:
    """Nummer des Textblocks, in dem eine markierte Stelle steht (über Leerraum hinweg); 0: nicht gefunden."""
    gesucht = _leer(zitat)
    if not gesucht:
        return 0
    for b in q.absaetze:
        if gesucht in b.text:
            return b.nr
    kurz = gesucht[:80]                       # lange Markierungen über Absätze hinweg: der Anfang zählt
    return next((b.nr for b in q.absaetze if kurz in b.text), 0)
