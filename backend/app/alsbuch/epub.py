"""EPUB 3 packen (WIKI-45): ein ZIP mit `mimetype` zuerst und ungepackt, `META-INF/container.xml`, dem Paket
(`OEBPS/paket.opf` mit Angaben, Liste aller Dateien und Lesereihenfolge), der Navigation (`nav.xhtml`, dazu `toc.ncx`
für ältere Lesegeräte), dem Stil, den Seiten und den Bildern. Ohne Abhängigkeit; reine Umformung."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone

from .darstellung import Navpunkt, Seite, dokument, e, inhalt_html

#: Bildarten, die ein EPUB tragen darf (Kernarten nach EPUB 3.3)
BILDARTEN = {"image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/svg+xml": "svg", "image/webp": "webp"}


@dataclass
class Epubbild:
    datei: str               # Pfad im Paket, etwa bilder/b3.jpg
    art: str                 # Medienart
    daten: bytes


@dataclass
class Epubangaben:
    titel: str
    untertitel: str
    kennung: str             # dauerhafte Kennung des Buchs (urn:uuid:...)
    sprache: str = "de"
    beschreibung: str = ""
    titelbild: str = ""      # Datei des Titelbilds unter den Bildern; leer: keins


CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/paket.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>"""


def _ncx(angaben: Epubangaben, nav: list[Navpunkt]) -> str:
    zaehler = [0]

    def punkte(liste: list[Navpunkt]) -> str:
        aus = []
        for p in liste:
            zaehler[0] += 1
            n = zaehler[0]
            aus.append(f'<navPoint id="n{n}" playOrder="{n}"><navLabel><text>{e(p.titel)}</text></navLabel>'
                       f'<content src="{e(p.ziel)}"/>{punkte(p.unter)}</navPoint>')
        return "".join(aus)

    karte = punkte(nav)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f'<head><meta name="dtb:uid" content="{e(angaben.kennung)}"/></head>'
            f"<docTitle><text>{e(angaben.titel)}</text></docTitle><navMap>{karte}</navMap></ncx>")


def _opf(angaben: Epubangaben, seiten: list[Seite], bilder: list[Epubbild], inhalt_im_buch: bool, geaendert: datetime) -> str:
    eintraege = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                 '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
                 '<item id="stil" href="stil.css" media-type="text/css"/>']
    eintraege += [f'<item id="s{i}" href="{e(s.datei)}" media-type="application/xhtml+xml"/>' for i, s in enumerate(seiten)]
    for i, b in enumerate(bilder):
        merkmal = ' properties="cover-image"' if b.datei == angaben.titelbild else ""
        kennung = "titelbild" if merkmal else f"b{i}"
        eintraege.append(f'<item id="{kennung}" href="{e(b.datei)}" media-type="{b.art}"{merkmal}/>')
    reihe = [f'<itemref idref="s{i}"/>' for i, _ in enumerate(seiten)]
    if inhalt_im_buch:
        titel = next((i for i, s in enumerate(seiten) if s.datei == "titel.xhtml"), -1)
        reihe.insert(titel + 1, '<itemref idref="nav"/>')
    angaben_xml = [f'<dc:identifier id="kennung">{e(angaben.kennung)}</dc:identifier>',
                   f"<dc:title>{e(angaben.titel)}</dc:title>", f"<dc:language>{e(angaben.sprache)}</dc:language>",
                   "<dc:creator>Nachschlag</dc:creator>",
                   f'<meta property="dcterms:modified">{geaendert.strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>']
    if angaben.untertitel:
        angaben_xml.append(f"<dc:description>{e(angaben.untertitel)}{('. ' + e(angaben.beschreibung)) if angaben.beschreibung else ''}</dc:description>")
    if angaben.titelbild:
        angaben_xml.append('<meta name="cover" content="titelbild"/>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="kennung" xml:lang="de">'
            f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">{"".join(angaben_xml)}</metadata>'
            f'<manifest>{"".join(eintraege)}</manifest><spine toc="ncx">{"".join(reihe)}</spine></package>')


def epub_bauen(angaben: Epubangaben, seiten: list[Seite], nav: list[Navpunkt], stil: str, bilder: list[Epubbild],
               inhalt_im_buch: bool, geaendert: datetime | None = None) -> bytes:
    """Das EPUB als Bytes. `inhalt_im_buch`: das Inhaltsverzeichnis steht als Seite hinter der Titelseite."""
    geaendert = geaendert or datetime.now(timezone.utc)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)

        def schreiben(name: str, inhalt: str | bytes) -> None:
            z.writestr(name, inhalt, compress_type=zipfile.ZIP_DEFLATED)

        schreiben("META-INF/container.xml", CONTAINER)
        schreiben("OEBPS/paket.opf", _opf(angaben, seiten, bilder, inhalt_im_buch, geaendert))
        schreiben("OEBPS/nav.xhtml", dokument("Inhalt", inhalt_html(nav, epub=True), stil_datei="stil.css", epub=True))
        schreiben("OEBPS/toc.ncx", _ncx(angaben, nav))
        schreiben("OEBPS/stil.css", stil)
        for s in seiten:
            schreiben(f"OEBPS/{s.datei}", dokument(s.titel, s.inhalt, stil_datei="stil.css", epub=True))
        for b in bilder:
            schreiben(f"OEBPS/{b.datei}", b.daten)
    return puffer.getvalue()
