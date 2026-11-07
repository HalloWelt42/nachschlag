"""Der Katalog der Bücher (Atom-Feed, WIKI-57 und WIKI-62): je Buch die Datei der neuesten Fassung mit Größe, dem Verweis
auf ihre Ladedatei (meta4, darin Prüfsumme und Spiegel) und allem, was der Katalog über das Buch weiß. Nur reine
Funktionen, ohne Netz. Zugeordnet wird über den Dateinamen im Verweis zum Laden, der Stamm und Stand trägt
(`.../wikipedia/wikipedia_de_all_maxi_2026-10.zim.meta4`). Vorschaubilder fremder Seiten werden nicht übernommen."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from urllib.parse import urlparse

from ..modell.buecherlader import Angaben
from .verzeichnis import zerlegen

_ATOM = "{http://www.w3.org/2005/Atom}"
_META4 = "{urn:ietf:params:xml:ns:metalink}"
#: Sprachen im Namen der Dateien und im Katalog (ISO 639-3)
KATALOGSPRACHE = {"de": "deu", "en": "eng", "mul": "mul"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Katalogeintrag:
    ordner: str          # Bereich aus dem Pfad des Verweises (zim/<ordner>/<datei>)
    datei: str
    stamm: str
    sprache: str
    stand: str
    groesse: int
    ladedatei: str       # Adresse der meta4-Datei
    angaben: Angaben


def _zahl(text: str | None) -> int:
    t = (text or "").strip()
    return int(t) if t.isdigit() else 0


def _schlagworte(tags: str) -> tuple[list[str], str, dict[str, bool]]:
    """`wikipedia;_category:wikipedia;_pictures:yes;...` -> freie Schlagworte, Kategorie und die Ja/Nein-Angaben."""
    freie, kategorie, schalter = [], "", {}
    for teil in (t.strip() for t in tags.split(";")):
        if not teil:
            continue
        if teil.startswith("_"):
            schluessel, _, wert = teil[1:].partition(":")
            if schluessel == "category":
                kategorie = wert
            elif wert in ("yes", "no"):
                schalter[schluessel] = wert == "yes"
        elif teil not in freie:
            freie.append(teil)
    return [f for f in freie if f != kategorie], kategorie, schalter          # die Kategorie nicht noch als Schlagwort


def eintraege_aus(feed: str | bytes) -> list[Katalogeintrag]:
    """Die Bücher eines Katalogs; Einträge ohne Verweis auf eine ZIM-Datei fallen weg."""
    aus = []
    for e in ET.fromstring(feed).iter(f"{_ATOM}entry"):
        link = next((l for l in e.iter(f"{_ATOM}link") if l.get("type") == "application/x-zim"), None)
        if link is None:
            continue
        ladedatei = link.get("href", "")
        pfad = urlparse(ladedatei).path.removesuffix(".meta4").split("/")
        name = zerlegen(pfad[-1])
        if not name:
            continue
        freie, kategorie, schalter = _schlagworte(e.findtext(f"{_ATOM}tags") or "")
        angaben = Angaben(
            titel=(e.findtext(f"{_ATOM}title") or "").strip(), beschreibung=(e.findtext(f"{_ATOM}summary") or "").strip(),
            artikel=_zahl(e.findtext(f"{_ATOM}articleCount")), medien=_zahl(e.findtext(f"{_ATOM}mediaCount")),
            autor=(e.findtext(f"{_ATOM}author/{_ATOM}name") or "").strip(),
            herausgeber=(e.findtext(f"{_ATOM}publisher/{_ATOM}name") or "").strip(),
            kategorie=kategorie or (e.findtext(f"{_ATOM}category") or "").strip(), schlagworte=freie,
            bilder=schalter.get("pictures"), videos=schalter.get("videos"), volltext=schalter.get("ftindex"),
            datum=(e.findtext("{http://purl.org/dc/terms/}issued") or "")[:10])
        aus.append(Katalogeintrag(ordner=pfad[-2] if len(pfad) > 1 else "", datei=pfad[-1], stamm=name.stamm,
                                  sprache=name.sprache, stand=name.stand, groesse=_zahl(link.get("length")),
                                  ladedatei=ladedatei, angaben=angaben))
    return aus


@dataclass(frozen=True)
class Ladedatei:
    """Was eine meta4-Datei über eine ZIM-Datei sagt: Prüfsumme und Spiegel (nach Vorrang, mit Land)."""
    sha256: str
    spiegel: list[tuple[str, str]]       # (Adresse der Datei, Land)


def ladedatei_aus(xml: str | bytes) -> Ladedatei:
    wurzel = ET.fromstring(xml)
    soll = next((h.text or "" for h in wurzel.iter(f"{_META4}hash") if h.get("type") == "sha-256"), "").strip().lower()
    spiegel = sorted(((int(u.get("priority") or 999), (u.text or "").strip(), u.get("location") or "")
                      for u in wurzel.iter(f"{_META4}url") if (u.text or "").strip().endswith(".zim")))
    return Ladedatei(sha256=soll if _SHA256.match(soll) else "", spiegel=[(a, land) for _, a, land in spiegel])
