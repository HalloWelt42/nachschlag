"""Artikel für heute (WIKI-7, Startseite B): aus den eigenen Themen ein Artikel, der noch nicht zu Ende gelesen ist, mit
dem Grund der Wahl. Jeden Tag ein anderer, am selben Tag derselbe: die Wahl hängt an Konto und Datum, nicht am Zufall."""

from __future__ import annotations

import hashlib
from datetime import date

from pydantic import BaseModel

from ..artikel import Artikelleser
from ..bibliothek import BuchFehlt, EintragFehlt
from ..modell.themen import Themeneintrag
from .speicher import Themen

#: so weit gelesen gilt ein Artikel als fertig (wie Weiterlesen auf der Startseite)
FERTIG_AB = 0.95


class Heute(BaseModel):
    buch: str
    pfad: str
    titel: str
    bild: str = ""
    einleitung: str = ""
    thema_id: str
    thema: str
    grund: str


def grund(thema: str, e: Themeneintrag) -> str:
    if e.anteil > 0:
        return f'Aus deinem Thema "{thema}", zu {round(e.anteil * 100)} % gelesen'
    if e.gelesen_je:
        return f'Aus deinem Thema "{thema}", schon einmal geöffnet'
    return f'Aus deinem Thema "{thema}", noch nicht gelesen'


async def artikel_fuer_heute(themen: Themen, konto: str, leser: Artikelleser, tag: date) -> Heute | None:
    """Ohne Thema mit offenen Artikeln nichts (die Startseite sagt dann, wie man eins anlegt)."""
    kandidaten = []
    for kopf in await themen.liste(konto):
        t = await themen.thema(konto, kopf.id)
        if t is not None:
            kandidaten += [(t, e) for e in t.eintraege if e.buch and e.anteil < FERTIG_AB]
    if not kandidaten:
        return None
    kandidaten.sort(key=lambda k: (k[0].id, k[1].id))
    t, e = kandidaten[int(hashlib.sha256(f"{konto}:{tag.isoformat()}".encode()).hexdigest(), 16) % len(kandidaten)]
    einleitung, bild = "", e.bild
    try:
        a = await leser.lesen(e.buch, e.pfad)
        einleitung, bild = a.einleitung, bild or a.bild
    except (BuchFehlt, EintragFehlt):
        pass                                   # die Quelle fehlt gerade: ohne Auszug, der Titel genügt
    return Heute(buch=e.buch, pfad=e.pfad, titel=e.titel, bild=bild, einleitung=einleitung, thema_id=t.id, thema=t.titel,
                 grund=grund(t.titel, e))
