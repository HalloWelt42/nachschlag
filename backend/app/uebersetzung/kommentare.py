"""Kommentare im Code übersetzen (WIKI-8, Nutzer: eigens behandelt, je Codeabschnitt umschaltbar). Der Code selbst bleibt
immer Zeichen für Zeichen; übersetzt wird nur der Text eines Kommentars, ohne seine Kommentarzeichen, Zeile für Zeile.
Das Ergebnis sind Paare aus Original und Übersetzung je Codeabschnitt; die Oberfläche tauscht sie im gezeigten Code,
wenn man den Abschnitt umschaltet.

Erkannt werden Kommentare an den Marken der Bausteine (span.c-kom, Dokumentation), sonst mit dem Lexer der Sprache
(Pygments; die Sprache aus den Schlagwörtern einer Frage oder dem Namen des Buchs). Ohne bekannte Sprache nur
Zeilenkommentare, die eine Zeile beginnen (// oder #): lieber ein Kommentar zu wenig als Code für Text gehalten."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pygments.lexers import get_lexer_by_name
from pygments.token import Comment
from pygments.util import ClassNotFound

#: Anfang und Ende eines Kommentars, die zum Code gehören (bleiben stehen): Zeichen, Sterne am Zeilenanfang, Leerraum
VORN = re.compile(r"^(\s*(?://+|#+|--|;+|\"|/\*+|\*+|<!--)?\s*)")
HINTEN = re.compile(r"(\s*(?:\*+/|-->)?\s*)$")
BUCHSTABE = re.compile(r"[^\W\d_]{2,}")
#: Teile eines Kommentars, die Bezeichner oder Werte sind und unverändert bleiben müssen
FEST = re.compile(r"`[^`]+`|[$@][A-Za-z_]\w*|\b\w+\(\)|\b[a-z]+_[a-z_0-9]+\b|\b[a-z]+[A-Z]\w*\b|\b\d+(?:[.,]\d+)?\b")
#: Sprachen aus Schlagwörtern, die Pygments anders nennt
SPRACHE_ALIAS = {"vimscript": "vim", "vimrc": "vim", "shell": "bash", "sh": "bash", "js": "javascript", "node.js": "javascript",
                 "c#": "csharp", "c++": "cpp", "golang": "go", "postgresql": "postgresql", "mysql": "mysql"}


@dataclass(frozen=True)
class Kommentarzeile:
    block: int          # Nummer des Codeabschnitts (pre) im Artikel
    original: str       # die ganze Zeile des Kommentars, wie sie im Code steht (mit Zeichen)
    vorn: str
    inhalt: str         # was übersetzt wird
    hinten: str

    def mit(self, uebersetzt: str) -> str:
        return self.vorn + uebersetzt.strip() + self.hinten


def _zeilen(block: int, kommentar: str) -> list[Kommentarzeile]:
    aus = []
    for zeile in kommentar.split("\n"):
        vorn = VORN.match(zeile).group(1)
        rest = zeile[len(vorn):]
        hinten = HINTEN.search(rest).group(1)
        inhalt = rest[: len(rest) - len(hinten)] if hinten else rest
        if BUCHSTABE.search(inhalt):
            aus.append(Kommentarzeile(block=block, original=zeile, vorn=vorn, inhalt=inhalt, hinten=hinten))
    return aus


def _lexer(sprache: str):
    name = SPRACHE_ALIAS.get(sprache.lower(), sprache.lower())
    try:
        return get_lexer_by_name(name, stripnl=False, ensurenl=False)
    except ClassNotFound:
        return None


def sprache_aus(hinweise: list[str]) -> str:
    """Die erste Sprache, die Pygments kennt (Schlagwörter einer Frage, Name des Buchs)."""
    for h in hinweise:
        for teil in re.split(r"[\s_/]+", h.lower()):
            if teil and _lexer(teil) is not None:
                return teil
    return ""


def kommentare(pres: list, sprache: str) -> list[Kommentarzeile]:
    """Die Kommentarzeilen aller Codeabschnitte (pre), in der Reihenfolge des Artikels."""
    lexer = _lexer(sprache) if sprache else None
    aus: list[Kommentarzeile] = []
    for nr, pre in enumerate(pres):
        marken = pre.xpath(".//span[contains(concat(' ', normalize-space(@class), ' '), ' c-kom ')]")
        if marken:
            texte = [m.text_content() for m in marken]
        elif lexer is not None:
            texte = [wert for art, wert in lexer.get_tokens(pre.text_content()) if art in Comment and art not in Comment.Preproc]
            texte = _verbinden(texte)
        else:
            texte = [m.group(0).strip() for m in re.finditer(r"(?m)^[ \t]*(?://|#(?![!\[]))[^\n]*", pre.text_content())]
        for t in texte:
            aus += _zeilen(nr, t)
    return aus


def _verbinden(teile: list[str]) -> list[str]:
    """Pygments liefert Zeilenkommentare oft mit dem Zeilenende als eigenem Stück: zu ganzen Kommentaren fügen."""
    aus: list[str] = []
    for t in teile:
        if aus and not aus[-1].endswith("\n") and t.strip() == "":
            aus[-1] += t
        elif t.strip():
            aus.append(t.rstrip("\n"))
    return aus


class Verfaelscht(ValueError):
    """Die Übersetzung eines Kommentars ändert Bezeichner, Werte oder Zahlen; der Kommentar bleibt im Original."""


def pruefen(zeile: Kommentarzeile, uebersetzt: str) -> None:
    text = uebersetzt.strip()
    if not text or "\n" in text:
        raise Verfaelscht("leer oder mehrzeilig")
    fehlt = [f for f in FEST.findall(zeile.inhalt) if f not in text]
    if fehlt:
        raise Verfaelscht(f"verändert: {', '.join(fehlt[:3])}")
