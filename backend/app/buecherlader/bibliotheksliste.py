"""Die Liste der Bücher für einen Bücherserver neben Nachschlag (`library.xml`), wahlweise: der Bedeutungsdienst liest
die Bücher über so einen Server. Der Bücherlader trägt ein Buch ein, sobald es in der Bibliothek liegt, und trägt es
aus, wenn er die Datei entfernt; andere Einträge bleiben unberührt. Geschrieben wird erst in eine Nachbardatei, dann
getauscht, damit der Server nie eine halbe Liste liest."""

from __future__ import annotations

import base64
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from libzim.reader import Archive

#: Angaben der Datei und ihr Name in der Liste
_ANGABEN = (("Title", "title"), ("Description", "description"), ("Language", "language"), ("Creator", "creator"),
            ("Publisher", "publisher"), ("Name", "name"), ("Flavour", "flavour"), ("Tags", "tags"), ("Date", "date"))


def _angabe(a: Archive, schluessel: str) -> str:
    try:
        return bytes(a.get_metadata(schluessel)).decode("utf-8", "replace").strip()
    except (KeyError, RuntimeError):
        return ""


def eintrag_aus(datei: Path) -> dict[str, str]:
    """Die Merkmale eines Buchs in der Liste, aus den Angaben der Datei."""
    a = Archive(str(datei))
    merkmale = {"id": str(a.uuid), "path": datei.name}
    merkmale |= {name: wert for schluessel, name in _ANGABEN if (wert := _angabe(a, schluessel))}
    merkmale |= {"articleCount": str(a.article_count), "mediaCount": str(a.media_count),
                 "size": str(datei.stat().st_size // 1024)}
    if a.has_illustration(48):
        merkmale["faviconMimeType"] = "image/png"
        merkmale["favicon"] = base64.b64encode(bytes(a.get_illustration_item(48).content)).decode("ascii")
    return merkmale


class Bibliotheksliste:
    def __init__(self, pfad: Path) -> None:
        self.pfad = pfad

    def _lesen(self) -> ET.Element:
        if self.pfad.is_file():
            return ET.parse(self.pfad).getroot()
        return ET.Element("library", version="20110515")

    def _schreiben(self, wurzel: ET.Element) -> None:
        ET.indent(wurzel)
        neu = self.pfad.with_name(self.pfad.name + ".neu")
        ET.ElementTree(wurzel).write(neu, encoding="utf-8", xml_declaration=False)
        os.replace(neu, self.pfad)

    def eintragen(self, datei: Path) -> None:
        """Ein Buch eintragen; steht die Datei schon drin, wird ihr Eintrag erneuert."""
        wurzel = self._lesen()
        for alt in [b for b in wurzel.findall("book") if b.get("path") == datei.name]:
            wurzel.remove(alt)
        ET.SubElement(wurzel, "book", eintrag_aus(datei))
        self._schreiben(wurzel)

    def austragen(self, dateiname: str) -> None:
        wurzel = self._lesen()
        weg = [b for b in wurzel.findall("book") if b.get("path") == dateiname]
        for b in weg:
            wurzel.remove(b)
        if weg:
            self._schreiben(wurzel)
