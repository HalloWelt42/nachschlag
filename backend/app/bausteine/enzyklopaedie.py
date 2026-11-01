"""Baustein Enzyklopädie (Erzeuger mwoffliner): Bücher wie die freie Enzyklopädie, Wikibooks, Wikivoyage.

Aufbau der Quelle (gemessen an wikipedia_de_all_maxi_2026-01): Inhalt in `#mw-content-text`, Überschriften als
`div.mw-heading > h2#Anker`, Steckbrief als `table.infobox` oder `table.taxobox`, Bilder unter `./_assets_/`, Verweise auf
Artikel relativ (`Rotfuchs`), Weiterleitungen auf Abschnitte als kleine Seite mit Sprung. Belegabschnitte
(Einzelnachweise, Weblinks, Literatur ...) gehören nicht in den Lesetext; ihre Online-Verweise kommen in
'Über diesen Artikel'."""

from __future__ import annotations

from lxml import html as lhtml

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
       "ext-phonos-PhonosButton", "mw-tmh-player")
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
    """Belegabschnitte samt allem bis zur nächsten Überschrift derselben oder höheren Ebene; liefert die Abschnitte mit
    Weblinks (ihre Verweise gehören zu 'Über diesen Artikel')."""
    weblinks: list = []
    behaelter = inhalt.xpath(".//div[contains(@class,'mw-content-ltr')]") or [inhalt]
    for wurzel in behaelter:
        kinder = list(wurzel)
        i = 0
        while i < len(kinder):
            u = _ueberschrift(kinder[i])
            if u and u[0].lower() in BELEGE:
                ebene = u[1]
                j = i + 1
                while j < len(kinder) and not ((v := _ueberschrift(kinder[j])) and v[1] <= ebene):
                    j += 1
                for k in kinder[i:j]:
                    wurzel.remove(k)
                if u[0].lower() in WEBLINKS:
                    weblinks.extend(kinder[i + 1:j])
                kinder = list(wurzel)
                continue
            i += 1
    return weblinks


def _steckbrief(inhalt, titel: str) -> Steckbrief | None:
    """Infobox oder Taxobox neu gesetzt: Kopf, Bild, Gruppen und Werte."""
    tabelle = next(iter(inhalt.xpath(".//table[contains(@class,'infobox') or contains(@class,'taxobox')]")), None)
    if tabelle is None:
        return None
    kopf = titel
    teile: list[str] = []
    werte: list[str] = []

    def werte_schliessen() -> None:
        if werte:
            teile.append('<dl class="steckbrief-werte">' + "".join(werte) + "</dl>")
            werte.clear()

    for tr in tabelle.iter("tr"):
        zellen = [z for z in tr if z.tag in ("th", "td")]
        if not zellen:
            continue
        bild = next(iter(tr.iter("img")), None)
        if bild is not None and len(zellen) == 1:
            werte_schliessen()
            unter = h.text_von(zellen[0])
            teile.append(f'<figure class="steckbrief-bild"><img src="{bild.get("src")}" alt="{bild.get("alt") or ""}" '
                         f'width="{bild.get("width") or ""}" height="{bild.get("height") or ""}" loading="lazy">'
                         + (f"<figcaption>{unter}</figcaption>" if unter else "") + "</figure>")
            continue
        if len(zellen) == 1 and next(iter(zellen[0].iter("table")), None) is not None:
            continue                     # verschachtelte Tabelle: ihre Zeilen kommen einzeln
        if len(zellen) == 1:
            text = h.text_von(zellen[0])
            if not text:
                continue
            if not teile and not werte and kopf == titel:
                kopf = text
            elif not werte and teile and teile[-1].startswith(('<div class="steckbrief-gruppe">', '<p class="steckbrief-name">')):
                teile.append(f'<p class="steckbrief-name">{text}</p>')     # Zeile unter einer Gruppe: Wert ohne Namen
            else:
                werte_schliessen()
                teile.append(f'<div class="steckbrief-gruppe">{text}</div>')
            continue
        name, wert = zellen[0], zellen[-1]
        werte.append(f"<dt>{h.text_von(name).rstrip(':')}</dt><dd>{h.als_html(wert)[4:-5] if wert.tag == 'td' else h.text_von(wert)}</dd>")
    werte_schliessen()
    tabelle.drop_tree()
    if not teile:
        return None
    return Steckbrief(titel=kopf, html="".join(teile))


class Enzyklopaedie:
    kennung = "enzyklopaedie"
    arten = frozenset({"enzyklopaedie"})
    lesedesign = True

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        kopf = next(iter(doc.xpath("//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        inhalt = next(iter(doc.xpath("//*[@id='mw-content-text']")), None)
        if inhalt is None:
            inhalt = next(iter(doc.xpath("//body")), doc)
        for el in list(inhalt.iter()):
            if not isinstance(el.tag, str) or el.getparent() is None:
                continue
            if el.tag in WEG_TAGS or _klassen(el) & set(WEG) or any(k.startswith("ext-phonos") for k in _klassen(el)):
                el.drop_tree()
        weblinks = _belege_entfernen(inhalt)
        verweise, online = h.verweise_umschreiben(inhalt, buch.kennung, eintrag.pfad, wege)
        online += [v for v in h.online_verweise(weblinks) if v not in online]
        bild = h.bilder_umschreiben(inhalt, buch.kennung, eintrag.pfad, wege)
        steckbrief = _steckbrief(inhalt, titel)
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
