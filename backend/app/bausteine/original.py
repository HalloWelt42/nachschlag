"""Baustein Originalansicht: der Rückfall für jedes Buch ohne eigenes Lesedesign. Die Seite bleibt unverändert und
öffnet in einem abgeschirmten Rahmen; Nachschlag liest nur Titel und Einleitung für Listen und Vorschauen."""

from __future__ import annotations

from lxml import html as lhtml

from ..bibliothek import Eintrag
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege


class Originalansicht:
    kennung = "original"
    arten = frozenset({"dokumentation", "frage_antwort", "webseite", "sonstiges"})
    darstellung = "original"

    def passt(self, eintrag: Eintrag) -> bool:
        return True                      # zeigt jede Seite, so wie sie ist

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        titel, einleitung = eintrag.titel, ""
        if eintrag.mime.startswith("text/html"):
            doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace") or "<html></html>")
            kopf = next(iter(doc.xpath("//h1")), None)
            titel = h.text_von(kopf) if kopf is not None and h.text_von(kopf) else titel
            einleitung = " ".join(t for p in doc.xpath("//p") if len(t := h.text_von(p)) > 40)[:600]
        return Aufbereitet(titel=titel, einleitung=einleitung)
