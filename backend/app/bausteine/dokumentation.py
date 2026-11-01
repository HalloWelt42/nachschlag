"""Baustein Dokumentation (Erzeuger devdocs2zim): Handbücher wie das von PHP, neu gesetzt im Grunddesign der
Artikelansicht (Entwurf doku-php.html). Die Quelle bringt das Handbuch als DocBook-HTML in `div._page`; jede Seite
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
from .code import einfaerben

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
    bloecke = [el for el in div.iter("pre", "p") if el.tag == "pre" or not el.xpath("ancestor::pre")]
    for i, el in enumerate(bloecke):
        if el.tag == "p":
            folgt_ausgabe = i + 1 < len(bloecke) and bloecke[i + 1].tag == "pre" and "phpcode" not in (bloecke[i + 1].get("class") or "")
            if folgt_ausgabe and VOR_AUSGABE.search(h.text_von(el)):
                continue
            absatz = SubElement(kasten, "p")
            absatz.set("class", "bnotiz")
            h.verschieben(el, absatz)
            continue
        code = el.text_content()
        if "phpcode" in (el.get("class") or "") or el.get("data-language") == "php":
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
    for pre in list(inhalt.iter("pre")):
        if pre.getparent() is None:
            continue
        if any(a.get("class") == "beispiel" for a in pre.iterancestors()):
            continue
        sprache = "php" if ("phpcode" in (pre.get("class") or "") or pre.get("data-language") == "php") else ""
        kasten = lhtml.Element("div")
        kasten.set("class", "beispiel")
        if sprache:
            kasten.append(einfaerben(pre.text_content(), sprache))
        else:
            aus = SubElement(kasten, "pre")
            aus.set("class", "ausgabe")
            aus.text = pre.text_content()
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


class Dokumentation:
    kennung = "dokumentation"
    arten = frozenset({"dokumentation"})
    darstellung = "lesedesign"

    def __init__(self) -> None:
        self._gliederungen: dict[tuple[str, str], Gliederung] = {}

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and b'class="_page' in eintrag.inhalt

    def _gliederung(self, buch: Buch, wege: Wege) -> Gliederung:
        schluessel = (buch.kennung, buch.stand)
        if schluessel not in self._gliederungen:
            self._gliederungen[schluessel] = _gliederung(wege.datei(buch.kennung, GLIEDERUNG))
        return self._gliederungen[schluessel]

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        gliederung = self._gliederung(buch, wege)
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        seite = next(iter(doc.xpath("//div[contains(@class,'_page')]")), None)
        if seite is None:
            return Aufbereitet(titel=eintrag.titel)
        for el in seite.xpath(".//div[contains(@class,'_attribution')]"):
            el.drop_tree()
        if eintrag.pfad == "index" or not seite.xpath(".//p|.//pre|.//table"):
            # Startseite des Buchs (in der Quelle leer): Übersicht der Rubriken
            return Aufbereitet(titel=buch.titel, gruppen=gliederung.rubriken, darstellung="uebersicht")

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

        nr = gliederung.rubrik_von.get(eintrag.pfad)
        rubrik = gliederung.rubriken[nr] if nr is not None else None
        steckbrief = self._steckbrief(buch, titel, signatur, fassungen, rubrik.titel if rubrik else "", code_titel)
        nachbarn: list[Nachbar] = []
        if rubrik:
            i = next((n for n, e in enumerate(rubrik.eintraege) if e.pfad == eintrag.pfad), 0)
            von = max(0, min(i - NACHBARN_UM, len(rubrik.eintraege) - 2 * NACHBARN_UM - 1))
            nachbarn = rubrik.eintraege[von:von + 2 * NACHBARN_UM + 1]
        return Aufbereitet(titel=titel, html=html, einleitung=einleitung, abschnitte=abschnitte, steckbrief=steckbrief,
                           bild=bild, verweise=verweise, online=online, rubrik=rubrik.titel if rubrik else "",
                           nachbarn=nachbarn, titelart="code" if code_titel else "text")

    @staticmethod
    def _steckbrief(buch: Buch, titel: str, signatur: str, fassungen: list[str], rubrik: str, code_titel: bool):
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
        for name, wert in (("Buch", f"{buch.titel}, Stand {h.datum(buch.stand)}"), ("Rubrik", rubrik)):
            if wert:
                SubElement(werte, "dt").text = name
                SubElement(werte, "dd").text = wert
        h.saeubern(wurzel)
        return Steckbrief(titel=titel, html="".join(h.als_html(k) for k in wurzel), code=code_titel)
