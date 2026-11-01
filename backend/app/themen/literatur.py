"""Literaturliste eines Themas (WIKI-31): je Artikel Titel, Quelle mit Stand und die Adresse im Netz, darunter die Belege,
die der Recherchemodus mit den Notizen zu diesem Artikel gesammelt hat. Ausgabe als Markdown, nach Bereichen."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ..bausteine.html import datum, online_adresse
from ..modell.artikel import Beleg
from ..modell.buch import Buch
from ..modell.meins import Notiz
from ..modell.themen import Thema, Themeneintrag


class Literaturliste(BaseModel):
    markdown: str


def _zeile(e: Themeneintrag, buch: Buch | None, belege: list[Beleg], heute: str) -> list[str]:
    url = online_adresse(buch, e.pfad) if buch else ""
    quelle = f"{buch.titel}, Stand {datum(buch.stand)}" if buch else e.buch_name
    zeilen = [f"- {e.titel}. In: {quelle}." + (f" {url} (abgerufen am {heute})" if url else "")]
    zeilen += [f"  - Beleg {b.nummer}: {b.text}" + (f" {b.url}" if b.url and b.url not in b.text else "") for b in belege]
    return zeilen


def literaturliste(thema: Thema, buecher: dict[str, Buch], notizen: list[Notiz]) -> str:
    heute = date.today().strftime("%d.%m.%Y")
    belege: dict[tuple[str, str], dict[int, Beleg]] = {}
    for n in notizen:
        for b in n.belege:
            belege.setdefault((n.buch_name, n.pfad), {})[b.nummer] = b
    gruppen = [("", [e for e in thema.eintraege if not e.bereich])]
    gruppen += [(b.titel, [e for e in thema.eintraege if e.bereich == b.id]) for b in thema.bereiche]
    zeilen = [f"# Literatur: {thema.titel}", ""]
    for titel, eintraege in gruppen:
        if not eintraege:
            continue
        if titel:
            zeilen += [f"## {titel}", ""]
        for e in sorted(eintraege, key=lambda x: x.platz):
            gesammelt = sorted(belege.get((e.buch_name, e.pfad), {}).values(), key=lambda b: b.nummer)
            zeilen += _zeile(e, buecher.get(e.buch), gesammelt, heute)
        zeilen.append("")
    return "\n".join(zeilen).rstrip() + "\n"
