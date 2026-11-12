"""Baustein Frage und Antwort (Erzeuger sotoki): Seiten von Stack Exchange (Stack Overflow, Vi and Vim, ...), neu
gesetzt im Grunddesign der Artikelansicht (Entwurf frage-antwort.html). Die Quelle bringt je Frage eine Seite mit
`#question` und `div.answer` (die akzeptierte mit `accepted-answer`), Stimmen in `data-score`, Wer und Wann in der
`post-signature`, Kommentare als `li.comment`, Schlagwörter in `.post-taglist`, verwandte Fragen in `#sidebar`.

Nachschlag setzt daraus: die Frage mit Stimmen, Schlagwörtern und Kommentaren, darunter die Antworten nach Stimmen (die
akzeptierte zuerst und gekennzeichnet), jede mit Wer und Wann; Kommentare zugeklappt. Der Steckbrief nennt Stimmen,
Antworten, Gefragt, Bearbeitet, Schlagwörter und verwandte Fragen.

Schlagwörter sind die Kategorien des Buchs (WIKI-95): die Seite `tags` wird zur Kategorieseite mit den Schlagwörtern als
Unterkategorien (mit der Zahl ihrer Fragen), eine Frage nennt ihre Schlagwörter als Kategorien, eine Fragenliste die
meistgenutzten. Jedes führt auf seine Liste `questions/tagged/<wort>`. Andere Seiten des Buchs (Nutzer) zeigt die
Originalansicht."""

from __future__ import annotations

import re
from typing import NamedTuple

from lxml import html as lhtml
from lxml.etree import SubElement

from ..bibliothek import Eintrag
from ..modell.artikel import Abschnitt, Beitrag, FrageAngaben, Fragekarte, Kategorieangaben, Kategorieverweis, Steckbrief
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege
from .code import code_text

KONTO = re.compile(r"users/(\d+)")
#: die Übersicht der Schlagwörter im Buch
SCHLAGWORTSEITE = "tags"
#: so viele der meistgenutzten Schlagwörter nennt eine Fragenliste als ihre Kategorien
SCHLAGWOERTER_IN_LISTEN = 24
_ZAHL_FRAGEN = re.compile(r"(\d[\d,.]*)\s+questions?", re.I)
#: die Schlagwörter der Übersicht je Buch, einmal gelesen (das Buch ändert sich nicht, eine neue Fassung hat eine neue Kennung)
_UEBERSICHT: dict[str, list[Kategorieverweis]] = {}
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


class Signatur(NamedTuple):
    datum: str           # TT.MM.JJJJ (ohne Jahr nur TT.MM)
    wer: str
    nr: str              # Nummer des Kontos im Buch (users/13055/...), leer, wenn die Quelle keine nennt


def _signaturen(beitrag) -> dict[str, Signatur]:
    """Wer und Wann eines Beitrags: {"gefragt": Signatur("03.02.2015", "thameera", "13055"), "bearbeitet": ...}."""
    ergebnis: dict[str, Signatur] = {}
    for sig in beitrag.xpath(".//div[contains(@class,'post-signature')]"):
        zeit = next(iter(sig.xpath(".//time")), None)
        wer = next(iter(sig.xpath(".//a[contains(@class,'s-user-card--link')]|.//*[contains(@class,'s-user-card--info')]//span")), None)
        if zeit is None:
            continue
        art, datum = _datum(zeit.get("datetime") or h.text_von(zeit))
        konto = KONTO.search(wer.get("href") or "") if wer is not None and wer.tag == "a" else None
        if art:
            ergebnis[art] = Signatur(datum, h.text_von(wer) if wer is not None else "", konto.group(1) if konto else "")
    return ergebnis


def _iso(datum: str) -> str:
    """TT.MM.JJJJ -> JJJJ-MM-TT (zum Sortieren und für Zeiträume); ohne Jahr leer."""
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", datum)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _schlagwoerter(eltern, marken: list[str], buch: Buch, wege: Wege) -> None:
    """Schlagwörter als Reihe; jedes führt ins Register (Klasse register: das Umschreiben lässt den Verweis stehen)."""
    reihe = SubElement(eltern, "div")
    reihe.set("class", "schlagwoerter")
    for m in marken:
        ziel = wege.schlagwort(buch.kennung, m)
        el = SubElement(reihe, "a" if ziel else "span")
        el.text = m
        if ziel:
            el.set("href", ziel)
            el.set("class", "register")


def _schlagwortpfad(wort: str) -> str:
    return f"questions/tagged/{wort}"


def _als_kategorien(marken: list[str], buch: Buch, wege: Wege) -> list[Kategorieverweis]:
    """Schlagwörter, deren Liste das Buch hat, als Kategorien."""
    return [Kategorieverweis(pfad=p, titel=m) for m in marken if wege.gibt_es(buch.kennung, p := _schlagwortpfad(m))]


def _schlagwortkarten(doc, buch: Buch, wege: Wege) -> list[Kategorieverweis]:
    """Die Karten der Schlagwortübersicht: Name, Liste im Buch, Zahl der Fragen (in der Folge der Quelle: die
    meistgenutzten zuerst)."""
    karten = []
    for karte in doc.xpath("//div[contains(@class,'js-tag-cell')]"):
        wort = _text(karte, ".//a[contains(@class,'post-tag')]")
        zahl = _ZAHL_FRAGEN.search(h.text_von(karte))
        if wort and wege.gibt_es(buch.kennung, pfad := _schlagwortpfad(wort)):
            karten.append(Kategorieverweis(pfad=pfad, titel=wort, anzahl=int(re.sub(r"\D", "", zahl.group(1))) if zahl else None))
    return karten


def _meistgenutzte(buch: Buch, wege: Wege) -> list[Kategorieverweis]:
    """Die meistgenutzten Schlagwörter des Buchs aus seiner Übersicht; ohne Übersicht keine."""
    if buch.kennung not in _UEBERSICHT:
        roh = wege.datei(buch.kennung, SCHLAGWORTSEITE)
        _UEBERSICHT[buch.kennung] = _schlagwortkarten(lhtml.fromstring(roh.decode("utf-8", "replace")), buch, wege) if roh else []
    return _UEBERSICHT[buch.kennung][:SCHLAGWOERTER_IN_LISTEN]


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


def _beitrag(quelle, art: str, buch: Buch, wege: Wege, akzeptiert: bool = False) -> tuple[object, Beitrag]:
    """Ein Beitrag (Frage oder Antwort) als qa-beitrag: Stimmen links, Text, Fuß mit Wer (verweist auf den Autor im
    Register) und Wann, Kommentare. Dazu der Beitrag als Angabe: Stimmen als Zahl (zum Sortieren, für Steckbrief und
    Register; geschrieben mit Tausenderpunkt), Autor mit Kontonummer, Datum."""
    roh = (quelle.get("data-score") or "0").strip()
    zahl = int(roh) if roh.lstrip("-").isdigit() else 0
    stimmen = _deutsche_zahl(roh)
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
        # nur äußere Blöcke, vorher gesammelt: die Quelle verschachtelt Blöcke (Block im Code eines Blocks), und das
        # Aushängen der Kinder hielte ein laufendes iter() im ausgehängten Teil fest; alle Blöcke danach blieben roh
        for pre in text.xpath(".//pre[not(ancestor::pre)]"):
            code = code_text(pre)
            for k in list(pre):
                pre.remove(k)
            pre.text = code
            pre.set("class", "codeblock")
        h.verschieben(text, rechts)
    if art == "gefragt":
        marken = [h.text_von(a) for a in quelle.xpath(".//a[contains(@class,'post-tag')]")]
        if marken:
            _schlagwoerter(rechts, marken, buch, wege)
    sig = _signaturen(quelle).get(art)
    fuss = SubElement(rechts, "div")
    fuss.set("class", "beitrag-fuss")
    if sig:
        zeile = SubElement(fuss, "span")
        zeile.text = f"{art} {sig.datum}" + (" von " if sig.wer else "")
        ziel = wege.autor(buch.kennung, sig.nr) if sig.nr else ""
        if sig.wer and ziel:
            autor = SubElement(zeile, "a")
            autor.set("href", ziel)
            autor.set("class", "register")
            autor.text = sig.wer
        elif sig.wer:
            zeile.text += sig.wer
    kommentare = _kommentare(quelle)
    if kommentare is not None:
        rechts.append(kommentare)
    angabe = Beitrag(art="frage" if art == "gefragt" else "antwort", autor=sig.wer if sig else "", autor_nr=sig.nr if sig else "",
                     stimmen=zahl, datum=_iso(sig.datum) if sig else "", akzeptiert=akzeptiert)
    return kasten, angabe


class FrageAntwort:
    kennung = "frage_antwort"
    arten = frozenset({"frage_antwort"})
    darstellung = "lesedesign"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and (b'id="question"' in eintrag.inhalt
                                                          or b'class="question-summary"' in eintrag.inhalt
                                                          or b"js-tag-cell" in eintrag.inhalt)

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        h.stile_uebersetzen(doc)
        if doc.xpath("//div[contains(@class,'js-tag-cell')]"):
            return self._schlagwoerter(doc, buch, wege)
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
        beitrag, frage_beitrag = _beitrag(frage, "gefragt", buch, wege)
        stimmen_frage = frage_beitrag.stimmen
        abschnitt.append(beitrag)
        abschnitte = [Abschnitt(anker="frage", titel="Frage", ebene=2)]

        antworten = []
        for quelle in doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' answer ')]"):
            akzeptiert = "accepted-answer" in (quelle.get("class") or "")
            kasten, b = _beitrag(quelle, "beantwortet", buch, wege, akzeptiert)
            antworten.append((not akzeptiert, -b.stimmen, quelle.get("data-answerid") or "", kasten, b.stimmen, b.autor, akzeptiert, b))
        antworten.sort(key=lambda a: (a[0], a[1]))            # die akzeptierte zuerst, dann nach Stimmen
        if antworten:
            kopf_a = SubElement(wurzel, "div")
            kopf_a.set("class", "antworten-kopf")
            ueberschrift = SubElement(kopf_a, "h2")
            ueberschrift.set("id", "antworten")
            ueberschrift.text = f"{len(antworten)} {'Antwort' if len(antworten) == 1 else 'Antworten'}"
            abschnitte.append(Abschnitt(anker="antworten", titel=ueberschrift.text, ebene=2))
        for _, _, kennung, kasten, stimmen, wer, akzeptiert, _ in antworten:
            antwort = SubElement(wurzel, "div")
            antwort.set("class", "antwort akzeptiert" if akzeptiert else "antwort")
            antwort.set("id", f"antwort-{kennung}")
            antwort.append(kasten)
            abschnitte.append(Abschnitt(anker=f"antwort-{kennung}", titel=f"{_deutsche_zahl(str(stimmen))} · {wer or 'unbekannt'}",
                                        ebene=3))

        verweise, online = h.verweise_umschreiben(wurzel, buch.kennung, eintrag.pfad, wege)
        bild = h.bilder_umschreiben(wurzel, buch.kennung, eintrag.pfad, wege)
        h.saeubern(wurzel)
        einleitung = next((t for p in wurzel.iter("p") if len(t := h.text_von(p)) > 20), "")
        html = "".join(h.als_html(k) for k in wurzel)

        steckbrief = self._steckbrief(doc, buch, eintrag, wege, nummer, stimmen_frage, antworten, signaturen)
        marken = [h.text_von(a) for a in frage.xpath(".//a[contains(@class,'post-tag')]")]
        angaben = FrageAngaben(stimmen=stimmen_frage, antworten=len(antworten), akzeptiert=any(a[6] for a in antworten),
                               gefragt=frage_beitrag.datum, schlagwoerter=marken,
                               beitraege=[frage_beitrag, *(a[7] for a in antworten)])
        return Aufbereitet(titel=titel, html=html, einleitung=einleitung, abschnitte=abschnitte, steckbrief=steckbrief,
                           bild=bild, verweise=verweise, online=online, rubrik="Fragen", frage=angaben,
                           kategorien=_als_kategorien(marken, buch, wege))

    @staticmethod
    def _schlagwoerter(doc, buch: Buch, wege: Wege) -> Aufbereitet:
        """Die Übersicht der Schlagwörter als Kategorieseite: jedes Schlagwort eine Unterkategorie mit seinen Fragen."""
        karten = _schlagwortkarten(doc, buch, wege)
        einleitung = _text(doc, "//*[@id='mainbar-full']/p")
        beschreibung = lhtml.Element("p")
        beschreibung.text = einleitung
        return Aufbereitet(titel="Schlagwörter", html=h.als_html(beschreibung) if einleitung else "", einleitung=einleitung,
                           darstellung="kategorie", rubrik=f"Kategorie · {len(karten)} Schlagwörter",
                           kategorie=Kategorieangaben(unter=karten, einheit="Fragen"))

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
        # die Liste eines Schlagworts ist dessen Kategorie: darüber die Übersicht aller (für den Kategorienbaum)
        ist_schlagwort = eintrag.pfad.startswith(_schlagwortpfad(""))
        uebersicht = [Kategorieverweis(pfad=SCHLAGWORTSEITE, titel="Alle Schlagwörter")] if wege.gibt_es(buch.kennung, SCHLAGWORTSEITE) else []
        return Aufbereitet(titel=titel, fragen=fragen, darstellung="uebersicht", rubrik="Fragen",
                           zurueck=blaettern.get("zurueck", ""), weiter=blaettern.get("weiter", ""),
                           kategorien=_meistgenutzte(buch, wege),
                           kategorie=Kategorieangaben(ober=uebersicht) if ist_schlagwort else None)

    @staticmethod
    def _steckbrief(doc, buch: Buch, eintrag: Eintrag, wege: Wege, nummer: str, stimmen: int, antworten: list,
                    signaturen: dict[str, tuple[str, str]]) -> Steckbrief:
        """Steckbrief (Entwurf): Stimmen, Antworten, Gefragt, Bearbeitet, Schlagwörter, verwandte Fragen."""
        wurzel = lhtml.Element("div")
        werte = SubElement(wurzel, "dl")
        werte.set("class", "steckbrief-werte")
        akzeptiert = any(a[6] for a in antworten)
        zeilen = [("Stimmen", _deutsche_zahl(str(stimmen))),
                  ("Antworten", f"{len(antworten)}" + (", eine akzeptiert" if akzeptiert else "")),
                  ("Gefragt", " von ".join(x for x in signaturen["gefragt"][:2] if x) if "gefragt" in signaturen else ""),
                  ("Bearbeitet", signaturen["bearbeitet"].datum if "bearbeitet" in signaturen else "")]
        for name, wert in zeilen:
            if wert:
                SubElement(werte, "dt").text = name
                SubElement(werte, "dd").text = wert
        marken = [h.text_von(a) for a in doc.xpath("//*[@id='question']//a[contains(@class,'post-tag')]")]
        if marken:
            SubElement(wurzel, "div").set("class", "steckbrief-gruppe")
            wurzel[-1].text = "Schlagwörter"
            _schlagwoerter(wurzel, marken, buch, wege)
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
