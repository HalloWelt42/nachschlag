"""Bildholer starten (im Container: `python -m bildholer`):

    BILDHOLER_DATEN    Ordner für Warteschlange und Regeln (Vorgabe /daten)
    BILDHOLER_ABLAGE   Ordner der großen Bilder, den Nachschlag nur lesend einhängt (Vorgabe /bilder)
    BILDHOLER_PORT     Port im eigenen Netz der Container (Vorgabe 8000)"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import uvicorn

from .api import app_bauen


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    app = app_bauen(Path(os.environ.get("BILDHOLER_DATEN", "/daten")), Path(os.environ.get("BILDHOLER_ABLAGE", "/bilder")))
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("BILDHOLER_PORT", "8000")), log_level="warning")


if __name__ == "__main__":
    main()
