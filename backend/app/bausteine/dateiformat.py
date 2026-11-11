"""Baustein Dateiformat: das Buch der Dateiformate (Erzeuger "dateiformate", eigenes Repo, WIKI-87).

Die Seiten sind schon sauber gebaut: eine Formatseite trägt ihre Angaben als JSON (`script#dateiformat`), den Steckbrief
als Tabelle (`table.steckbrief`, je Zeile `data-feld`) und je Quelle einen Abschnitt (`section.quelle`) mit Herkunft;
weitere Fassungen derselben Quelle (englisches Original) und Umwandlungen stehen aufklappbar (`details`). Kategorie-,
Endungs- und Startseiten sind Listen. Der Baustein setzt daraus Steckbrief, Lesedesign und Inhaltsverzeichnis; die
Startseite wird eine Übersicht der Kategorien in Gruppen."""

from __future__ import annotations

import json

from lxml import html as lhtml
from lxml.etree import SubElement

from ..bibliothek import Eintrag
from ..modell.artikel import Gruppe, Kategorieangaben, Kategorieverweis, Nachbar, Steckbrief
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege

KENNZEICHEN_START = b'class="start"'
KENNZEICHEN_KATEGORIE = b'<article class="kategorie"'


def _kategorien_der_formatseite(doc) -> list[Kategorieverweis]:
    """Die Kategorien eines Formats aus seinen Angaben (JSON); ein Format kann in mehreren stehen."""
    block = next(iter(doc.xpath("//script[@id='dateiformat']")), None)
    if block is None or not block.text:
        return []
    try:
        daten = json.loads(block.text)
    except ValueError:
        return []
    return [Kategorieverweis(pfad=k["pfad"], titel=k["name"].get("de") or k["kennung"]) for k in daten.get("kategorien", [])]


def _verweise(doc, pfad: str, buch: Buch, wege: Wege, xpath: str) -> list[Kategorieverweis]:
    aus = []
    for a in doc.xpath(xpath):
        anzahl = None
        for zahl in a.findall("small"):
            anzahl = int(h.text_von(zahl)) if h.text_von(zahl).isdigit() else None
            zahl.drop_tree()
        ziel = h.ziel_im_buch(pfad, a.get("href") or "")
        if ziel and wege.gibt_es(buch.kennung, ziel):
            aus.append(Kategorieverweis(pfad=ziel, titel=h.text_von(a), anzahl=anzahl))
    return aus


def _steckbrief(tabelle, titel: str) -> Steckbrief:
    """Zeilen der Tabelle als Namen und Werte (wie der Steckbrief der Enzyklopädie)."""
    wurzel = lhtml.Element("div")
    werte = SubElement(wurzel, "dl")
    werte.set("class", "steckbrief-werte")
    for tr in tabelle.iter("tr"):
        name, wert = tr.find("th"), tr.find("td")
        if name is None or wert is None:
            continue
        SubElement(werte, "dt").text = h.text_von(name)
        dd = SubElement(werte, "dd")
        h.verschieben(wert, dd)
    h.saeubern(wurzel)
    return Steckbrief(titel=titel, html="".join(h.als_html(k) for k in wurzel))


def _inhaltsverzeichnis(inhalt) -> list:
    """Abschnitte ohne die Überschriften in aufklappbaren Fassungen (die stehen sonst doppelt im Inhalt)."""
    kopie = lhtml.fromstring(h.als_html(inhalt))
    for d in list(kopie.iter("details")):
        d.drop_tree()
    return h.ueberschriften(kopie)


class Dateiformat:
    kennung = "dateiformat"
    arten = frozenset({"dateiformat"})
    darstellung = "lesedesign"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and b"<article" in eintrag.inhalt[:8192]

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        if KENNZEICHEN_START in eintrag.inhalt[:8192]:
            return self._start(buch, eintrag, doc, wege)
        if KENNZEICHEN_KATEGORIE in eintrag.inhalt:
            return self._kategorie(buch, eintrag, doc, wege)
        kategorien = _kategorien_der_formatseite(doc)
        artikel = next(iter(doc.xpath("//article")), doc)
        kopf = next(iter(artikel.xpath(".//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        if kopf is not None:
            kopf.drop_tree()
        tabelle = next(iter(artikel.xpath(".//table[contains(@class,'steckbrief')]")), None)
        kurz = next(iter(artikel.xpath(".//header/p[contains(@class,'kurz')]")), None)
        einleitung = h.text_von(kurz) if kurz is not None else ""
        verweise, online = h.verweise_umschreiben(artikel, buch.kennung, eintrag.pfad, wege)
        steckbrief = _steckbrief(tabelle, titel) if tabelle is not None else None
        if tabelle is not None:
            tabelle.drop_tree()
        for header in artikel.xpath(".//header"):
            header.drop_tag()
        if kurz is not None:
            kurz.set("class", "einleitung")
        bild = h.bilder_umschreiben(artikel, buch.kennung, eintrag.pfad, wege)
        for herkunft in artikel.xpath(".//p[contains(@class,'herkunft')]"):
            herkunft.set("class", "hinweis")
        abschnitte = _inhaltsverzeichnis(artikel)
        h.ueberschriften(artikel)                       # Anker auch in den Fassungen (Sprünge aus dem Text)
        h.saeubern(artikel)
        if not einleitung:
            erster = next((p for p in artikel.iter("p") if len(h.text_von(p)) > 40), None)
            einleitung = h.text_von(erster) if erster is not None else ""
        rumpf = "".join(h.als_html(k) for k in artikel)
        return Aufbereitet(titel=titel, html=rumpf, einleitung=einleitung[:1200], abschnitte=abschnitte,
                           steckbrief=steckbrief, bild=bild, verweise=verweise, online=online, kategorien=kategorien)

    def _kategorie(self, buch: Buch, eintrag: Eintrag, doc, wege: Wege) -> Aufbereitet:
        """Kategorieseite in der Kategorie-Ansicht von Nachschlag: Oberkategorie, Unterkategorien (bei großen
        Kategorien die Seiten je Anfangsbuchstabe), Formate und die Beschreibung der Kategorie."""
        kopf = next(iter(doc.xpath("//article//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        p = eintrag.pfad
        angaben = Kategorieangaben(ober=_verweise(doc, p, buch, wege, "//article/p[contains(@class,'pfad')]//a"),
                                   unter=_verweise(doc, p, buch, wege, "//article/ul[contains(@class,'kacheln')]//a"),
                                   seiten=_verweise(doc, p, buch, wege, "//article/ul[contains(@class,'formate')]//a"))
        angaben.seiten_gesamt = len(angaben.seiten)
        beschreibung = next(iter(doc.xpath("//article/section[contains(@class,'quelle')]")), None)
        html_text, einleitung = "", ""
        if beschreibung is not None:
            for herkunft in beschreibung.xpath(".//p[contains(@class,'herkunft')]"):
                herkunft.set("class", "hinweis")
            h.verweise_umschreiben(beschreibung, buch.kennung, p, wege)
            h.saeubern(beschreibung)
            html_text, einleitung = "".join(h.als_html(k) for k in beschreibung), h.text_von(beschreibung)[:400]
        kurz = next(iter(doc.xpath("//article/p[contains(@class,'kurz')]")), None)
        if kurz is not None and not einleitung:
            einleitung = h.text_von(kurz)
        teile = [*([f"{len(angaben.unter)} Unterseiten"] if angaben.unter else []),
                 *([f"{len(angaben.seiten)} Formate"] if angaben.seiten else [])]
        return Aufbereitet(titel=titel, html=html_text, einleitung=einleitung, rubrik=" · ".join(["Kategorie", *teile]),
                           kategorie=angaben, kategorien=angaben.ober, darstellung="kategorie")

    def _start(self, buch: Buch, eintrag: Eintrag, doc, wege: Wege) -> Aufbereitet:
        """Startseite: je Obergruppe die Kategorien als Rubrik (wie die Übersicht eines Handbuchs)."""
        gruppen: list[Gruppe] = []
        for sektion in doc.xpath("//section[contains(@class,'gruppe')]"):
            kopf = next(iter(sektion.iter("h2")), None)
            eintraege = []
            for a in sektion.xpath(".//ul//a"):
                for zahl in a.findall("small"):        # Anzahl der Formate steht nur in der Originalansicht
                    zahl.drop_tree()
                ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
                if ziel and wege.gibt_es(buch.kennung, ziel):
                    eintraege.append(Nachbar(pfad=ziel, titel=h.text_von(a)))
            if eintraege:
                gruppen.append(Gruppe(titel=h.text_von(kopf) if kopf is not None else "", eintraege=eintraege))
        kurz = next(iter(doc.xpath("//p[contains(@class,'kurz')]")), None)
        return Aufbereitet(titel=buch.titel, gruppen=gruppen, darstellung="uebersicht", einleitung=h.text_von(kurz) if kurz is not None else "")
