"""Baustein Übersicht: Seiten aus Kacheln (Erzeuger mwoffliner baut so die Startseite eines Buchs, `body.article-list-
home` mit `a.item > figure > img + figcaption`). Die Quelle ordnet die Kacheln per Skript an und zeigt ohne Skript nur
lückenhaft; Nachschlag liest die Einträge aus und setzt sie selbst als Karten (Entwurf start-a.html, Reihe aus Karten)."""

from __future__ import annotations

from lxml import html as lhtml

from ..bibliothek import Eintrag
from ..modell.artikel import Kachel
from ..modell.buch import Buch
from . import html as h
from .basis import Aufbereitet, Wege

KENNZEICHEN = b"article-list-home"


class Uebersicht:
    kennung = "uebersicht"
    arten = frozenset({"enzyklopaedie"})
    darstellung = "uebersicht"

    def passt(self, eintrag: Eintrag) -> bool:
        return eintrag.mime.startswith("text/html") and KENNZEICHEN in eintrag.inhalt[:4096]

    def aufbereiten(self, buch: Buch, eintrag: Eintrag, wege: Wege) -> Aufbereitet:
        doc = lhtml.fromstring(eintrag.inhalt.decode("utf-8", "replace"))
        kacheln: list[Kachel] = []
        for a in doc.xpath("//a[contains(concat(' ', normalize-space(@class), ' '), ' item ')]"):
            ziel = h.ziel_im_buch(eintrag.pfad, a.get("href") or "")
            if not ziel or not wege.gibt_es(buch.kennung, ziel):
                continue
            unter = next(iter(a.iter("figcaption")), None)
            titel = h.text_von(unter) if unter is not None else h.text_von(a)
            img = next(iter(a.iter("img")), None)
            src = (img.get("src") or "") if img is not None else ""
            bild = wege.medien(buch.kennung, h.ziel_im_buch(eintrag.pfad, src)) if src and not h.ist_online(src) else ""
            kacheln.append(Kachel(pfad=ziel, titel=titel or ziel.replace("_", " "), bild=bild))
        return Aufbereitet(titel=buch.titel, kacheln=kacheln, bild=kacheln[0].bild if kacheln else "")
