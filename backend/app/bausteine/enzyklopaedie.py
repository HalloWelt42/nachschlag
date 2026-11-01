"""Baustein Enzyklopädie (Erzeuger mwoffliner): Bücher wie die freie Enzyklopädie, Wikibooks, Wikivoyage.

Aufbau der Quelle (gemessen an wikipedia_de_all_maxi_2026-01): Inhalt in `#mw-content-text`, Überschriften als
`div.mw-heading > h2#Anker`, Steckbrief als `table.infobox` oder `table.taxobox`, Bilder unter `./_assets_/`, Verweise auf
Artikel relativ (`Rotfuchs`), Weiterleitungen auf Abschnitte als kleine Seite mit Sprung. Belegabschnitte
(Einzelnachweise, Weblinks, Literatur ...) gehören nicht in den Lesetext; ihre Online-Verweise kommen in
'Über diesen Artikel'."""

from __future__ import annotations

from lxml import html as lhtml
from lxml.etree import SubElement

from ..bibliothek import Eintrag
from ..modell.artikel import Steckbrief
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege

#: Überschriften der Belegabschnitte (Deutsch und Englisch), ganz aus dem Lesetext genommen
BELEGE = {"einzelnachweise", "weblinks", "literatur", "anmerkungen", "quellen", "fußnoten", "references", "external links",
          "further reading", "notes", "sources", "bibliography", "citations", "footnotes", "normdaten"}
#: davon die Abschnitte mit Verweisen ins Netz
WEBLINKS = {"weblinks", "external links"}
#: Bausteine der Quelle ohne Lesewert im eigenen Design
WEG = ("mw-editsection", "reference", "mw-references-wrap", "navbox", "navbox-styles", "metadata", "noprint",
       "sisterproject", "catlinks", "mw-authority-control", "toc", "mw-jump-link", "printfooter", "ext-phonos",
       "ext-phonos-PhonosButton", "mw-tmh-player",
       "hatnote")                        # Hinweiszeilen wie "... leitet hierher weiter" gehören zur Quelle, nicht zum Text
#: Medien, die nicht im Buch liegen (Ton und Film werden online abgespielt)
WEG_TAGS = ("audio", "video", "source", "track")


def _klassen(el) -> set[str]:
    return set((el.get("class") or "").split())


def _ueberschrift(el) -> tuple[str, int] | None:
    """(Text, Ebene), wenn das Element eine Überschrift ist (auch eingepackt in div.mw-heading)."""
    if el.tag in ("h2", "h3", "h4"):
        return h.text_von(el), int(el.tag[1])
    if el.tag == "div" and "mw-heading" in _klassen(el):
        inner = next((k for k in el if k.tag in ("h2", "h3", "h4")), None)
        if inner is not None:
            return h.text_von(inner), int(inner.tag[1])
    return None


def _belege_entfernen(inhalt) -> list:
    """Belegabschnitte aus dem Lesetext nehmen; liefert die Teile der Abschnitte mit Weblinks (ihre Verweise gehören
    zu 'Über diesen Artikel'). Zwei Aufbauten der Quelle: jeder Abschnitt in einem eigenen <section> mit der
    Überschrift vorn (heutige Seiten), oder Überschriften und Inhalt hintereinander in einem Behälter (dann gilt alles
    bis zur nächsten Überschrift derselben oder höheren Ebene)."""
    weblinks: list = []
    for kopf in list(inhalt.xpath(".//div[contains(@class,'mw-heading')] | .//h2 | .//h3 | .//h4")):
        behaelter = kopf.getparent()
        u = _ueberschrift(kopf)
        if behaelter is None or not u or u[0].lower() not in BELEGE or "mw-heading" in _klassen(behaelter):
            continue                     # eine Überschrift im Kopf eines Abschnitts zählt über den Kopf
        if behaelter.tag == "section" and len(behaelter) and behaelter[0] is kopf and behaelter.getparent() is not None:
            teile = list(behaelter)[1:]
            behaelter.getparent().remove(behaelter)
        else:
            kinder = list(behaelter)
            i = kinder.index(kopf)
            j = i + 1
            while j < len(kinder) and not ((v := _ueberschrift(kinder[j])) and v[1] <= u[1]):
                j += 1
            teile = kinder[i + 1:j]
            for k in kinder[i:j]:
                behaelter.remove(k)
        if u[0].lower() in WEBLINKS:
            weblinks.extend(teile)
    return weblinks


def _zelleninhalt(zelle, ziel) -> None:
    """Inhalt einer Zelle (Text und Elemente mit Auszeichnung) in `ziel` verschieben; Absätze lösen sich auf, ein
    Umbruch am Ende fällt weg."""
    if zelle.text:
        ziel.text = (ziel.text or "") + zelle.text
    for kind in list(zelle):
        ziel.append(kind)
    for absatz in list(ziel.iter("p", "div")):
        if absatz is not ziel:
            absatz.drop_tag()
    while len(ziel) and ziel[-1].tag == "br" and not (ziel[-1].tail or "").strip():
        ziel.remove(ziel[-1])


INFOKASTEN = ".//table[contains(@class,'infobox') or contains(@class,'taxobox')]"


def _steckbrief_aus(tabelle) -> tuple[str | None, object] | None:
    """Ein Infokasten (Infobox, Taxobox) neu gesetzt: Kopf, Unterzeile, Bild mit Unterschrift, Gruppen, Werte und
    Namen (Entwurf teile/artikel.html). Als Elementbaum gebaut: der Inhalt der Zellen wandert mit Auszeichnung und
    Verweisen, nie als Text zusammengesetzt. Liefert Kopf und Inhalt (noch ungesäubert) oder nichts, wenn nichts bleibt."""
    kopf: str | None = None
    wurzel = lhtml.Element("div")
    werte = None                         # die offene Liste von Namen und Werten (dl)

    def neu(tag: str, klasse: str = "", text: str = "", in_=None):
        el = SubElement(wurzel if in_ is None else in_, tag)
        if klasse:
            el.set("class", klasse)
        if text:
            el.text = text
        return el

    def letztes(klasse: str):
        return wurzel[-1] if len(wurzel) and wurzel[-1].get("class") == klasse else None

    unterschrift = tabelle.find("caption")
    if unterschrift is not None and h.text_von(unterschrift):
        kopf = h.text_von(unterschrift)
    for tr in tabelle.iter("tr"):
        zellen = [z for z in tr if z.tag in ("th", "td")]
        if not zellen:
            continue
        bild = next(iter(tr.iter("img")), None)
        if bild is not None and len(zellen) == 1:
            werte = None
            figur = neu("figure", "steckbrief-bild")
            img = neu("img", in_=figur)
            for name in ("src", "alt", "width", "height"):
                img.set(name, bild.get(name) or "")
            img.set("loading", "lazy")
            halter = bild
            while halter.getparent() is not zellen[0]:
                halter = halter.getparent()
            zellen[0].remove(halter)     # das Bild selbst; der Rest der Zelle ist die Unterschrift
            unter = neu("figcaption", in_=figur)
            _zelleninhalt(zellen[0], unter)
            if not h.text_von(unter):
                figur.remove(unter)
            continue
        if len(zellen) == 1 and next(iter(zellen[0].iter("table")), None) is not None:
            continue                     # verschachtelte Tabelle: ihre Zeilen kommen einzeln
        if len(zellen) == 1:
            text = h.text_von(zellen[0])
            if not text:
                continue
            if kopf is None:
                kopf = text
            elif not len(wurzel) or letztes("steckbrief-unter") is not None:
                neu("p", "steckbrief-unter", text)          # Zeile direkt unter dem Kopf (etwa Zeitraum)
            elif werte is None and (name := letztes("steckbrief-name")) is not None:
                neu("br", in_=name)                         # weitere Zeile eines Namens (etwa Autor und Jahr)
                _zelleninhalt(zellen[0], neu("span", in_=name))
            elif werte is None and letztes("steckbrief-gruppe") is not None:
                _zelleninhalt(zellen[0], neu("p", "steckbrief-name"))   # Zeile unter einer Gruppe: Wert ohne Namen
            else:
                werte = None
                neu("div", "steckbrief-gruppe", text)
            continue
        name, wert = zellen[0], zellen[-1]
        if werte is None:
            werte = neu("dl", "steckbrief-werte")
        neu("dt", text=h.text_von(name).rstrip(":"), in_=werte)
        _zelleninhalt(wert, neu("dd", in_=werte))
    return (kopf, wurzel) if len(wurzel) else None


def _steckbriefe(inhalt, titel: str) -> Steckbrief | None:
    """Der erste Infokasten wird der Steckbrief des Artikels (neben dem Text); jeder weitere (etwa die Organisation zu
    einem Vertrag) wird an seiner Stelle gleich gesetzt und schwebt dort rechts im Text. Gesäubert wie der Artikel:
    Attribute und Klassen der Quelle fallen weg, Text kommt maskiert."""
    tabellen = inhalt.xpath(INFOKASTEN)
    steckbrief: Steckbrief | None = None
    for tabelle in tabellen:
        if any(a in tabellen for a in tabelle.iterancestors()) or tabelle.getparent() is None:
            continue                     # Kasten im Kasten: gehört zum äußeren
        gebaut = _steckbrief_aus(tabelle)
        if gebaut is None:
            tabelle.drop_tree()
            continue
        kopf, wurzel = gebaut
        if steckbrief is None:
            h.saeubern(wurzel)
            steckbrief = Steckbrief(titel=kopf or titel, html="".join(h.als_html(k) for k in wurzel))
            tabelle.drop_tree()
            continue
        kasten = lhtml.Element("aside")
        kasten.set("class", "steckbrief")
        if kopf:
            SubElement(kasten, "div").set("class", "steckbrief-kopf")
            kasten[0].text = kopf
        kasten.extend(list(wurzel))
        kasten.tail = tabelle.tail
        tabelle.getparent().replace(tabelle, kasten)
    return steckbrief


class Enzyklopaedie:
    kennung = "enzyklopaedie"
    arten = frozenset({"enzyklopaedie"})
    darstellung = "lesedesign"

    def passt(self, eintrag: Eintrag) -> bool:
        """Nur Artikel (mit `#mw-content-text`); die Startseite des Buchs ist eine eigene Kachelseite."""
        return eintrag.mime.startswith("text/html") and b'id="mw-content-text"' in eintrag.inhalt

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        kopf = next(iter(doc.xpath("//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        inhalt = next(iter(doc.xpath("//*[@id='mw-content-text']")), None)
        if inhalt is None:
            inhalt = next(iter(doc.xpath("//body")), doc)
        h.stile_uebersetzen(inhalt)      # vor allem anderen: Verstecktes darf nicht in Steckbrief oder Einleitung
        for el in list(inhalt.iter()):
            if not isinstance(el.tag, str) or el.getparent() is None:
                continue
            if el.tag in WEG_TAGS or _klassen(el) & set(WEG) or any(k.startswith("ext-phonos") for k in _klassen(el)):
                el.drop_tree()
        weblinks = _belege_entfernen(inhalt)
        verweise, online = h.verweise_umschreiben(inhalt, buch.kennung, eintrag.pfad, wege)
        online += [v for v in h.online_verweise(weblinks) if v not in online]
        bild = h.bilder_umschreiben(inhalt, buch.kennung, eintrag.pfad, wege)
        steckbrief = _steckbriefe(inhalt, titel)
        for div in list(inhalt.xpath(".//div[contains(@class,'mw-heading')]")):
            div.drop_tag()
        abschnitte = h.ueberschriften(inhalt)
        einleitung: list[str] = []
        for el in inhalt.iter("p", "h2"):
            if el.tag == "h2":
                break
            text = h.text_von(el)
            if len(text) > 40:
                einleitung.append(text)
        h.saeubern(inhalt)
        if steckbrief:
            steckbrief.html = h.gerade(steckbrief.html)
        rumpf = "".join(h.als_html(k) for k in inhalt)
        return Aufbereitet(titel=titel, html=rumpf, einleitung=" ".join(einleitung)[:1200], abschnitte=abschnitte,
                           steckbrief=steckbrief, bild=bild, verweise=verweise, online=online)
