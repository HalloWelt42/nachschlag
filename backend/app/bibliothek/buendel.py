"""Bündel (WIKI-83): Bücher derselben Herkunft, die zusammen ein Werk sind, erscheinen in jeder Bücherliste als eine
Ebene statt einzeln. Erkannt am Namen der Bücher (`<familie>_<sprache>_<thema>`, etwa freecodecamp_de_rosetta-code), nur
für Übungen (Wunsch des Nutzers: die Übungsbücher von freeCodeCamp) und nur unter den aktiven Quellen; ein Bündel braucht
mindestens zwei Bücher. Das Buch mit dem Thema `all` ist das Gesamtbuch: die Ebene öffnet es (Entscheidung des Nutzers),
darunter stehen die übrigen als Themen. Das Gesamtbuch enthält alle Themen: in Suche, Stöbern und Zählung gehen die
Themen darum nicht noch einmal ein (`buendel_im_gesamt`), sonst stünde jede Aufgabe doppelt da. Eine Regel für Lesen,
Suche, Stöbern und Bibliothek; die Oberfläche ordnet nur."""

from __future__ import annotations

import re
from collections import defaultdict

from ..modell.buch import Buch

NAME = re.compile(r"^(?P<familie>[a-z0-9]+)_(?P<sprache>[a-z]{2,3})_(?P<thema>[a-z0-9][a-z0-9_-]*)$")
ARTEN = frozenset({"uebung"})
GESAMT = "all"


def _schluessel(b: Buch) -> str | None:
    m = NAME.match(b.name)
    return f"{m['familie']}_{m['sprache']}" if m and b.art in ARTEN and b.archiv is None else None


def buendeln(buecher: list[Buch]) -> list[Buch]:
    """Dieselben Bücher in derselben Reihenfolge, Mitglieder eines Bündels mit Kennung, Titel und Rolle."""
    gruppen: dict[str, list[Buch]] = defaultdict(list)
    for b in buecher:
        if (s := _schluessel(b)) is not None:
            gruppen[s].append(b)
    angaben: dict[str, dict] = {}
    for s, mitglieder in gruppen.items():
        if len(mitglieder) < 2:
            continue
        gesamt = next((b for b in mitglieder if b.name.endswith(f"_{GESAMT}")), None)
        titel = gesamt.titel if gesamt else s.split("_")[0].capitalize()
        for b in mitglieder:
            angaben[b.kennung] = {"buendel": s, "buendel_titel": titel, "buendel_gesamt": b is gesamt,
                                  "buendel_im_gesamt": gesamt is not None and b is not gesamt}
    return [b.model_copy(update=angaben[b.kennung]) if b.kennung in angaben else b for b in buecher]
