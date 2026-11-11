"""Echte Zufallsfunde aus den Probebüchern für die Entwürfe (WIKI-89): Titel, Auszug, Buch, Bild, Buchsymbol, nach
mockups/kacheln/daten/ (nicht im Repo: Bilder und Symbole fremder Bücher). Aufruf aus backend/:

    .venv/bin/python ../mockups/kacheln/funde_ziehen.py
"""
import asyncio
import json
import random
import re
import sys
from urllib.parse import unquote
from pathlib import Path
sys.path.insert(0, str(Path.home() / "Entwicklung/Werkzeuge/nachschlag/backend"))
from app.artikel import Artikelleser
from app.bibliothek import Bibliothek

ZIEL = Path.home() / "Entwicklung/Werkzeuge/nachschlag/mockups/kacheln/daten"
BUECHER = Path.home() / "Entwicklung/Werkzeuge/nachschlag/daten-probe/buecher"

async def main():
    random.seed(11)
    bib = Bibliothek(lambda: str(BUECHER)); leser = Artikelleser(bib)
    stand = await bib.stand()
    funde = []
    for b in stand.buecher:
        if not b.faehigkeiten.lesedesign or b.kennung.startswith(("probe", "dateiformate_de_all_2026-11")) and "11-11" not in b.kennung:
            continue
        symbol = ""
        if b.symbol:
            (ZIEL / f"{b.kennung}.png").write_bytes(await bib.symbol(b.kennung)); symbol = f"daten/{b.kennung}.png"
        gefunden = 0
        for _ in range(40):
            if gefunden >= (3 if b.medien > 50 else 1):
                break
            try:
                pfad = await leser.zufall(b.kennung); a = await leser.lesen(b.kennung, pfad)
            except Exception:
                continue
            if not a.einleitung or len(a.einleitung) < 60:
                continue
            bild = ""
            if a.bild:
                m = re.match(r"/api/v1/inhalt/medien/[^/]+/(.+)$", a.bild)
                if m:
                    e = await bib.eintrag(b.kennung, unquote(m.group(1)))
                    endung = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg", "image/gif": "gif"}.get(e.mime, "")
                    if endung and len(e.inhalt) > 3000:
                        name = f"{len(funde):02d}.{endung}"; (ZIEL / name).write_bytes(e.inhalt); bild = f"daten/{name}"
            if b.medien > 50 and not bild and gefunden < 2:
                continue
            funde.append({"titel": a.titel, "auszug": a.einleitung[:420], "buch": b.titel, "art": b.art, "sprache": b.sprache,
                          "symbol": symbol, "bild": bild})
            gefunden += 1
    (ZIEL / "funde.json").write_text(json.dumps(funde, ensure_ascii=False, indent=1))
    print(len(funde), sum(1 for f in funde if f["bild"]), [f["titel"] for f in funde])

asyncio.run(main())
