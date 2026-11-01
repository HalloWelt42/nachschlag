"""Die Angaben einer Seite für eine Quellenangabe: Titel, die Quelle mit ihrem Stand, die Adresse im Netz und, wo die
Quelle es nennt (Frage und Antwort), wer die Seite verfasst hat und wann."""

from __future__ import annotations

from ..modell.artikel import Artikel
from ..modell.buch import Buch
from .formen import Zitierangaben


def zitierangaben(buch: Buch, titel: str, url: str, autor: str = "", datum: str = "") -> Zitierangaben:
    return Zitierangaben(titel=titel, quelle=buch.titel, stand=buch.stand, url=url, autor=autor, datum=datum)


def aus_artikel(buch: Buch, a: Artikel) -> Zitierangaben:
    return zitierangaben(buch, a.titel, a.quelle_url, a.autor, a.datum)
