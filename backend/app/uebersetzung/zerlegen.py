"""Einen Artikel zum Übersetzen zerlegen und wieder zusammensetzen (WIKI-8). Struktur und Daten bleiben getrennt: ans
Modell geht nur Text, je Textlauf (Absatz, Listenpunkt, Überschrift, Zelle) eine Vorlage. Darin stehen Auszeichnungen
als nummerierte Marken (<t1>...</t1>) und alles Unantastbare (Code, Formeln, Bilder, Belegmarken) als Platzhalter
(<x2/>), dessen Inhalt nie zum Modell geht. Eingesetzt wird eine Übersetzung nur, wenn sie die Prüfung besteht: dieselben
Marken an denselben Stellen der Schachtelung und dieselben Zahlen. Sonst bleibt der Lauf im Original."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from html import escape, unescape

#: Auszeichnungen im Fließtext: ihr Text wird übersetzt, die Auszeichnung bleibt
INLINE = {"a", "abbr", "b", "bdi", "bdo", "cite", "dfn", "em", "i", "mark", "q", "s", "small", "span", "strong", "sub",
          "sup", "u", "time", "data", "del", "ins"}
#: Unantastbar im Fließtext: geht als Platzhalter durch und kommt unverändert zurück
ATOM = {"code", "kbd", "samp", "var", "tt", "math", "img", "svg", "br", "wbr", "input", "button"}
ATOM_KLASSEN = {"beleg", "ort", "name", "typ", "var"}
#: Ganze Teile, die nie übersetzt werden: Code, Formeln, Signaturen, Namen und Daten der Beiträge
NIE = {"pre", "code", "script", "style", "math", "svg", "template"}
NIE_KLASSEN = {"formel", "signatur", "codeblock", "ausgabe", "beitrag-fuss", "schlagwoerter", "qa-stimmen", "steckbrief-bild",
               "versionen"}

MARKE = re.compile(r"<(/?)t(\d+)>|<x(\d+)/>")
ZAHL = re.compile(r"\d+")
BUCHSTABE = re.compile(r"[^\W\d_]")


def _tag(el) -> str:
    return el.tag if isinstance(el.tag, str) else ""


def _klassen(el) -> set[str]:
    return set((el.get("class") or "").split()) if _tag(el) else set()


def _nie(el) -> bool:
    return _tag(el) in NIE or bool(_klassen(el) & NIE_KLASSEN) or el.get("translate") == "no"


def _atom(el) -> bool:
    """Kommentare und Unantastbares: Platzhalter."""
    return not _tag(el) or _tag(el) in ATOM or bool(_klassen(el) & ATOM_KLASSEN) or el.get("translate") == "no"


def _fliesstext(el) -> bool:
    """Gehört zum Textlauf: ein Platzhalter oder eine Auszeichnung, die nur Fließtext enthält."""
    if _atom(el):
        return True
    return _tag(el) in INLINE and all(_tag(k) in INLINE or _atom(k) for k in el.iterdescendants())


def _text(text: str | None) -> str:
    return escape(re.sub(r"\s+", " ", text or ""), quote=False)


@dataclass
class Lauf:
    """Ein Textlauf in `eltern`: der Text am Anfang (der Text von `eltern`, wenn `vor` None ist, sonst der Schwanz des
    Blocks `vor`) und die Auszeichnungen dahinter, bis zum nächsten Block."""
    eltern: object
    vor: object | None
    kinder: list = field(default_factory=list)
    vorlage: str = ""
    teile: dict[int, object] = field(default_factory=dict)       # Nummer der Marke -> Element im Original
    eltern_von: dict[int, int] = field(default_factory=dict)     # Nummer -> Nummer der umgebenden Marke (0: keine)
    rand_vorn: str = ""
    rand_hinten: str = ""

    def bauen(self, start: str | None) -> None:
        n = 0

        def innen(kinder, oben: int) -> str:
            nonlocal n
            s = ""
            for k in kinder:
                n += 1
                nr = n                   # n zählt in der Tiefe weiter, die Marke schließt mit ihrer eigenen Nummer
                self.teile[nr], self.eltern_von[nr] = k, oben
                s += f"<x{nr}/>" if _atom(k) else f"<t{nr}>{_text(k.text)}{innen(list(k), nr)}</t{nr}>"
                s += _text(k.tail)
            return s

        roh = _text(start) + innen(self.kinder, 0)
        self.rand_vorn = " " if roh.startswith(" ") else ""
        self.rand_hinten = " " if roh.endswith(" ") and roh.strip() else ""
        self.vorlage = roh.strip()


def laeufe(wurzel) -> list[Lauf]:
    """Alle Textläufe mit Buchstaben darin, in der Reihenfolge des Texts; Teile, die nie übersetzt werden, bleiben aus."""
    gefunden: list[Lauf] = []

    def abschliessen(lauf: Lauf, start: str | None) -> None:
        lauf.bauen(start)
        if BUCHSTABE.search(unescape(MARKE.sub(" ", lauf.vorlage))):
            gefunden.append(lauf)

    def besuchen(el) -> None:
        if _nie(el):
            return
        lauf, start = Lauf(eltern=el, vor=None), el.text
        for k in list(el):
            if _fliesstext(k):
                lauf.kinder.append(k)
                continue
            abschliessen(lauf, start)
            besuchen(k)
            lauf, start = Lauf(eltern=el, vor=k), k.tail
        abschliessen(lauf, start)

    besuchen(wurzel)
    return gefunden


class Abgelehnt(ValueError):
    """Die Übersetzung eines Laufs besteht die Prüfung nicht; der Lauf bleibt im Original."""


def _zahlen(vorlage: str) -> list[str]:
    return sorted(ZAHL.findall(unescape(MARKE.sub(" ", vorlage))))


def _lesen(lauf: Lauf, uebersetzt: str) -> list:
    """Die Übersetzung als Baum: Text (str), ("t", n, Kinder) oder ("x", n). Wirft `Abgelehnt`, wenn Marken fehlen, fremd,
    doppelt, falsch geschachtelt oder vertauscht sind, oder wenn die Zahlen abweichen."""
    if "<" in MARKE.sub("", uebersetzt):
        raise Abgelehnt("fremde Auszeichnung")
    wurzel: list = []
    stapel: list[tuple[int, list]] = [(0, wurzel)]
    gesehen: dict[int, int] = {}
    pos = 0
    for m in MARKE.finditer(uebersetzt):
        if m.start() > pos:
            stapel[-1][1].append(uebersetzt[pos:m.start()])
        pos = m.end()
        zu, t, x = m.group(1), m.group(2), m.group(3)
        n = int(t or x)
        if n not in lauf.teile:
            raise Abgelehnt(f"unbekannte Marke {n}")
        if zu:
            if stapel[-1][0] != n:
                raise Abgelehnt(f"Marke {n} falsch geschlossen")
            stapel.pop()
            continue
        if n in gesehen:
            raise Abgelehnt(f"Marke {n} doppelt")
        if bool(x) != _atom(lauf.teile[n]):
            raise Abgelehnt(f"Marke {n} vertauscht")
        gesehen[n] = stapel[-1][0]
        if x:
            stapel[-1][1].append(("x", n))
        else:
            kinder: list = []
            stapel[-1][1].append(("t", n, kinder))
            stapel.append((n, kinder))
    if pos < len(uebersetzt):
        stapel[-1][1].append(uebersetzt[pos:])
    if len(stapel) != 1:
        raise Abgelehnt("Marke nicht geschlossen")
    if gesehen != lauf.eltern_von:
        raise Abgelehnt("Marken fehlen oder sind anders geschachtelt")
    if _zahlen(uebersetzt) != _zahlen(lauf.vorlage):
        raise Abgelehnt("Zahlen weichen ab")
    return wurzel


def _elemente(lauf: Lauf, knoten: list) -> tuple[str, list]:
    """Text vor dem ersten Element und die Elemente (mit ihren Schwänzen): Auszeichnungen als flache Kopien mit dem
    neuen Text, Platzhalter als das unveränderte Original."""
    vorn, elemente = "", []
    for k in knoten:
        if isinstance(k, str):
            if elemente:
                elemente[-1].tail = (elemente[-1].tail or "") + unescape(k)
            else:
                vorn += unescape(k)
            continue
        original = lauf.teile[k[1]]
        if k[0] == "x":
            el = copy.deepcopy(original)
            el.tail = None
        else:
            el = original.makeelement(original.tag, dict(original.attrib))
            el.text, innen = _elemente(lauf, k[2])
            el.extend(innen)
        elemente.append(el)
    return vorn, elemente


def pruefen(lauf: Lauf, uebersetzt: str) -> None:
    _lesen(lauf, re.sub(r"\s+", " ", uebersetzt).strip())


def einsetzen(lauf: Lauf, uebersetzt: str) -> None:
    """Die Übersetzung prüfen und an die Stelle des Laufs setzen; `Abgelehnt` lässt das Original unberührt."""
    vorn, neu = _elemente(lauf, _lesen(lauf, re.sub(r"\s+", " ", uebersetzt).strip()))
    vorn = lauf.rand_vorn + vorn
    if neu:
        neu[-1].tail = (neu[-1].tail or "") + lauf.rand_hinten
    else:
        vorn += lauf.rand_hinten
    eltern = lauf.eltern
    if lauf.kinder:
        stelle = eltern.index(lauf.kinder[0])
        for k in lauf.kinder:
            eltern.remove(k)
    else:
        stelle = eltern.index(lauf.vor) + 1 if lauf.vor is not None else 0
    if lauf.vor is None:
        eltern.text = vorn
    else:
        lauf.vor.tail = vorn
    for i, k in enumerate(neu):
        eltern.insert(stelle + i, k)
