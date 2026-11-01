"""Literaturliste eines Themas (WIKI-31): je Artikel die Quellenangabe in der gewählten Form (einfach, APA, DIN ISO 690
oder BibTeX), darunter die Belege, die der Recherchemodus mit den Notizen zu diesem Artikel gesammelt hat. Nach
Bereichen, Artikel ohne Bereich zuerst; als Markdown, bei BibTeX als .bib mit den Belegen als Kommentar. Die Formen
selbst stehen in `zitieren`; hier nur die Liste."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel

from ..bausteine.html import online_adresse
from ..modell.artikel import Beleg
from ..modell.buch import Buch
from ..modell.meins import Notiz
from ..modell.themen import Thema, Themeneintrag
from ..zitieren import Form, Zitierangaben, schluessel, zitierangaben, zitieren

#: (Buch, Pfad) -> (Autor, Datum), nur für Quellen, die ihre Verfasser nennen (Frage und Antwort)
Verfasser = Callable[[str, str], Awaitable[tuple[str, str]]]


class Literaturliste(BaseModel):
    form: Form
    text: str


def _beleg(b: Beleg) -> str:
    return f"Beleg {b.nummer}: {b.text}" + (f" {b.url}" if b.url and b.url not in b.text else "")


async def _angaben(e: Themeneintrag, buch: Buch | None, verfasser: Verfasser) -> Zitierangaben:
    if buch is None:
        return Zitierangaben(titel=e.titel, quelle=e.buch_name)
    autor, datum = await verfasser(buch.kennung, e.pfad) if buch.art == "frage_antwort" else ("", "")
    return zitierangaben(buch, e.titel, online_adresse(buch, e.pfad), autor, datum)


async def literaturliste(thema: Thema, buecher: dict[str, Buch], notizen: list[Notiz], form: Form,
                         verfasser: Verfasser) -> str:
    belege: dict[tuple[str, str], dict[int, Beleg]] = {}
    for n in notizen:
        for b in n.belege:
            belege.setdefault((n.buch_name, n.pfad), {})[b.nummer] = b
    gruppen = [("", [e for e in thema.eintraege if not e.bereich])]
    gruppen += [(b.titel, [e for e in thema.eintraege if e.bereich == b.id]) for b in thema.bereiche]
    bib = form == "bibtex"
    zeilen = [f"% Literatur: {thema.titel}" if bib else f"# Literatur: {thema.titel}", ""]
    vergeben: set[str] = set()
    for titel, eintraege in gruppen:
        if not eintraege:
            continue
        if titel:
            zeilen += [f"% {titel}" if bib else f"## {titel}", ""]
        for e in sorted(eintraege, key=lambda x: x.platz):
            angaben = await _angaben(e, buecher.get(e.buch), verfasser)
            gesammelt = [_beleg(b) for b in sorted(belege.get((e.buch_name, e.pfad), {}).values(), key=lambda b: b.nummer)]
            if bib:
                kennung = _frei(schluessel(angaben), vergeben)
                zeilen += [zitieren(angaben, "bibtex").replace(f"@misc{{{schluessel(angaben)},", f"@misc{{{kennung},", 1)]
                zeilen += [f"% {g}" for g in gesammelt] + [""]
            else:
                zeilen += [f"- {zitieren(angaben, form)}"] + [f"  - {g}" for g in gesammelt]
        if not bib:
            zeilen.append("")
    return "\n".join(zeilen).rstrip() + "\n"


def _frei(kennung: str, vergeben: set[str]) -> str:
    """Eindeutige Kennung in der Liste: rotfuchs2026, rotfuchs2026b, rotfuchs2026c ..."""
    neu, zusatz = kennung, ord("b")
    while neu in vergeben:
        neu, zusatz = f"{kennung}{chr(zusatz)}", zusatz + 1
    vergeben.add(neu)
    return neu
