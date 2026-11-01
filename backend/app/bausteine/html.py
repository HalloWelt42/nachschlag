"""Gemeinsame Handgriffe am HTML für alle Bausteine: Verweise prüfen und umschreiben, Bilder auf den Medienweg legen,
Überschriften mit Ankern versehen, Text gerade setzen. Jeder Baustein entscheidet selbst, was er davon nutzt."""

from __future__ import annotations

import re
import unicodedata
from html import escape as html_maskieren
from urllib.parse import unquote, urljoin

from lxml import html as lhtml

from ..modell.artikel import Abschnitt, Verweiszahlen
from .basis import Wege

#: typografische Zeichen der Quelle, im Lesedesign gerade gesetzt (Nutzer: nur gerade Zeichen)
GERADE = str.maketrans({0x201E: '"', 0x201C: '"', 0x201D: '"', 0x201A: "'", 0x2018: "'", 0x2019: "'",
                        0x2013: "-", 0x2014: "-", 0x00AB: '"', 0x00BB: '"', 0x2039: "'", 0x203A: "'"})
#: sicher tote Ziele (Platzhalter von Archivierungsdiensten)
TOT = re.compile(r"\.invalid(/|$)", re.I)
ERLAUBTE_ATTRIBUTE = {"href", "src", "alt", "title", "id", "width", "height", "colspan", "rowspan", "class", "lang", "dir",
                      "data-geo", "data-buch", "data-pfad", "loading", "decoding"}
#: Klassen, die das Lesedesign kennt; alle Klassen der Quelle fallen weg
EIGENE_KLASSEN = {"wl", "ort", "hinweis", "steckbrief", "steckbrief-kopf", "steckbrief-unter", "steckbrief-bild",
                  "steckbrief-gruppe", "steckbrief-werte", "steckbrief-name", "klade", "linie-unten", "linie-links",
                  "rechts", "einleitung",
                  # Dokumentation (Entwurf doku-php.html): Signatur, Parameter, Änderungen, Beispiele, Siehe auch, Code
                  "signatur", "name", "typ", "var", "versionen", "parameterliste", "aenderungen", "beispiel", "bkopf", "bnotiz",
                  "ausgabe-titel", "ausgabe", "siehe", "c-kw", "c-tag", "c-fn", "c-var", "c-str", "c-num", "c-kom",
                  # Frage und Antwort (Entwurf frage-antwort.html)
                  "qa-beitrag", "qa-stimmen", "zahl", "was", "akz-marke", "antwort", "akzeptiert", "antworten-kopf",
                  "beitrag-fuss", "schlagwoerter", "kommentare", "kommentar-liste", "codeblock", "verwandt"}

VERSTECKT = re.compile(r"display\s*:\s*none", re.I)
LINIE = {"linie-unten": re.compile(r"border-bottom\s*:\s*[^;]*\d", re.I),
         "linie-links": re.compile(r"border-left\s*:\s*[^;]*\d", re.I)}
SCHWEBT_RECHTS = re.compile(r"float\s*:\s*right", re.I)
KURSIV = re.compile(r"font-style\s*:\s*italic", re.I)


def maskieren(text: str) -> str:
    """Text für HTML (spitze Klammern, Kaufmannsund, Anführungszeichen)."""
    return html_maskieren(text, quote=True)


def verschieben(quelle, ziel) -> None:
    """Inhalt eines Elements (Text und Kinder) ans Ende eines anderen hängen."""
    if quelle.text:
        if len(ziel):
            ziel[-1].tail = (ziel[-1].tail or "") + quelle.text
        else:
            ziel.text = (ziel.text or "") + quelle.text
    for kind in list(quelle):
        ziel.append(kind)


def datum(stand: str) -> str:
    """Datum der Quelle (2026-08-18) wie im Deutschen (18.08.2026)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", stand.strip())
    return f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else stand


def gerade(text: str) -> str:
    return text.translate(GERADE)


def text_von(el) -> str:
    return gerade(re.sub(r"\s+", " ", el.text_content()).strip())


def anker_aus(titel: str, vergeben: set[str]) -> str:
    roh = unicodedata.normalize("NFKD", titel)
    basis = re.sub(r"[^A-Za-z0-9]+", "-", "".join(z for z in roh if not unicodedata.combining(z))).strip("-").lower() or "abschnitt"
    anker, n = basis, 2
    while anker in vergeben:
        anker, n = f"{basis}-{n}", n + 1
    vergeben.add(anker)
    return anker


def ziel_im_buch(eintragspfad: str, href: str) -> str:
    """Pfad im Buch, auf den ein relativer Verweis einer Seite zeigt (ohne Anker)."""
    basis = "/" + eintragspfad
    return unquote(urljoin(basis, href.partition("#")[0]).lstrip("/"))


def ist_online(href: str) -> bool:
    return bool(re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I)) or href.startswith("//")


def online_verweise(elemente) -> list[str]:
    """Lebende Online-Verweise in den Elementen (etwa einem Abschnitt Weblinks, der nicht im Text bleibt)."""
    gefunden: list[str] = []
    for el in elemente:
        for a in el.iter("a"):
            href = (a.get("href") or "").strip()
            if href.startswith(("http:", "https:", "//")) and not TOT.search(href) and href not in gefunden:
                gefunden.append(href)
    return gefunden


def verweise_umschreiben(wurzel, buch: str, eintragspfad: str, wege: Wege) -> tuple[Verweiszahlen, list[str]]:
    """Interne Verweise prüfen und auf die Leseseite legen; ohne Ziel bleibt nur der Text. Koordinaten werden zum Ort.
    Online-Verweise kommen aus dem Text heraus und in eine Liste (für 'Über diesen Artikel')."""
    zahlen = Verweiszahlen()
    online: list[str] = []
    for a in list(wurzel.iter("a")):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        if href.startswith("geo:"):
            zahlen.koordinaten += 1
            a.tag = "span"
            a.attrib.clear()
            a.set("class", "ort")
            a.set("data-geo", href[4:].split("?")[0])
            continue
        if ist_online(href):
            zahlen.online += 1
            if not TOT.search(href) and href not in online:
                online.append(href)
            a.drop_tag()
            continue
        ziel = ziel_im_buch(eintragspfad, href)
        if not ziel or ziel.startswith(("_", "-/")):
            a.drop_tag()
            continue
        if wege.gibt_es(buch, ziel):
            zahlen.intern += 1
            anker = href.partition("#")[2]
            a.attrib.clear()
            a.set("href", wege.artikel(buch, ziel) + (f"#{anker}" if anker else ""))
            a.set("class", "wl")
        else:
            zahlen.ohne_ziel += 1
            a.drop_tag()
    return zahlen, online


def bilder_umschreiben(wurzel, buch: str, eintragspfad: str, wege: Wege) -> str:
    """Bilder auf den Medienweg legen (nie größer als die Datei); liefert das erste Bild des Inhalts."""
    erstes = ""
    for img in list(wurzel.iter("img")):
        src = img.get("src") or ""
        if not src or src.startswith(("data:", "http:", "https:", "//")):
            img.drop_tree()
            continue
        adresse = wege.medien(buch, ziel_im_buch(eintragspfad, src))
        for name in ("srcset", "sizes", "style", "data-src"):
            img.attrib.pop(name, None)
        img.set("src", adresse)
        img.set("loading", "lazy")
        if not erstes and int(img.get("width") or 0) >= 120:
            erstes = adresse
    return erstes


def ueberschriften(wurzel) -> list[Abschnitt]:
    """h2 bis h4 mit Anker (vorhandene id bleibt); daraus das Inhaltsverzeichnis."""
    vergeben: set[str] = {el.get("id") for el in wurzel.iter() if el.get("id")}
    abschnitte: list[Abschnitt] = []
    for h in wurzel.iter("h2", "h3", "h4"):
        titel = text_von(h)
        if not titel:
            continue
        anker = h.get("id") or anker_aus(titel, vergeben)
        h.set("id", anker)
        abschnitte.append(Abschnitt(anker=anker, titel=titel, ebene=int(h.tag[1])))
    return abschnitte


def stile_uebersetzen(wurzel) -> None:
    """Was die Quelle nur über Stilangaben ausdrückt und beim Säubern verloren ginge, vorher in Bedeutung übersetzen:
    Verstecktes (display: none, etwa Wartungsvermerke von Vorlagen) fällt weg; Linien an Tabellenzellen (so zeichnen
    Stammbäume ihre Äste) werden zu Klassen, die das Lesedesign nachzeichnet; rechts schwebende Kästen bleiben rechts."""
    for el in list(wurzel.iter()):
        if not isinstance(el.tag, str) or el.getparent() is None:
            continue
        stil = el.get("style") or ""
        if VERSTECKT.search(stil):
            el.drop_tree()
            continue
        zusatz = [k for k, muster in LINIE.items() if el.tag in ("td", "th") and muster.search(stil)]
        if el.tag == "span" and KURSIV.search(stil):
            el.tag = "i"                 # Kursiv nur als Stil (etwa fremdsprachige Titel) wird echtes Kursiv
        if el.tag in ("table", "div") and SCHWEBT_RECHTS.search(stil):
            zusatz.append("rechts")
        if zusatz:
            el.set("class", " ".join([*(el.get("class") or "").split(), *zusatz]))


def saeubern(wurzel) -> None:
    """Nur erlaubte Attribute, keine Skripte, Stile oder Formulare; Text gerade gesetzt."""
    for el in list(wurzel.iter("script", "style", "link", "meta", "noscript", "form", "input", "button", "iframe")):
        el.drop_tree()
    for el in wurzel.iter():
        if not isinstance(el.tag, str):
            continue
        for name in list(el.attrib):
            if name not in ERLAUBTE_ATTRIBUTE:
                del el.attrib[name]
        if "class" in el.attrib:
            eigene = [k for k in el.get("class", "").split() if k in EIGENE_KLASSEN]
            if eigene:
                el.set("class", " ".join(eigene))
            else:
                del el.attrib["class"]
        if el.text:
            el.text = gerade(el.text)
        if el.tail:
            el.tail = gerade(el.tail)
    leere_entfernen(wurzel)


#: Hüllen, die ohne Inhalt nichts zeigen (etwa ein Absatz oder Span, aus dem ein Ton-Knopf entfernt wurde)
HUELLEN = ("p", "span", "b", "i", "em", "strong", "small", "sup", "sub", "div", "figcaption")
#: Elemente, die auch ohne Text etwas zeigen
SICHTBAR = ("img", "math", "br", "hr", "table")


def leere_entfernen(wurzel) -> None:
    """Leere Hüllen weg (ihr folgender Text bleibt), dann Umbrüche am Ende einer Hülle; von innen nach außen, damit
    eine Hülle, die nur leere Hüllen trug, selbst leer wird."""
    for el in reversed(list(wurzel.iter(*HUELLEN))):
        if el is wurzel or el.getparent() is None:
            continue
        if not (el.text or "").strip() and not any(isinstance(k.tag, str) and (k.tag in SICHTBAR and k.tag != "br" or
                                                                              k.tag not in SICHTBAR) for k in el):
            el.drop_tag()                # Hülle weg, ihr Text (auch ein einzelnes Leerzeichen) und Folgetext bleiben
    for el in wurzel.iter(*HUELLEN):
        while len(el) and el[-1].tag == "br" and not (el[-1].tail or "").strip():
            el.remove(el[-1])


def als_html(el) -> str:
    return lhtml.tostring(el, encoding="unicode", method="html")
