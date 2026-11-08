"""Prüfung nach dem Umformen (WIKI-45): jede Zahl des Ergebnisses muss im Original stehen, jeder Absatz und jeder Punkt
braucht einen gültigen Beleg, und ein Satz, dessen Wörter in den belegten Absätzen kaum vorkommen, steht so nicht im
Original und wird markiert (nicht von selbst neu geschrieben; das bestimmt man im Probekapitel). Reine Umformung.

Zahlen werden in beiden Schreibweisen gelesen (120.500 und 120,5 auf Deutsch, 1,430 und 1.43 auf Englisch), damit auch
übersetzte Artikel passen. Die Wortprüfung vergleicht Wortstämme (die ersten Buchstaben längerer Wörter ohne
Füllwörter) und gilt nur, wenn das Original deutsch ist."""

from __future__ import annotations

import re

from ..modell.alsbuch import Absatz, Buchartikel, Buchkapitel, Glossareintrag, Kasten, Pruefung, Satzhinweis
from .quelle import Quelltext

ZAHL = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")
WORT = re.compile(r"[^\W\d_]+", re.UNICODE)
SATZENDE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9\"'(])")
#: Anteil der Wortstämme eines Satzes, der in den belegten Absätzen stehen muss
SCHWELLE = 0.5
#: Sätze mit weniger Inhaltswörtern prüft die Wortprüfung nicht (zu wenig, um etwas zu sagen)
MIN_WOERTER = 3
#: so viele Buchstaben bilden den Stamm eines Worts; kürzere Wörter zählen nicht
STAMM = 5
FUELLWOERTER = frozenset("""
aber alle allem allen aller alles also auch auf aus bald beim beide beiden bereits bevor dabei daher damit dann darum
dass davon dazu dein deine deinen deiner dem den denen denn der deren derer des deshalb dessen dich die dies diese
diesem diesen dieser dieses dir doch dort durch eben eher eigentlich eine einem einen einer eines einige einigen
einiger etwa etwas euch euer eure eurem euren eurer fast gegen ganz gern gibt habe haben hast hatte hatten hier hinter
ihnen ihre ihrem ihren ihrer ihres immer indem jede jedem jeden jeder jedes jedoch jene jenem jenen jener jenes kann
kaum kein keine keinem keinen keiner können könnte machen macht mehr mein meine meinem meinen meiner meist meisten
mich mittels muss musste nach nein nicht nichts noch nun nur ohne oder schon sehr sein seine seinem seinen seiner
seines selbst sich sie sind sogar solche solchen soll sollte sondern sowie über unter viel viele vielen vom von
voran vorher wann warum weil weiter welche welchem welchen welcher welches wenn werde werden wieder will wird wirklich
wobei wohl worden wurde wurden würde würden zudem zwar zwischen
""".split())


def zahlwerte(text: str) -> set[str]:
    """Die Werte aller Zahlen eines Texts in beiden Schreibweisen (Punkt und Komma als Tausender- oder Dezimalzeichen)."""
    werte: set[str] = set()
    for roh in ZAHL.findall(text):
        werte |= _lesarten(roh)
    return werte


def _lesarten(roh: str) -> set[str]:
    lesarten = {roh}
    for tausend, dezimal in ((".", ","), (",", ".")):
        teile = roh.split(dezimal)
        ganz = teile[0]
        if len(teile) > 2:
            continue
        gruppen = ganz.split(tausend)
        if len(gruppen) > 1 and not all(len(g) == 3 for g in gruppen[1:]):
            continue
        wert = "".join(gruppen) + ("." + teile[1] if len(teile) == 2 else "")
        if tausend not in (teile[1] if len(teile) == 2 else ""):
            lesarten.add(_ohne_nullen(wert))
    return lesarten


def _ohne_nullen(wert: str) -> str:
    ganz, _, rest = wert.partition(".")
    ganz = ganz.lstrip("0") or "0"
    rest = rest.rstrip("0")
    return f"{ganz}.{rest}" if rest else ganz


def _zahlen_im_text(text: str) -> list[tuple[str, set[str]]]:
    return [(roh, _lesarten(roh)) for roh in ZAHL.findall(text)]


def staemme(text: str) -> set[str]:
    return {w[:STAMM] for w in (x.casefold() for x in WORT.findall(text)) if len(w) >= 4 and w not in FUELLWOERTER}


def saetze(text: str) -> list[str]:
    return [s.strip() for s in SATZENDE.split(text.strip()) if s.strip()]


class _Pruefer:
    def __init__(self, q: Quelltext, artikel: str) -> None:
        self.q, self.artikel = q, artikel
        self.texte = {b.nr: b.text for b in q.absaetze}
        self.alle_zahlen = zahlwerte(" ".join(self.texte.values()))
        self.deutsch = q.sprache == "de"
        self.zahlen = self.zahlen_gefunden = self.stellen = self.belegt = 0
        self.hinweise: list[Satzhinweis] = []

    def _referenz(self, belege: list[int]) -> str:
        gueltig = [b for b in belege if b in self.texte]
        return " ".join(self.texte[b] for b in gueltig)

    def stelle(self, text: str, belege: list[int], absatz: int) -> list[str]:
        """Prüft einen Absatz oder Punkt; gibt die Sätze zurück, die so nicht im Original stehen."""
        self.stellen += 1
        referenz = self._referenz(belege)
        if referenz:
            self.belegt += 1
        else:
            self.hinweise.append(Satzhinweis(artikel=self.artikel, absatz=absatz, text=text[:200], art="beleg"))
        for roh, lesarten in _zahlen_im_text(text):
            self.zahlen += 1
            if lesarten & self.alle_zahlen:
                self.zahlen_gefunden += 1
            else:
                self.hinweise.append(Satzhinweis(artikel=self.artikel, absatz=absatz, text=roh, art="zahl"))
        if not (self.deutsch and referenz):
            return []
        bekannt = staemme(referenz)
        ohne = []
        for satz in saetze(text):
            eigene = staemme(satz)
            if len(eigene) >= MIN_WOERTER and len(eigene & bekannt) / len(eigene) < SCHWELLE:
                ohne.append(satz)
                self.hinweise.append(Satzhinweis(artikel=self.artikel, absatz=absatz, text=satz, art="satz"))
        return ohne

    def ergebnis(self) -> Pruefung:
        return Pruefung(zahlen=self.zahlen, zahlen_gefunden=self.zahlen_gefunden, absaetze=self.stellen, belegt=self.belegt,
                        hinweise=self.hinweise)


def pruefen(q: Quelltext, a: Buchartikel) -> tuple[Buchartikel, Pruefung]:
    """Prüft die umgeformten Teile eines Artikels gegen sein Original; der Text wie im Buch braucht keine Prüfung.
    Ergebnis: der Artikel mit markierten Sätzen (`ohne_beleg`) und die Zahlen der Prüfung."""
    p = _Pruefer(q, a.titel)
    absaetze: list[Absatz] = []
    for i, x in enumerate(a.absaetze):
        if x.html:                                       # Text wie im Buch
            absaetze.append(x)
            continue
        absaetze.append(x.model_copy(update={"ohne_beleg": p.stelle(x.text, x.belege, i)}))

    def kasten(k: Kasten | None) -> None:
        for punkt in (k.punkte if k else []):
            p.stelle(punkt.text, punkt.belege, -1)

    kasten(a.blick)
    for k in a.kaesten:
        kasten(k)
    return a.model_copy(update={"absaetze": absaetze}), p.ergebnis()


def zusammen(pruefungen: list[Pruefung]) -> Pruefung:
    """Mehrere Prüfungen (je Artikel) als eine."""
    return Pruefung(zahlen=sum(p.zahlen for p in pruefungen), zahlen_gefunden=sum(p.zahlen_gefunden for p in pruefungen),
                    absaetze=sum(p.absaetze for p in pruefungen), belegt=sum(p.belegt for p in pruefungen),
                    hinweise=[h for p in pruefungen for h in p.hinweise])


def kapitel_pruefen(k: Buchkapitel, text: str) -> list[Satzhinweis]:
    """Einleitung und Antworten eines Kapitels gegen seinen umgeformten Text: jede Zahl muss darin stehen."""
    werte = zahlwerte(text)
    hinweise = []
    for satz in [s.text for s in k.einleitung] + [f.antwort for f in k.fragen]:
        for roh, lesarten in _zahlen_im_text(satz):
            if not lesarten & werte:
                hinweise.append(Satzhinweis(artikel=k.titel, absatz=-1, text=roh, art="zahl"))
    return hinweise


def glossar_im_text(eintraege: list[Glossareintrag], text: str) -> list[Glossareintrag]:
    """Nur Begriffe, die im Text des Kapitels vorkommen (in irgendeiner Schreibung)."""
    klein = text.casefold()
    return [g for g in eintraege if g.begriff.casefold() in klein]
