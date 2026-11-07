"""Bausteine der Inhaltsart Anleitung (iFixit, WIKI-64; Entwürfe ifixit-*.html, entschieden im Gespräch 08.11.2026).

Die Quelle ist ein Abbild der Webseite. Je Seitenart ein Baustein, erkannt an Merkmalen im Inhalt, nie am Pfad:
- Anleitung (auch Zerlegung): `guide-intro-title`, Kopfdaten (Schwierigkeit als `difficulty-N`, Zeitaufwand), Werkzeuge
  und Ersatzteile, Schritte (`li.step-wrapper`) mit Bildern und Zeilen (`level-N`, Marken `bullet-line-icon-note|
  caution|reminder`, Farbpunkte `bullet_<farbe>` passend zu Markierungen im Bild), Abschluss.
- Gerät: `banner-content`; Kategorien führen Unterkategorien (`categoryListCell`), Geräte ihre Anleitungen (die Titel
  dort nennen das Bauteil), dazu Werkzeuge und eine Beschreibung.
Die Sprache bestimmt der Text (alle Seiten tragen lang=fr). Zu welchem Gerät eine Anleitung gehört, sagen nur die
Geräteseiten (Verweise im Text der Anleitung zeigen oft auf andere Modelle); das führt der eigene Index zusammen.
Nutzer- und Info-Seiten zeigt die Originalansicht."""

from __future__ import annotations

import re

from lxml import html as lhtml

from ..bibliothek import Eintrag
from ..modell.anleitung import Anleitungsangaben, Geraeteangaben, Geraeteeintrag, Schritt, Werkzeug, Zeile
from ..modell.buch import Buch
from ..textsprache import sprache_von
from . import html as h
from .basis import Aufbereitet, Wege

ANLEITUNG = b"guide-intro-title"
ZERLEGUNG = b"teardown-image-overlay"
GERAET = b"banner-content"
MARKEN = {"note": "hinweis", "caution": "vorsicht", "reminder": "erinnerung"}
#: Zeitangaben der Quelle in Minuten je Einheit (deutsch, englisch, französisch: das Buch mischt)
EINHEITEN = {"sekunde": 1 / 60, "second": 1 / 60, "minute": 1, "stunde": 60, "hour": 60, "heure": 60, "tag": 1440, "day": 1440}
_ZEITTEIL = re.compile(r"(\d+(?:[.,]\d+)?)\s*([a-zäöü]+)?", re.I)


def _klasse(el, name: str) -> list:
    return el.xpath(f'.//*[contains(concat(" ", normalize-space(@class), " "), " {name} ")]')


def _eins(el, xpath: str):
    return next(iter(el.xpath(xpath)), None)


def _text(el) -> str:
    return h.gerade(h.text_von(el)) if el is not None else ""


def zeitspanne(text: str) -> tuple[int | None, int | None]:
    """"1 - 2 Stunden" -> (60, 120); "30 Minuten - 1 Stunde" -> (30, 60); "10 Minuten" -> (10, 10); ohne Zahl: (None, None)."""
    teile = [m for m in _ZEITTEIL.finditer(text)]
    if not teile:
        return None, None

    def minuten(zahl: str, einheit: str | None, sonst: str | None) -> int | None:
        e = (einheit or sonst or "").lower()
        faktor = next((f for k, f in EINHEITEN.items() if e.startswith(k)), None)
        return round(float(zahl.replace(",", ".")) * faktor) if faktor is not None else None

    letzte = teile[-1].group(2)
    von = minuten(teile[0].group(1), teile[0].group(2), letzte)
    bis = minuten(teile[-1].group(1), letzte, letzte)
    return von, bis


def _bild(wege: Wege, buch: Buch, pfad: str, img) -> str:
    src = (img.get("src") or "") if img is not None else ""
    return wege.medien(buch.kennung, h.ziel_im_buch(pfad, src)) if src and not h.ist_online(src) else ""


def _werkzeuge(doc, art: str, wege: Wege, buch: Buch, pfad: str) -> list[Werkzeug]:
    aus = []
    for li in doc.xpath(f'//*[contains(@class,"item-list-{art}")]//li'):
        name = _text(_eins(li, './/*[@itemprop="name"]'))
        if name:
            aus.append(Werkzeug(name=name, bild=_bild(wege, buch, pfad, _eins(li, ".//img"))))
    return aus


def _zeile(li) -> Zeile:
    klassen = li.get("class") or ""
    stufe = re.search(r"level-(\d)", klassen)
    marke = re.search(r"bullet-line-icon-(\w+)", klassen)
    farbe = re.search(r"bullet_(\w+)", lhtml.tostring(li, encoding="unicode")[:400])
    absatz = _eins(li, "./p")
    return Zeile(stufe=min(int(stufe.group(1)), 3) if stufe else 0, marke=MARKEN.get(marke.group(1), "") if marke else "",
                 farbe=farbe.group(1) if farbe and farbe.group(1) != "black" else "", text=_text(absatz if absatz is not None else li))


def _schritte(doc, wege: Wege, buch: Buch, pfad: str) -> list[Schritt]:
    aus = []
    for nr, s in enumerate(doc.xpath('//ol[contains(@class,"steps-container")]//li[contains(@class,"step-wrapper")]'), 1):
        bilder = s.xpath('.//*[contains(@class,"step-thumbnails")]//img') or s.xpath('.//img[contains(@class,"js-step-main-image")]')[:1]
        aus.append(Schritt(nr=nr, titel=_text(_eins(s, './/*[contains(@class,"stepTitleTitle")]')),
                           bilder=[b for b in (_bild(wege, buch, pfad, i) for i in bilder) if b],
                           zeilen=[_zeile(li) for li in s.xpath('.//ul[contains(@class,"step-lines")]/li')]))
    return aus


def anleitung_lesen(doc, buch: Buch, pfad: str, wege: Wege, zerlegung: bool) -> tuple[str, Anleitungsangaben]:
    """Titel und Angaben einer Anleitung; eine Wahrheit für Lesen, Werkstatt und Index."""
    titel = _text(_eins(doc, '//*[contains(@class,"guide-intro-title")]'))
    werte = {_text(_eins(i, './/p[contains(@class,"item-title")]')): _text(_eins(i, './/p[contains(@class,"item-value")]'))
             for i in doc.xpath('//*[contains(@class,"details-item ")]')}
    schw = next((int(m.group(1)) for el in doc.xpath('//*[contains(@class,"difficulty-")]')
                 if (m := re.search(r"\bdifficulty-(\d)\b", el.get("class") or ""))), 0)
    zeit = next((v for k, v in werte.items() if k.lower().startswith(("zeit", "time", "temps"))), "")
    von, bis = zeitspanne(zeit)
    einleitung = _text(_eins(doc, '//*[contains(@class,"introduction-container")]//*[@itemprop="description"]'))
    schritte = _schritte(doc, wege, buch, pfad)
    text = " ".join([titel, einleitung] + [z.text for s in schritte[:20] for z in s.zeilen])
    return titel, Anleitungsangaben(
        art="zerlegung" if zerlegung else "anleitung", sprache=sprache_von(text),
        autor=_text(_eins(doc, '//*[contains(@class,"guide-author")]//a')), schwierigkeit=schw if 0 < schw <= 5 else 0,
        schwierigkeit_text=next((v for k, v in werte.items() if k.lower().startswith(("schwierig", "difficult"))), ""),
        zeit=zeit, zeit_von=von, zeit_bis=bis, einleitung=einleitung,
        hauptbild=_bild(wege, buch, pfad, _eins(doc, '//*[contains(@class,"guide-main-image")]//img')),
        werkzeuge=_werkzeuge(doc, "tools", wege, buch, pfad), teile=_werkzeuge(doc, "parts", wege, buch, pfad),
        schritte=schritte, abschluss=_text(_eins(doc, '//*[contains(@class,"conclusionText")]')))


def _lesetext(titel: str, a: Anleitungsangaben) -> str:
    """Die Anleitung als schlichtes HTML: für Volltext, Vorlesen und Übersetzen (die Ansicht setzt sie selbst aus den
    Angaben)."""
    teile = [f"<p>{h.maskieren(a.einleitung)}</p>"] if a.einleitung else []
    for s in a.schritte:
        teile.append(f'<h2 id="schritt-{s.nr}">Schritt {s.nr}{": " + h.maskieren(s.titel) if s.titel else ""}</h2>')
        teile.append("<ul>" + "".join(f"<li>{h.maskieren(z.text)}</li>" for z in s.zeilen) + "</ul>")
    if a.abschluss:
        teile.append(f"<p>{h.maskieren(a.abschluss)}</p>")
    return "".join(teile)


class Anleitung:
    kennung = "anleitung"
    arten = frozenset({"anleitung"})
    darstellung = "anleitung"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and ANLEITUNG in eintrag.inhalt

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        titel, angaben = anleitung_lesen(doc, buch, eintrag.pfad, wege, ZERLEGUNG in eintrag.inhalt)
        return Aufbereitet(titel=titel or eintrag.titel, html=_lesetext(titel, angaben), einleitung=angaben.einleitung,
                           bild=angaben.hauptbild or next((s.bilder[0] for s in angaben.schritte if s.bilder), ""),
                           anleitung=angaben)


class Geraet:
    kennung = "geraet"
    arten = frozenset({"anleitung"})
    darstellung = "geraet"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and GERAET in eintrag.inhalt and ANLEITUNG not in eintrag.inhalt

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        pfad = eintrag.pfad

        def eintraege(xpath: str, titel_xpath: str) -> list[Geraeteeintrag]:
            aus, gesehen = [], set()
            for a in doc.xpath(xpath):
                ziel = h.ziel_im_buch(pfad, a.get("href") or "")
                if ziel in gesehen or not wege.gibt_es(buch.kennung, ziel):
                    continue
                gesehen.add(ziel)
                kurz = _text(_eins(a, ".//p"))
                aus.append(Geraeteeintrag(pfad=ziel, titel=_text(_eins(a, titel_xpath)) or _text(a), kurz=kurz,
                                          bild=_bild(wege, buch, pfad, _eins(a, ".//img")),
                                          empfohlen="entry" in (a.get("class") or "").split()))
            return aus

        werkzeuge = list(dict.fromkeys(t for t in (_text(x) for x in doc.xpath('//*[contains(@class,"deviceToolsList")]//*[@itemprop="name" or contains(@class,"title")]')) if t))
        beschreibung = _eins(doc, '//*[contains(@class,"wikiRenderedText")]')
        html, verweise = "", None
        if beschreibung is not None:
            verweise, _ = h.verweise_umschreiben(beschreibung, buch.kennung, pfad, wege)
            h.bilder_umschreiben(beschreibung, buch.kennung, pfad, wege)
            h.saeubern(beschreibung)
            html = h.als_html(beschreibung)
        angaben = Geraeteangaben(
            kurz=_text(_eins(doc, '//*[contains(@class,"banner-blurb")]')) or _text(_eins(doc, '//*[contains(@class,"banner-summary")]')),
            bild=_bild(wege, buch, pfad, _eins(doc, '//*[contains(@class,"banner-small-photo")]//img')),
            unterkategorien=eintraege('//*[contains(@class,"categoryListCell")]/a', './/*[contains(@class,"title")]'),
            anleitungen=eintraege('//a[contains(@href,"Anleitung/") or contains(@href,"Teardown/")]', ".//h4"),
            werkzeuge=werkzeuge)
        weiter = {"verweise": verweise} if verweise else {}
        return Aufbereitet(titel=_text(_eins(doc, '//*[contains(@class,"banner-title")]')) or eintrag.titel, html=html,
                           einleitung=angaben.kurz, bild=angaben.bild, geraet=angaben, **weiter)


class Anleitungsstart:
    """Startseite des Buchs (`featured-categories`): Nachschlag zeigt dort "Anleitungen finden" (Suche mit Filtern) und
    die obersten Kategorien als Einstieg in den Gerätebaum."""
    kennung = "anleitungsstart"
    arten = frozenset({"anleitung"})
    darstellung = "anleitungen"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and b"featured-categories" in eintrag.inhalt

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        kategorien, gesehen = [], set()
        for a in doc.xpath('//a[contains(@class,"featured-category-item") or contains(@class,"sub-category")]'):
            ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
            if ziel in gesehen or not wege.gibt_es(buch.kennung, ziel):
                continue
            gesehen.add(ziel)
            titel = _text(_eins(a, './/*[contains(@class,"sub-category-title-text") or contains(@class,"featured-category-title")]'))
            kategorien.append(Geraeteeintrag(pfad=ziel, titel=titel or _text(a), bild=_bild(wege, buch, eintrag.pfad, _eins(a, ".//img")),
                                             empfohlen="featured-category-item" in (a.get("class") or "")))
        return Aufbereitet(titel=buch.titel, geraet=Geraeteangaben(kurz=buch.beschreibung, unterkategorien=kategorien))
