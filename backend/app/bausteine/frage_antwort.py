"""Baustein Frage und Antwort (Erzeuger sotoki): Seiten von Stack Exchange (Stack Overflow, Vi and Vim, ...), neu
gesetzt im Grunddesign der Artikelansicht (Entwurf frage-antwort.html). Die Quelle bringt je Frage eine Seite mit
`#question` und `div.answer` (die akzeptierte mit `accepted-answer`), Stimmen in `data-score`, Wer und Wann in der
`post-signature`, Kommentare als `li.comment`, Schlagwörter in `.post-taglist`, verwandte Fragen in `#sidebar`.

Nachschlag setzt daraus: die Frage mit Stimmen, Schlagwörtern und Kommentaren, darunter die Antworten nach Stimmen (die
akzeptierte zuerst und gekennzeichnet), jede mit Wer und Wann; Kommentare zugeklappt. Der Steckbrief nennt Stimmen,
Antworten, Gefragt, Bearbeitet, Schlagwörter und verwandte Fragen. Andere Seiten des Buchs (Nutzer, Schlagwörter)
zeigt die Originalansicht."""

from __future__ import annotations

import re

from lxml import html as lhtml
from lxml.etree import SubElement

from ..bibliothek import Eintrag
from ..modell.artikel import Abschnitt, Fragekarte, Steckbrief
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege
from .code import code_text

MONATE = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
ZEIT = re.compile(r"(asked|answered|edited)?\s*([A-Z][a-z]{2})\s+(\d{1,2})(?:\s*'(\d{2}))?")


def _datum(text: str) -> tuple[str, str]:
    """("asked Feb 03 '15 at 18:16") -> ("gefragt", "03.02.2015"); ohne Jahr gilt das Jahr nicht als bekannt."""
    m = ZEIT.search(text)
    if not m or m.group(2) not in MONATE:
        return "", text.strip()
    art = {"asked": "gefragt", "answered": "beantwortet", "edited": "bearbeitet"}.get(m.group(1) or "", "")
    jahr = f".20{m.group(4)}" if m.group(4) else ""
    return art, f"{int(m.group(3)):02d}.{MONATE[m.group(2)]:02d}{jahr}"


def _text(el, xpath: str) -> str:
    treffer = next(iter(el.xpath(xpath)), None)
    return h.text_von(treffer) if treffer is not None else ""


def _zahl(el, xpath: str) -> int:
    """Eine Zahl aus einem Teil (Stimmen, Antworten), Trennzeichen der Quelle entfernt."""
    return int(re.sub(r"\D", "", _text(el, xpath)) or 0)


def _deutsche_zahl(roh: str) -> str:
    """Zahl mit Tausenderpunkt wie überall in der App (27527 -> 27.527, -3 bleibt -3); Unlesbares bleibt, wie es ist."""
    try:
        return f"{int(roh):,}".replace(",", ".")
    except ValueError:
        return roh


def _listentitel(quelle: str) -> str:
    """Feste Überschriften der Fragenlisten, wie Nachschlag sie nennt."""
    if quelle.lower() in ("most popular", "top questions", "highest scored questions", "newest questions", "all questions"):
        return {"newest questions": "Neueste Fragen", "all questions": "Alle Fragen"}.get(quelle.lower(), "Beliebteste Fragen")
    if m := re.match(r"questions tagged \[?([^\]]+)\]?", quelle, re.I):
        return f"Fragen mit dem Schlagwort {m.group(1)}"
    return quelle


def _signaturen(beitrag) -> dict[str, tuple[str, str]]:
    """Wer und Wann eines Beitrags: {"gefragt": ("03.02.2015", "thameera"), "bearbeitet": (...)}."""
    ergebnis: dict[str, tuple[str, str]] = {}
    for sig in beitrag.xpath(".//div[contains(@class,'post-signature')]"):
        zeit = next(iter(sig.xpath(".//time")), None)
        wer = next(iter(sig.xpath(".//a[contains(@class,'s-user-card--link')]|.//*[contains(@class,'s-user-card--info')]//span")), None)
        if zeit is None:
            continue
        art, datum = _datum(zeit.get("datetime") or h.text_von(zeit))
        if art:
            ergebnis[art] = (datum, h.text_von(wer) if wer is not None else "")
    return ergebnis


def _kommentare(beitrag):
    """Kommentare zugeklappt (details) mit Stimmen, Text und Wer; ohne Kommentare nichts."""
    liste = beitrag.xpath(".//li[contains(concat(' ', normalize-space(@class), ' '), ' comment ')]")
    if not liste:
        return None
    kasten = lhtml.Element("details")
    kasten.set("class", "kommentare")
    SubElement(kasten, "summary").text = f"{len(liste)} {'Kommentar' if len(liste) == 1 else 'Kommentare'}"
    ul = SubElement(kasten, "ul")
    ul.set("class", "kommentar-liste")
    for k in liste:
        li = SubElement(ul, "li")
        punkte = k.get("data-comment-score") or ""
        if punkte and punkte != "0":
            SubElement(li, "b").text = f"+{punkte}"
        text = next(iter(k.xpath(".//span[contains(@class,'comment-copy')]")), None)
        if text is not None:
            h.verschieben(text, li)
        wer = next(iter(k.xpath(".//a[contains(@class,'comment-user')]|.//span[contains(@class,'comment-user')]")), None)
        if wer is not None:
            SubElement(li, "i").text = h.text_von(wer)
            li[-1].tail = None
    return kasten


def _beitrag(quelle, art: str, akzeptiert: bool = False):
    """Ein Beitrag (Frage oder Antwort) als qa-beitrag: Stimmen links, Text, Fuß mit Wer und Wann, Kommentare."""
    stimmen = _deutsche_zahl(quelle.get("data-score") or "0")
    kasten = lhtml.Element("div")
    kasten.set("class", "qa-beitrag")
    links = SubElement(kasten, "div")
    links.set("class", "qa-stimmen")
    SubElement(links, "span").set("class", "zahl")
    links[-1].text = stimmen
    SubElement(links, "span").set("class", "was")
    links[-1].text = "Stimmen"
    rechts = SubElement(kasten, "div")
    if akzeptiert:
        SubElement(rechts, "span").set("class", "akz-marke")
        rechts[-1].text = "Akzeptierte Antwort"
    text = next(iter(quelle.xpath(".//div[contains(@class,'js-post-body')]")), None)
    if text is not None:
        for pre in text.iter("pre"):
            code = code_text(pre)
            for k in list(pre):
                pre.remove(k)
            pre.text = code
            pre.set("class", "codeblock")
        h.verschieben(text, rechts)
    if art == "gefragt":
        marken = [h.text_von(a) for a in quelle.xpath(".//a[contains(@class,'post-tag')]")]
        if marken:
            reihe = SubElement(rechts, "div")
            reihe.set("class", "schlagwoerter")
            for m in marken:
                SubElement(reihe, "span").text = m
    sig = _signaturen(quelle).get(art)
    fuss = SubElement(rechts, "div")
    fuss.set("class", "beitrag-fuss")
    if sig:
        SubElement(fuss, "span").text = f"{art} {sig[0]}" + (f" von {sig[1]}" if sig[1] else "")
    kommentare = _kommentare(quelle)
    if kommentare is not None:
        rechts.append(kommentare)
    return kasten, int(stimmen) if stimmen.lstrip("-").isdigit() else 0, (sig[1] if sig else "")


class FrageAntwort:
    kennung = "frage_antwort"
    arten = frozenset({"frage_antwort"})
    darstellung = "lesedesign"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and (b'id="question"' in eintrag.inhalt
                                                          or b'class="question-summary"' in eintrag.inhalt)

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        h.stile_uebersetzen(doc)
        if not doc.xpath("//*[@id='question']"):
            return self._liste(doc, buch, eintrag, wege)
        kopf = next(iter(doc.xpath("//*[@id='question-header']//h1")), None)
        titel = h.text_von(kopf) if kopf is not None else eintrag.titel
        frage = doc.xpath("//*[@id='question']")[0]
        nummer = frage.get("data-questionid") or ""
        signaturen = _signaturen(frage)

        wurzel = lhtml.Element("div")
        abschnitt = SubElement(wurzel, "section")
        abschnitt.set("id", "frage")
        beitrag, stimmen_frage, _ = _beitrag(frage, "gefragt")
        abschnitt.append(beitrag)
        abschnitte = [Abschnitt(anker="frage", titel="Frage", ebene=2)]

        antworten = []
        for quelle in doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' answer ')]"):
            akzeptiert = "accepted-answer" in (quelle.get("class") or "")
            kasten, stimmen, wer = _beitrag(quelle, "beantwortet", akzeptiert)
            antworten.append((not akzeptiert, -stimmen, quelle.get("data-answerid") or "", kasten, stimmen, wer, akzeptiert))
        antworten.sort(key=lambda a: (a[0], a[1]))            # die akzeptierte zuerst, dann nach Stimmen
        if antworten:
            kopf_a = SubElement(wurzel, "div")
            kopf_a.set("class", "antworten-kopf")
            ueberschrift = SubElement(kopf_a, "h2")
            ueberschrift.set("id", "antworten")
            ueberschrift.text = f"{len(antworten)} {'Antwort' if len(antworten) == 1 else 'Antworten'}"
            abschnitte.append(Abschnitt(anker="antworten", titel=ueberschrift.text, ebene=2))
        for _, _, kennung, kasten, stimmen, wer, akzeptiert in antworten:
            antwort = SubElement(wurzel, "div")
            antwort.set("class", "antwort akzeptiert" if akzeptiert else "antwort")
            antwort.set("id", f"antwort-{kennung}")
            antwort.append(kasten)
            abschnitte.append(Abschnitt(anker=f"antwort-{kennung}", titel=f"{stimmen} · {wer or 'unbekannt'}", ebene=3))

        verweise, online = h.verweise_umschreiben(wurzel, buch.kennung, eintrag.pfad, wege)
        bild = h.bilder_umschreiben(wurzel, buch.kennung, eintrag.pfad, wege)
        h.saeubern(wurzel)
        einleitung = next((t for p in wurzel.iter("p") if len(t := h.text_von(p)) > 20), "")
        html = "".join(h.als_html(k) for k in wurzel)

        steckbrief = self._steckbrief(doc, buch, eintrag, wege, nummer, stimmen_frage, antworten, signaturen)
        return Aufbereitet(titel=titel, html=html, einleitung=einleitung, abschnitte=abschnitte, steckbrief=steckbrief,
                           bild=bild, verweise=verweise, online=online, rubrik="Fragen")

    @staticmethod
    def _liste(doc, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        """Fragenliste (Startseite, Schlagwortseiten): Karten mit Stimmen, Antworten, Auszug, Schlagwörtern, dazu
        Blättern über die Seiten der Quelle."""
        fragen: list[Fragekarte] = []
        for karte in doc.xpath("//div[contains(@class,'question-summary')]"):
            a = next(iter(karte.xpath(".//a[contains(@class,'question-hyperlink')]")), None)
            if a is None:
                continue
            ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
            if not ziel or not wege.gibt_es(buch.kennung, ziel):
                continue
            status = next(iter(karte.xpath(".//div[contains(@class,'status')]")), None)
            zeit = next(iter(karte.xpath(".//time")), None)
            fragen.append(Fragekarte(
                pfad=ziel, titel=h.text_von(a), auszug=_text(karte, ".//*[contains(@class,'excerpt')]"),
                stimmen=_zahl(karte, ".//*[contains(@class,'vote-count-post')]"),
                antworten=_zahl(karte, ".//div[contains(@class,'status')]/strong"),
                akzeptiert=status is not None and "accepted" in (status.get("class") or ""),
                schlagwoerter=[h.text_von(t) for t in karte.xpath(".//a[contains(@class,'post-tag')]")],
                gefragt=_datum(zeit.get("datetime") or "")[1] if zeit is not None else ""))
        blaettern = {}
        for a in doc.xpath("//*[contains(@class,'s-pagination')]//a"):
            ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
            richtung = {"next": "weiter", "prev": "zurueck"}.get((a.get("rel") or "").strip())
            text = h.text_von(a).lower()
            richtung = richtung or ("weiter" if text.startswith("next") else "zurueck" if text.startswith("prev") else None)
            if richtung and ziel and wege.gibt_es(buch.kennung, ziel):
                blaettern[richtung] = ziel
        kopf = next(iter(doc.xpath("//h1")), None)
        titel = _listentitel(h.text_von(kopf) if kopf is not None else "") or buch.titel
        return Aufbereitet(titel=titel, fragen=fragen, darstellung="uebersicht", rubrik="Fragen",
                           zurueck=blaettern.get("zurueck", ""), weiter=blaettern.get("weiter", ""))

    @staticmethod
    def _steckbrief(doc, buch: Buch, eintrag: Eintrag, wege: Wege, nummer: str, stimmen: int, antworten: list,
                    signaturen: dict[str, tuple[str, str]]) -> Steckbrief:
        """Steckbrief (Entwurf): Stimmen, Antworten, Gefragt, Bearbeitet, Schlagwörter, verwandte Fragen."""
        wurzel = lhtml.Element("div")
        werte = SubElement(wurzel, "dl")
        werte.set("class", "steckbrief-werte")
        akzeptiert = any(a[6] for a in antworten)
        zeilen = [("Stimmen", str(stimmen)),
                  ("Antworten", f"{len(antworten)}" + (", eine akzeptiert" if akzeptiert else "")),
                  ("Gefragt", " von ".join(x for x in signaturen.get("gefragt", ("", ""))) if "gefragt" in signaturen else ""),
                  ("Bearbeitet", signaturen["bearbeitet"][0] if "bearbeitet" in signaturen else "")]
        for name, wert in zeilen:
            if wert:
                SubElement(werte, "dt").text = name
                SubElement(werte, "dd").text = wert
        marken = [h.text_von(a) for a in doc.xpath("//*[@id='question']//a[contains(@class,'post-tag')]")]
        if marken:
            SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
            wurzel[-1].text = "Schlagwörter"
            reihe = SubElement(wurzel, "div")
            reihe.set("class", "schlagwoerter")
            for m in marken:
                SubElement(reihe, "span").text = m
        verwandt = []
        for a in doc.xpath("//*[@id='sidebar']//a[contains(@class,'question-hyperlink')]"):
            ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
            if ziel and wege.gibt_es(buch.kennung, ziel):
                verwandt.append((wege.artikel(buch.kennung, ziel), h.text_von(a)))
        if verwandt:
            SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
            wurzel[-1].text = "Verwandt"
            liste = SubElement(wurzel, "ul")
            liste.set("class", "verwandt")
            for adresse, text in verwandt[:6]:
                a = SubElement(SubElement(liste, "li"), "a")
                a.set("href", adresse)
                a.set("class", "wl")
                a.text = text
        h.saeubern(wurzel)
        return Steckbrief(titel=f"Frage {nummer}" if nummer else "Frage", html="".join(h.als_html(k) for k in wurzel))
