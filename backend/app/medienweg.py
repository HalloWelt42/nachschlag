"""Bildadressen gespeicherter Einträge (Merkzettel, Verlauf, Notizen, Themen) auf die heutige Fassung eines Buchs.

Gespeichert wird die Adresse von damals (/api/v1/inhalt/medien/<Kennung>/<Pfad>); nach dem Umschalten auf eine neue
Fassung gibt es die alte Kennung nicht mehr, und das Bild antwortete 404 (WIKI-97). Beim Lesen zeigt die Adresse darum auf
die Fassung, die heute zum Namen gehört; gibt es das Buch nicht mehr, bleibt das Bild leer."""

from __future__ import annotations

from urllib.parse import quote

MEDIEN = "/api/v1/inhalt/medien/"


def bild_heute(bild: str, kennung: str) -> str:
    if not bild.startswith(MEDIEN):
        return bild
    if not kennung:
        return ""
    _, _, pfad = bild[len(MEDIEN):].partition("/")
    return f"{MEDIEN}{quote(kennung)}/{pfad}" if pfad else ""
