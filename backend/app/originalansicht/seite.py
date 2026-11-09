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


#: abgeschirmt ohne eigene Herkunft (kein allow-same-origin): Skripte, Formulare, neue Fenster und Hinweisfenster
#: dürfen sein, die Seite oben im Browser wechseln nie. Dieselben Rechte trägt der Rahmen in der App
SANDBOX = "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads"


def inhaltsregeln(anfrage: URL) -> str:
    """Die Seite läuft abgeschirmt ohne eigene Herkunft (auch allein geöffnet), lädt und verbindet sich nur mit den
    Wegen der Originalseiten (nicht mit der Schnittstelle der App, nichts nach außen), Skripte des Buchs laufen, wie
    sie sind, und einbetten darf sie nur die App."""
    wege = f"{anfrage.scheme}://{anfrage.netloc}{PRAEFIX}/"
    return "; ".join([
        f"sandbox {SANDBOX}",
        f"default-src {wege} data: blob:",
        f"script-src {wege} 'unsafe-inline' 'unsafe-eval' blob:",
        f"style-src {wege} 'unsafe-inline'",
        f"img-src {wege} data: blob:",
        f"media-src {wege} data: blob:",
        f"font-src {wege} data:",
        f"connect-src {wege} data: blob:",
        f"worker-src {wege} blob:",
        f"frame-src {wege} data: blob:",
        "object-src 'none'",
        f"base-uri {wege}",
        f"form-action {wege}",
        "frame-ancestors 'self'",
    ])
