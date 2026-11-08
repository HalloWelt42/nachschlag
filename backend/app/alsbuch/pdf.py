"""Satz als PDF (WIKI-45) mit WeasyPrint: dasselbe XHTML wie im EPUB, mit Druckstil (Seitengröße, Seitenzahlen,
Kopfzeile, Inhaltsverzeichnis mit Seitenzahlen, Silbentrennung). Bilder kommen nur aus dem Buch selbst: der Abruf kennt
allein die Bilder, die der Aufrufer mitgibt, nichts aus dem Netz oder von der Platte. "Zwei Seiten je A4" setzt A5 und
stellt je zwei Seiten nebeneinander auf ein Blatt A4 quer (pypdf).

WeasyPrint braucht Pango aus dem System (im Abbild über apt, am Mac aus Homebrew mit
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib). Fehlt es, sagt `verfuegbar()` warum; EPUB geht trotzdem."""

from __future__ import annotations

import io
import logging
from functools import cache

logger = logging.getLogger("nachschlag.alsbuch")

BASIS = "buch:///"


class PdfFehler(Exception):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


@cache
def verfuegbar() -> str:
    """Leer, wenn der Satz als PDF geht; sonst der Grund in Worten."""
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as f:
        logger.warning("PDF nicht möglich: %s", f)
        return "Für den Satz als PDF fehlen hier die Bibliotheken (Pango); EPUB geht"
    return ""


def pdf_bauen(html: str, bilder: dict[str, tuple[bytes, str]], zwei_je_a4: bool = False) -> tuple[bytes, int]:
    """Das PDF und die Zahl seiner Seiten (bei zwei je A4: Seiten A5). `bilder`: Pfad im Dokument -> (Daten, Art)."""
    if grund := verfuegbar():
        raise PdfFehler(grund)
    from weasyprint import HTML

    def abrufen(adresse: str, *_, **__) -> dict:
        name = adresse.removeprefix(BASIS)
        if name not in bilder:
            raise ValueError(f"nicht im Buch: {adresse}")
        daten, art = bilder[name]
        return {"string": daten, "mime_type": art}

    dokument = HTML(string=html, base_url=BASIS, url_fetcher=abrufen).render()
    seiten = len(dokument.pages)
    pdf = dokument.write_pdf()
    return (zwei_auf_eins(pdf) if zwei_je_a4 else pdf), seiten


def zwei_auf_eins(pdf: bytes) -> bytes:
    """Je zwei Seiten A5 nebeneinander auf einem Blatt A4 quer, in Lesereihenfolge."""
    from pypdf import PageObject, PdfReader, PdfWriter, Transformation

    leser = PdfReader(io.BytesIO(pdf))
    schreiber = PdfWriter()
    seiten = list(leser.pages)
    for i in range(0, len(seiten), 2):
        links = seiten[i]
        breite, hoehe = float(links.mediabox.width), float(links.mediabox.height)
        blatt = PageObject.create_blank_page(width=2 * breite, height=hoehe)
        blatt.merge_transformed_page(links, Transformation())
        if i + 1 < len(seiten):
            blatt.merge_transformed_page(seiten[i + 1], Transformation().translate(tx=breite, ty=0))
        schreiber.add_page(blatt)
    aus = io.BytesIO()
    schreiber.write(aus)
    return aus.getvalue()
