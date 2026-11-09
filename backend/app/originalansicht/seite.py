"""Was eine Originalseite auf ihrem Weg mitbekommt (WIKI-85): die Brücke und die Inhaltsregeln."""

from __future__ import annotations

import re

from starlette.datastructures import URL

from .herkunft import PRAEFIX

#: die Brücke als erstes Skript der Seite (verzögert: läuft nach dem Lesen der Seite, vor den Skripten des Buchs)
BRUECKE_TAG = f'<script src="{PRAEFIX}/bruecke.js" defer></script>'.encode()
_KOPF = re.compile(rb"<head(?:\s[^>]*)?>", re.I)
_HTML = re.compile(rb"<html(?:\s[^>]*)?>", re.I)


def bruecke_einsetzen(html: bytes) -> bytes:
    """Setzt die Brücke an den Anfang des Kopfs (ohne Kopf: nach <html>, sonst ganz vorn); sonst bleibt alles, wie es
    im Buch steht."""
    for muster in (_KOPF, _HTML):
        if treffer := muster.search(html):
            return html[:treffer.end()] + BRUECKE_TAG + html[treffer.end():]
    return BRUECKE_TAG + html


def inhaltsregeln(anfrage: URL) -> str:
    """Die Seite lädt und verbindet sich nur mit ihrer eigenen Herkunft (nichts nach außen), Skripte des Buchs laufen,
    wie sie sind, und einbetten dürfen sie nur Seiten desselben Rechners (die App, gleich auf welchem Port)."""
    rechner = f"{anfrage.scheme}://{anfrage.hostname}:*"
    return "; ".join([
        "default-src 'self' data: blob:",
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data: blob:",
        "media-src 'self' data: blob:",
        "font-src 'self' data:",
        "connect-src 'self' data: blob:",
        "worker-src 'self' blob:",
        "frame-src 'self' data: blob:",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        f"frame-ancestors 'self' {rechner}",
    ])
