"""Index-Dienst auf dem Mac starten (ein Teil von Nachschlag im Stellwerk; rechnet, hält kein Modell):

    cd backend && .venv/bin/python -m app.indexdienst

Einstellungen aus der Umgebung (Adressen im eigenen Netz und der Schlüssel stehen nie im Repo):
    NACHSCHLAG_INDEX_PI          Adresse von Nachschlag auf dem Pi (https://...)
    NACHSCHLAG_INDEX_SCHLUESSEL  Schlüssel des Index-Dienstes, derselbe wie in den Einstellungen von Nachschlag
    NACHSCHLAG_INDEX_BUECHER     Ordner der eingehängten Freigabe mit den ZIM-Libs (nur lesend)
    NACHSCHLAG_INDEX_ZIEL        Ordner der gebauten Indizes auf dem Mac
    NACHSCHLAG_INDEX_FREIGABE    Freigabe zum Neueinhängen nach einem Netzwechsel (//guest@rechner/name), wahlweise
Das Zertifikat des Pi prüft die Hausstelle dieses Rechners."""

from __future__ import annotations

import logging
import os
import signal
import threading
from pathlib import Path

import httpx

from appkern.app.geruest import hausstelle

from .arbeiter import Arbeiter, einhaengen_mit


def _wert(name: str) -> str:
    wert = os.environ.get(name, "")
    if not wert:
        raise SystemExit(f"{name} fehlt in der Umgebung")
    return wert


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    buecher = Path(_wert("NACHSCHLAG_INDEX_BUECHER")).expanduser()
    ziel = Path(_wert("NACHSCHLAG_INDEX_ZIEL")).expanduser()
    freigabe = os.environ.get("NACHSCHLAG_INDEX_FREIGABE", "")
    einhaengen = einhaengen_mit(freigabe, buecher) if freigabe else None
    if einhaengen:
        einhaengen()
    stelle = hausstelle()
    pi = httpx.Client(base_url=_wert("NACHSCHLAG_INDEX_PI").rstrip("/"), verify=str(stelle) if stelle else True,
                      headers={"Authorization": f"Bearer {_wert('NACHSCHLAG_INDEX_SCHLUESSEL')}"},
                      timeout=httpx.Timeout(15.0, write=120.0))
    halt = threading.Event()
    for zeichen in (signal.SIGTERM, signal.SIGINT):
        signal.signal(zeichen, lambda *_: halt.set())
    logging.getLogger("nachschlag.indexdienst").info("Index-Dienst läuft: Bücher %s, Indizes %s", buecher, ziel)
    with pi:
        Arbeiter(pi, buecher, ziel, einhaengen).laufen(halt)


if __name__ == "__main__":
    main()
