"""Sprache eines Texts bestimmen, wo die Quelle sie nicht verlässlich nennt (iFixit: alle Seiten tragen lang=fr, der Inhalt
ist deutsch oder englisch; WIKI-64). Nach häufigen kleinen Wörtern; zu wenig Text heißt unbekannt."""

from __future__ import annotations

import re

#: häufige kleine Wörter je Sprache (in der Stichprobe von 1.500 Anleitungen eindeutig getrennt)
WOERTER = {
    "de": frozenset("der die das und ist nicht mit den sie du dein deine auf für von zu ein eine einen wenn kann werden "
                    "wird oder sich es aus bei dem im".split()),
    "en": frozenset("the and is not with to you your on for of a an if can be will or it from at this that remove".split()),
}
MINDESTENS = 5
VORSPRUNG = 1.5


def sprache_von(text: str) -> str:
    """de, en oder leer (zu wenig Text oder kein klarer Vorsprung)."""
    woerter = re.findall(r"[a-zäöüß]+", text.lower())
    zahl = {s: sum(w in liste for w in woerter) for s, liste in WOERTER.items()}
    de, en = zahl["de"], zahl["en"]
    if de >= MINDESTENS and de > en * VORSPRUNG:
        return "de"
    if en >= MINDESTENS and en > de * VORSPRUNG:
        return "en"
    return ""
