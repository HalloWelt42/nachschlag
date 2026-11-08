"""Kategorien in Büchern, die sie mitbringen (mwoffliner ab 2.x, etwa das Klexikon; WIKI-75). Ein Artikel nennt seine
Kategorien in der Leiste `#mw-normal-catlinks` (versteckte Wartungskategorien stehen in einer eigenen Leiste und bleiben
draußen). Eine Kategorieseite (`mw-category-generated`) zeigt Unterkategorien (`#mw-subcategories`) und Seiten
(`#mw-pages`); hat sie mehr als eine Seite davon, liegen die übrigen als Teile im Buch
(`_categories_partials_<Kategorie>_<subcats|pages>_<n>`), die die Quelle per Skript nachlädt. Hier werden alle Teile
gelesen: die Kategorie zeigt alle ihre Seiten. Bücher ohne Kategorien (Wikipedia aus mwoffliner 1.x) haben weder Leiste
noch Kategorieseiten; dort bleibt alles wie zuvor."""

from __future__ import annotations

from lxml import html as lhtml

from ..bibliothek import Eintrag
from ..modell.artikel import Kategorieangaben, Kategorieverweis
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege

ERKENNUNG = b'class="mw-category-generated"'
#: so viele nachgeladene Teile liest eine Kategorie höchstens (je etwa 200 Einträge)
TEILE_HOECHSTENS = 500


def _verweise(wurzel, buch: Buch, pfad: str, wege: Wege, xpath: str) -> list[Kategorieverweis]:
    """Verweise auf Seiten im Buch (Ziel steht darin), in der Reihenfolge der Quelle, jede einmal."""
    aus: dict[str, Kategorieverweis] = {}
    for a in wurzel.xpath(xpath):
        ziel = h.ziel_im_buch(pfad, a.get("href") or "")
        if not ziel or ziel in aus or h.ist_online(a.get("href") or "") or not wege.gibt_es(buch.kennung, ziel):
            continue
        aus[ziel] = Kategorieverweis(pfad=ziel, titel=h.gerade(h.text_von(a)) or ziel)
    return list(aus.values())


def kategorien_der_seite(doc, buch: Buch, pfad: str, wege: Wege) -> list[Kategorieverweis]:
    """Die sichtbaren Kategorien einer Seite (Leiste am Ende), ohne Wartungskategorien."""
    return _verweise(doc, buch, pfad, wege, "//*[@id='mw-normal-catlinks']//a[@href]")


def _mitglieder(doc, buch: Buch, pfad: str, wege: Wege, abschnitt: str, teil: str) -> list[Kategorieverweis]:
    """Unterkategorien oder Seiten: aus den nachgeladenen Teilen, wenn das Buch welche hat, sonst von der Seite selbst."""
    aus: dict[str, Kategorieverweis] = {}
    for n in range(1, TEILE_HOECHSTENS + 1):
        roh = wege.datei(buch.kennung, f"_categories_partials_{pfad}_{teil}_{n}")
        if not roh:
            break
        stueck = lhtml.fragment_fromstring(roh.decode("utf-8", "replace"), create_parent="div")
        for v in _verweise(stueck, buch, pfad, wege, ".//*[contains(@class,'mw-category')]//li/a[@href]"):
            aus.setdefault(v.pfad, v)
    if not aus:
        for v in _verweise(doc, buch, pfad, wege, f"//*[@id='{abschnitt}']//*[contains(@class,'mw-category')]//li/a[@href]"):
            aus.setdefault(v.pfad, v)
    return list(aus.values())


class Kategorie:
    kennung = "kategorie"
    arten = frozenset({"enzyklopaedie"})
    darstellung = "kategorie"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and ERKENNUNG in eintrag.inhalt

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        pfad = eintrag.pfad
        kopf = next(iter(doc.xpath("//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        angaben = Kategorieangaben(ober=kategorien_der_seite(doc, buch, pfad, wege),
                                   unter=_mitglieder(doc, buch, pfad, wege, "mw-subcategories", "subcats"),
                                   seiten=_mitglieder(doc, buch, pfad, wege, "mw-pages", "pages"))
        # die Beschreibung der Kategorie: der Text vor den erzeugten Listen
        inhalt = next(iter(doc.xpath("//*[@id='mw-content-text']")), None)
        beschreibung = ""
        if inhalt is not None:
            for el in list(inhalt.xpath(".//*[contains(@class,'mw-category-generated')] | .//*[@id='catlinks'] "
                                        "| .//*[contains(@class,'zim-footer')]")):
                if el.getparent() is not None:
                    el.drop_tree()
            h.verweise_umschreiben(inhalt, buch.kennung, pfad, wege)
            h.bilder_umschreiben(inhalt, buch.kennung, pfad, wege)
            h.saeubern(inhalt)
            if h.text_von(inhalt).strip():
                beschreibung = "".join(h.als_html(k) for k in inhalt)
        name = titel.split(":", 1)[-1].strip() or titel
        return Aufbereitet(titel=name, html=beschreibung, einleitung=h.text_von(inhalt)[:400] if inhalt is not None else "",
                           rubrik=" · ".join(["Kategorie", *([f"{len(angaben.unter)} Unterkategorien"] if angaben.unter else []),
                                              *([f"{len(angaben.seiten)} Seiten"] if angaben.seiten else [])]),
                           kategorie=angaben, kategorien=angaben.ober)
