"""Baustein Dokumentation: Handbücher wie das von PHP, neu gesetzt im Grunddesign der Artikelansicht (Entwurf
doku-php.html). Zwei Verpackungen desselben DocBook-HTML: devdocs2zim (`div._page`, Gliederung in `navbar.json`) und
der Spiegel von php.net (warc2zim/zimit, `#layout-content`, Nachbarn in `.layout-menu`, Rubrik in den Brotkrumen,
Nutzernotizen in `#usernotes`). Jede Seite
einer Funktion hat feste Teile (`div.refsect1.description`, `.parameters`, `.returnvalues`, `.changelog`, `.examples`,
`.seealso`), dazu Signatur (`pre.methodsynopsis`), Fassungen (`p.verinfo`) und Zweck (`p.refpurpose`). Die Gliederung
des Buchs steht in `navbar.json` (Rubriken mit ihren Einträgen): daraus Rubrik und Nachbarn einer Seite und die
Startseite des Buchs als Übersicht der Rubriken.

Die Teile benennt Nachschlag selbst (das ist die Gliederung, keine Übersetzung des Inhalts); der Text der Quelle bleibt,
bis der Übersetzer ihn übersetzt. Code wird eingefärbt wie im Editor der Codeschmiede."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from lxml import html as lhtml
from lxml.etree import SubElement

from ..bibliothek import Eintrag
from ..modell.artikel import Gruppe, Nachbar, Steckbrief
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege
from .code import code_text, einfaerben

GLIEDERUNG = "navbar.json"
#: Nachbarn einer Seite in ihrer Rubrik: so viele davor und danach (Entwurf zeigt die Umgebung, nicht die ganze Rubrik)
NACHBARN_UM = 3

#: Teile einer Seite (Klasse des refsect1) und wie Nachschlag sie nennt
TEILE = {"description": "Beschreibung", "parameters": "Parameter", "returnvalues": "Rückgabewerte",
         "changelog": "Änderungen", "examples": "Beispiele", "seealso": "Siehe auch", "notes": "Hinweise",
         "errors": "Fehler und Ausnahmen", "unicode": "Unicode", "constructorsynopsis": "Konstruktor"}
#: feste Überschriften anderer Seitenarten (Klassen, Erweiterungen) und wie Nachschlag sie nennt
UEBERSCHRIFTEN = {"introduction": "Einführung", "class synopsis": "Klassenübersicht", "predefined constants":
                  "Vordefinierte Konstanten", "table of contents": "Inhalt", "changelog": "Änderungen", "examples": "Beispiele",
                  "see also": "Siehe auch", "notes": "Hinweise", "parameters": "Parameter", "return values": "Rückgabewerte",
                  "description": "Beschreibung", "errors/exceptions": "Fehler und Ausnahmen", "properties": "Eigenschaften",
                  "installing/configuring": "Installation und Einrichtung", "requirements": "Voraussetzungen",
                  "installation": "Installation", "runtime configuration": "Einstellungen zur Laufzeit",
                  "resource types": "Ressourcen"}
#: einleitende Sätze vor einer Ausgabe ("The above example will output:"); die Ausgabe trägt ihren eigenen Titel
VOR_AUSGABE = re.compile(r"(will output|outputs?|output of the above|would output|have:|produces?|displays?|"
                         r"result(s)? (is|in)|prints?)[^.]*:?\s*$", re.I)
SIGNATUR_TEIL = re.compile(r"(?P<var>&?\.{0,3}\$\w+)|(?P<wort>[?\\\w|]+)(?P<aufruf>\()?|(?P<sonst>[^\w$?\\|]+)")


@dataclass(frozen=True)
class Gliederung:
    rubriken: list[Gruppe]
    rubrik_von: dict[str, int]           # Pfad -> Nummer der Rubrik


def _gliederung(daten: bytes | None) -> Gliederung:
    rubriken: list[Gruppe] = []
    rubrik_von: dict[str, int] = {}
    if daten:
        for knoten in json.loads(daten).get("children", []):
            gesehen: set[str] = set()       # manche Rubriken nennen dieselbe Seite mehrfach (Sprachreferenz)
            eintraege = [Nachbar(pfad=k["href"], titel=k.get("name") or k["href"]) for k in knoten.get("children", [])
                         if k.get("href") and not (k["href"] in gesehen or gesehen.add(k["href"]))]
            if not eintraege:
                continue
            for e in eintraege:
                rubrik_von.setdefault(e.pfad, len(rubriken))
            rubriken.append(Gruppe(titel=knoten.get("name", ""), eintraege=eintraege))
    return Gliederung(rubriken, rubrik_von)


def _signatur(text: str, klasse: str = "signatur"):
    """Signatur als Kasten mit Name, Typen und Variablen (Entwurf: .signatur .name/.typ/.var)."""
    kasten = lhtml.Element("div")
    kasten.set("class", klasse)
    letztes = None

    def anhaengen(t: str, k: str | None) -> None:
        nonlocal letztes
        if not k:
            if letztes is None:
                kasten.text = (kasten.text or "") + t
            else:
                letztes.tail = (letztes.tail or "") + t
            return
        letztes = SubElement(kasten, "span")
        letztes.set("class", k)
        letztes.text = t

    name_gesetzt = False
    for m in SIGNATUR_TEIL.finditer(" ".join(text.split())):
        if m.group("var"):
            anhaengen(m.group("var"), "var")
        elif m.group("wort"):
            ist_name = bool(m.group("aufruf")) and not name_gesetzt
            name_gesetzt |= ist_name
            anhaengen(m.group("wort"), "name" if ist_name else "typ")
            if m.group("aufruf"):
                anhaengen("(", None)
        else:
            anhaengen(m.group("sonst"), None)
    return kasten


def _typen_aus(signatur: str) -> dict[str, str]:
    """Parameter und ihr Typ aus der Signatur: {"callback": "?callable", "arrays": "array"}."""
    innen = signatur[signatur.find("(") + 1:signatur.rfind(")")]
    return {m.group(2): m.group(1) for m in re.finditer(r"([?\\\w|]+)\s+&?(?:\.\.\.)?\$(\w+)", innen)}


def _ersetzen(alt, neu) -> None:
    neu.tail = alt.tail
    alt.getparent().replace(alt, neu)


#: Teile eines Beispiels in Reihenfolge: Code (pre oder php.net-gefärbt in div.phpcode), Ausgabe (pre), Sätze dazwischen
BLOECKE = (".//pre[not(ancestor::*[contains(@class,'phpcode')])] | .//div[contains(@class,'phpcode')] | "
           ".//p[not(ancestor::pre) and not(ancestor::*[contains(@class,'phpcode')])]")


def _ist_php(el) -> bool:
    return "phpcode" in (el.get("class") or "") or el.get("data-language") == "php"


def _beispiel(div) -> None:
    """Beispiel der Quelle (div.example) als Kasten: Kopf, eingefärbter Code, Ausgabe mit eigenem Titel."""
    kasten = lhtml.Element("div")
    kasten.set("class", "beispiel")
    titel = next(iter(div.xpath("./p[strong]|./div[contains(@class,'example-title')]")), None)
    if titel is not None:
        kopf = SubElement(kasten, "h3")   # Überschrift: so stehen die Beispiele im Inhalt (Entwurf)
        kopf.set("class", "bkopf")
        kopf.text = re.sub(r"^Example\s*#(\d+)\s*", r"Beispiel \1: ", h.text_von(titel))
        titel.getparent().remove(titel)
    bloecke = div.xpath(BLOECKE)
    for i, el in enumerate(bloecke):
        if el.tag == "p":
            folgt_ausgabe = i + 1 < len(bloecke) and not _ist_php(bloecke[i + 1])
            if folgt_ausgabe and VOR_AUSGABE.search(h.text_von(el)):
                continue
            absatz = SubElement(kasten, "p")
            absatz.set("class", "bnotiz")
            h.verschieben(el, absatz)
            continue
        code = code_text(el).strip("\n")
        if _ist_php(el):
            kasten.append(einfaerben(code, "php"))
        else:
            titel_a = SubElement(kasten, "div")
            titel_a.set("class", "ausgabe-titel")
            titel_a.text = "Ausgabe"
            aus = SubElement(kasten, "pre")
            aus.set("class", "ausgabe")
            aus.text = code
    _ersetzen(div, kasten)


def _code_bloecke(inhalt) -> None:
    """Code außerhalb von Beispielen (Sprachreferenz): eingefärbt im Kasten ohne Kopf."""
    for pre in list(inhalt.xpath(".//pre[not(ancestor::*[contains(@class,'phpcode')])] | .//div[contains(@class,'phpcode')]")):
        if pre.getparent() is None:
            continue
        if any(a.get("class") == "beispiel" for a in pre.iterancestors()):
            continue
        code = code_text(pre).strip("\n")
        kasten = lhtml.Element("div")
        kasten.set("class", "beispiel")
        if _ist_php(pre):
            kasten.append(einfaerben(code, "php"))
        else:
            aus = SubElement(kasten, "pre")
            aus.set("class", "ausgabe")
            aus.text = code
        halter = pre
        while halter.getparent() is not None and halter.getparent().tag == "div" and len(halter.getparent()) == 1 \
                and not (halter.getparent().text or "").strip() and halter.getparent() is not inhalt:
            halter = halter.getparent()      # leere Hüllen um den Code (div.example-contents, div.cdata) mit ersetzen
        _ersetzen(halter, kasten)


def _siehe(div) -> None:
    """Siehe auch: Verweis mit Name in Code und Erklärung daneben (Entwurf .siehe)."""
    liste = lhtml.Element("div")
    liste.set("class", "siehe")
    for li in div.iter("li"):
        a = next(iter(li.iter("a")), None)
        if a is None:
            continue
        rest = h.text_von(li)[len(h.text_von(a)):].lstrip(" -").strip()
        neu = SubElement(liste, "a")
        neu.set("href", a.get("href") or "")
        code = SubElement(neu, "code")
        code.text = h.text_von(a)
        if rest:
            SubElement(neu, "span").text = rest
    for alt in list(div):
        if alt.tag not in ("h2", "h3"):
            div.remove(alt)
    div.append(liste)


def _parameter(div, typen: dict[str, str]) -> None:
    """Parameter als Liste aus Name mit Typ und Erklärung (Entwurf .parameter; eigener Name, weil die Quelle ihre
    Parameternamen selbst code.parameter nennt)."""
    for dl in div.iter("dl"):
        dl.set("class", "parameterliste")
        for dt in dl.findall("dt"):
            name = h.text_von(dt).lstrip("$")
            for k in list(dt):
                dt.remove(k)
            dt.text = f"${name}"
            if typen.get(name):
                SubElement(dt, "span").set("class", "typ")
                dt[-1].text = typen[name]


#: Teile der Seite von php.net, die nicht zum Handbuch gehören (Sprachwahl, Melden, Notizen der Nutzer)
SPIEGEL_WEG = (".//*[contains(@class,'page-tools')] | .//*[@id='usernotes'] | .//*[contains(@class,'edit-bug')] | "
               ".//*[contains(@class,'contribute')] | .//form")
NULLBREITE = chr(0x200B)                 # php.net bricht lange Namen mit Leerzeichen der Breite null


def _spiegel_umgebung(doc, seite, pfad: str) -> tuple[str, str, list[Nachbar], int]:
    """Rubrik (letzte Brotkrume) mit ihrer Seite, Nachbarn (Seitenleiste) und Zahl der Nutzernotizen; danach fällt
    alles weg, was nicht zum Handbuch gehört."""
    krumen = doc.xpath("//*[@id='breadcrumbs']//ul/li/a")
    rubrik = h.text_von(krumen[-1]) if krumen else ""
    rubrik_pfad = h.ziel_im_buch(pfad, krumen[-1].get("href") or "") if krumen else ""
    umgebung = [Nachbar(pfad=h.ziel_im_buch(pfad, a.get("href") or ""), titel=h.text_von(a).replace(NULLBREITE, ""))
                for a in doc.xpath("//aside[contains(@class,'layout-menu')]//ul[contains(@class,'child-menu-list')]//a")
                if a.get("href")]
    notizen = len(seite.xpath(".//*[@id='usernotes']//div[contains(@class,'note') and @id]"))
    for el in seite.xpath(SPIEGEL_WEG):
        if el.getparent() is not None:
            el.drop_tree()
    return rubrik, rubrik_pfad, umgebung, notizen


def _spiegel_inhaltsverzeichnis(seite, pfad: str) -> list[Gruppe]:
    """Das Inhaltsverzeichnis einer Seite ohne eigenen Text (Startseite des Handbuchs: ul.chunklist mit Kapiteln und
    ihren Seiten) als Rubriken; einzelne Seiten ohne Unterseiten (Copyright, Preface) bilden eine eigene Rubrik vorn.
    Hat die Seite eigenen Inhalt (Funktion, Kapiteltext), keine."""
    liste = next(iter(seite.xpath(".//ul[contains(@class,'chunklist_set') and not(contains(@class,'chunklist_children'))]")), None)
    if liste is None or seite.xpath(".//*[contains(@class,'refentry')]") or any(
            len(h.text_von(p)) > 80 for p in seite.iter("p")):
        return []
    einzeln: list[Nachbar] = []
    rubriken: list[Gruppe] = []
    for li in liste.findall("li"):
        a = li.find("a")
        if a is None:
            continue
        eigene = Nachbar(pfad=h.ziel_im_buch(pfad, a.get("href") or ""), titel=h.text_von(a))
        kinder = [Nachbar(pfad=h.ziel_im_buch(pfad, k.get("href") or ""), titel=h.text_von(k))
                  for k in li.xpath("./ul/li/a")]
        if kinder:
            rubriken.append(Gruppe(titel=eigene.titel, eintraege=[Nachbar(pfad=eigene.pfad, titel="Überblick"), *kinder]))
        else:
            einzeln.append(eigene)
    return ([Gruppe(titel="Allgemein", eintraege=einzeln)] if einzeln else []) + rubriken


def _fenster(eintraege: list[Nachbar], pfad: str) -> list[Nachbar]:
    """Die Umgebung einer Seite in ihrer Rubrik: NACHBARN_UM Seiten davor und danach."""
    if not eintraege:
        return []
    i = next((n for n, e in enumerate(eintraege) if e.pfad == pfad), 0)
    von = max(0, min(i - NACHBARN_UM, len(eintraege) - 2 * NACHBARN_UM - 1))
    return eintraege[von:von + 2 * NACHBARN_UM + 1]


class Dokumentation:
    kennung = "dokumentation"
    arten = frozenset({"dokumentation"})        # auch Spiegel von Handbüchern (Art nach ihrer Quelle, Bibliothek)
    darstellung = "lesedesign"

    def __init__(self) -> None:
        self._gliederungen: dict[tuple[str, str], Gliederung] = {}

    def passt(self, eintrag: Eintrag) -> bool:
        if not eintrag.mime.startswith("text/html"):
            return False
        return b'class="_page' in eintrag.inhalt or (b'id="layout-content"' in eintrag.inhalt
                                                    and (b"layout-menu" in eintrag.inhalt or b"chunklist" in eintrag.inhalt))

    def _gliederung(self, buch: Buch, wege: Wege) -> Gliederung:
        schluessel = (buch.kennung, buch.stand)
        if schluessel not in self._gliederungen:
            self._gliederungen[schluessel] = _gliederung(wege.datei(buch.kennung, GLIEDERUNG))
        return self._gliederungen[schluessel]

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        seite = next(iter(doc.xpath("//div[contains(@class,'_page')]")), None)
        notizen = 0
        if seite is not None:                                       # devdocs: Gliederung aus navbar.json
            gliederung = self._gliederung(buch, wege)
            for el in seite.xpath(".//div[contains(@class,'_attribution')]"):
                el.drop_tree()
            if eintrag.pfad == "index" or not seite.xpath(".//p|.//pre|.//table"):
                # Startseite des Buchs (in der Quelle leer): Übersicht der Rubriken
                return Aufbereitet(titel=buch.titel, gruppen=gliederung.rubriken, darstellung="uebersicht")
            nr = gliederung.rubrik_von.get(eintrag.pfad)
            rubrik_titel = gliederung.rubriken[nr].titel if nr is not None else ""
            umgebung = gliederung.rubriken[nr].eintraege if nr is not None else []
            rubrik_pfad = ""                                        # devdocs: die Rubrik hat keine eigene Seite
        else:                                                       # Spiegel von php.net: Gliederung aus der Seite
            seite = next(iter(doc.xpath("//*[@id='layout-content']")), None)
            if seite is None:
                return Aufbereitet(titel=eintrag.titel)
            rubriken = _spiegel_inhaltsverzeichnis(seite, eintrag.pfad)
            if rubriken:                                            # Inhaltsverzeichnis des Handbuchs (Startseite)
                return Aufbereitet(titel=buch.titel, gruppen=rubriken, darstellung="uebersicht")
            rubrik_titel, rubrik_pfad, umgebung, notizen = _spiegel_umgebung(doc, seite, eintrag.pfad)

        kopf = next(iter(seite.xpath(".//h1|.//h2")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        if kopf is not None:
            kopf.drop_tree()
        code_titel = bool(seite.xpath(".//*[contains(@class,'refentry')]")) or titel.endswith("()")

        # Fassungen und Zweck (Kopf einer Funktionsseite)
        fassungen: list[str] = []
        for p in seite.xpath(".//p[contains(@class,'verinfo')]"):
            fassungen = [f.strip() for f in h.text_von(p).strip("()").split(",") if f.strip()]
            p.drop_tree()
        zweck = ""
        for p in seite.xpath(".//p[contains(@class,'refpurpose')]"):
            ziel = next(iter(p.xpath(".//*[contains(@class,'dc-title')]")), None)
            zweck = h.text_von(ziel if ziel is not None else p)
            p.drop_tree()

        # Signatur
        signatur = ""
        for pre in seite.xpath(".//pre[contains(@class,'methodsynopsis')]|.//div[contains(@class,'methodsynopsis') "
                               "and not(ancestor::div[contains(@class,'classsynopsis')])]"):
            text = h.text_von(pre)
            signatur = signatur or text
            _ersetzen(pre, _signatur(text))
        for div in seite.xpath(".//div[contains(@class,'classsynopsis')]"):
            kasten = lhtml.Element("div")
            kasten.set("class", "signatur")
            for zeile in div.xpath(".//*[contains(@class,'classsynopsisinfo') or contains(@class,'fieldsynopsis') "
                                   "or contains(@class,'methodsynopsis') or contains(@class,'constructorsynopsis')]"):
                SubElement(kasten, "div").text = h.text_von(zeile)
            _ersetzen(div, kasten)

        # Teile der Seite: eigene Überschriften, Parameter, Änderungen, Beispiele, Siehe auch
        typen = _typen_aus(signatur)
        for teil in seite.xpath(".//div[contains(@class,'refsect1')]"):
            art = next((k for k in (teil.get("class") or "").split() if k in TEILE), "")
            ueberschrift = next(iter(teil.xpath("./h3|./h2")), None)
            if ueberschrift is not None:
                ueberschrift.tag = "h2"
                if art:
                    for k in list(ueberschrift):
                        ueberschrift.remove(k)
                    ueberschrift.text = TEILE[art]
            if art == "parameters":
                _parameter(teil, typen)
            elif art == "changelog":
                for t in teil.iter("table"):
                    t.set("class", "aenderungen")
            elif art == "seealso":
                _siehe(teil)
        for kopfzeile in seite.iter("h2", "h3", "h4"):
            deutsch = UEBERSCHRIFTEN.get(h.text_von(kopfzeile).lower())
            if deutsch:
                for k in list(kopfzeile):
                    kopfzeile.remove(k)
                kopfzeile.text = deutsch
        for h4 in seite.xpath(".//div[contains(@class,'refsect2')]/h4|.//div[contains(@class,'refsect1')]//h4"):
            h4.tag = "h3"
        for note in seite.xpath(".//blockquote[contains(@class,'note')]|.//div[contains(@class,'note') or "
                                "contains(@class,'warning') or contains(@class,'caution') or contains(@class,'tip')]"):
            note.tag = "div"
            note.set("class", "hinweis")
        for div in seite.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' example ')]"):
            if div.getparent() is not None:
                _beispiel(div)
        _code_bloecke(seite)

        verweise, online = h.verweise_umschreiben(seite, buch.kennung, eintrag.pfad, wege)
        bild = h.bilder_umschreiben(seite, buch.kennung, eintrag.pfad, wege)
        abschnitte = h.ueberschriften(seite)
        h.saeubern(seite)
        einleitung = zweck or next((t for p in seite.iter("p") if len(t := h.text_von(p)) > 40), "")
        html = h.als_html(seite)
        if zweck:
            html = f'<p class="einleitung">{h.maskieren(zweck)}</p>' + html

        steckbrief = self._steckbrief(buch, titel, signatur, fassungen, rubrik_titel, code_titel, notizen)
        return Aufbereitet(titel=titel, html=html, einleitung=einleitung, abschnitte=abschnitte, steckbrief=steckbrief,
                           bild=bild, verweise=verweise, online=online, rubrik=rubrik_titel, rubrik_pfad=rubrik_pfad,
                           nachbarn=_fenster(umgebung, eintrag.pfad), titelart="code" if code_titel else "text")

    @staticmethod
    def _steckbrief(buch: Buch, titel: str, signatur: str, fassungen: list[str], rubrik: str, code_titel: bool,
                    notizen: int = 0):
        """Steckbrief einer Seite (Entwurf): Signatur, verfügbare Fassungen, Quelle. Ohne Signatur und Fassungen keiner."""
        if not signatur and not fassungen:
            return None
        wurzel = lhtml.Element("div")
        if signatur:
            SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
            wurzel[-1].text = "Signatur"
            wurzel.append(_signatur(signatur))
        if fassungen:
            SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
            wurzel[-1].text = "Verfügbar"
            liste = SubElement(wurzel, "div")
            liste.set("class", "versionen")
            for f in fassungen:
                SubElement(liste, "span").text = f
        SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
        wurzel[-1].text = "Quelle"
        werte = SubElement(wurzel, "dl")
        werte.set("class", "steckbrief-werte")
        for name, wert in (("Quelle", f"{buch.titel}, Stand {h.datum(buch.stand)}"), ("Rubrik", rubrik),
                           ("Notizen", f"{notizen} der Nutzer" if notizen else "")):
            if wert:
                SubElement(werte, "dt").text = name
                SubElement(werte, "dd").text = wert
        h.saeubern(wurzel)
        return Steckbrief(titel=titel, html="".join(h.als_html(k) for k in wurzel), code=code_titel)
