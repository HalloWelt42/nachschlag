"""Notizen und Themen als Markdown in der Ablage der App (WIKI-23): lesbar und weiter nutzbar auch außerhalb von
Nachschlag. Die Ablage ist die Kellerwolke (Zweig der App), wenn eine eingetragen ist, sonst der Ordner `ablage` im
Datenordner (WIKI-11, `appkern.ablage`).

- Notizen je Artikel: `Notizen/<Buch>/<Artikel>.md`, nach jeder Änderung neu geschrieben; ohne Notizen wird die Datei
  gelöscht (in der Kellerwolke: in den Papierkorb). Abschaltbar in den Einstellungen; "Alle ablegen" schreibt den
  ganzen Bestand.
- Themen auf Wunsch: `Themen/<Thema>.md` mit Bereichen, Artikeln, den Notizen dazu und der Literaturliste.

Verweise führen zurück in Nachschlag (Adresse, unter der die App geöffnet wird). Die Darstellung ist reine Umformung
ohne Ein- und Ausgabe, die Ablage spricht allein mit `appkern.ablage`."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from urllib.parse import quote

from appkern.ablage import Ablage, AblageFehler

from .modell.meins import Notiz
from .modell.themen import Thema
from .sammlung.dienst import ordnername

logger = logging.getLogger(__name__)


class MarkdownFehler(Exception):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


# ----- Darstellung ----------------------------------------------------------------------------------------------------

def verweis(adresse: str, buch: str, pfad: str) -> str:
    return f"{adresse.rstrip('/')}/lesen/{quote(buch)}/{quote(pfad)}" if adresse and buch else ""


def _zitat(text: str) -> str:
    return "\n".join(f"> {z}" if z else ">" for z in text.strip().splitlines())


def _notiz(n: Notiz) -> str:
    teile = []
    kopf = f"### {n.abschnitt}" if n.abschnitt else "### Zum ganzen Artikel" if not n.zitat else "### Stelle"
    teile.append(kopf)
    if n.zitat:
        teile.append(_zitat(n.zitat))
    if n.text.strip():
        teile.append(n.text.strip())
    elif n.zitat:
        teile.append("*markiert*")
    for b in n.belege:
        teile.append(f"- Beleg [{b.nummer}]: {b.text}" + (f" {b.url}" if b.url else ""))
    if n.quelle_url:
        teile.append(f"- Im Netz: {n.quelle_url}")
    teile.append(f"*{n.geaendert[:10]}*")
    return "\n\n".join(teile)


def notizen_md(titel: str, buch_name: str, link: str, notizen: list[Notiz]) -> str:
    kopf = [f"# {titel}", "", f"Notizen aus Nachschlag, Quelle: {buch_name}" + (f" ([Artikel öffnen]({link}))" if link else "")]
    return "\n".join(kopf) + "\n\n" + "\n\n".join(_notiz(n) for n in sorted(notizen, key=lambda n: n.angelegt)) + "\n"


def thema_md(t: Thema, notizen: list[Notiz], literatur: str, adresse: str) -> str:
    je_artikel: dict[tuple[str, str], list[Notiz]] = {}
    for n in notizen:
        je_artikel.setdefault((n.buch_name, n.pfad), []).append(n)
    zeilen = [f"# {t.titel}", ""]
    if t.beschreibung.strip():
        zeilen += [t.beschreibung.strip(), ""]
    gruppen = [(b.titel, b.id) for b in sorted(t.bereiche, key=lambda b: b.platz)] + [("Ohne Bereich", "")]
    for titel, kennung in gruppen:
        eintraege = sorted((e for e in t.eintraege if e.bereich == kennung), key=lambda e: e.platz)
        if not eintraege:
            continue
        zeilen += [f"## {titel}", ""]
        for e in eintraege:
            link = verweis(adresse, e.buch, e.pfad)
            zeilen.append(f"- [{e.titel}]({link}) ({e.buch_name})" if link else f"- {e.titel} ({e.buch_name})")
            for n in je_artikel.get((e.buch_name, e.pfad), []):
                text = (n.text.strip() or n.zitat.strip()).replace("\n", " ")
                if text:
                    zeilen.append(f"  - {text[:300]}")
        zeilen.append("")
    if literatur.strip():
        zeilen += ["## Literatur", "", literatur.strip(), ""]
    return "\n".join(zeilen)


# ----- Ablage ---------------------------------------------------------------------------------------------------------

class Markdownablage:
    def __init__(self, ablage: Callable[[], Ablage], notizen: Callable[[str, str, str], Awaitable[list[Notiz]]],
                 adresse: Callable[[], str], an: Callable[[], bool]) -> None:
        """`ablage()`: die Ablage der App, wie sie gerade gilt; `notizen(konto, buch, pfad)`: Notizen eines Artikels
        (leer: alle des Kontos); `an()`: Notizen von selbst ablegen (Einstellung)."""
        self._ablage, self._notizen, self._adresse, self._an = ablage, notizen, adresse, an

    @staticmethod
    async def _schreiben(ablage: Ablage, pfad: str, text: str) -> str:
        """Schreibt und nennt den Ort für Menschen."""
        try:
            await ablage.schreiben(pfad, text.encode(), inhaltstyp="text/markdown")
        except AblageFehler as f:
            raise MarkdownFehler(f.meldung) from f
        return await ablage.ort(pfad)

    async def artikel_ablegen(self, ablage: Ablage, buch: str, buch_name: str, pfad: str, titel: str,
                              notizen: list[Notiz]) -> str | None:
        datei = f"Notizen/{ordnername(buch_name)}/{ordnername(titel)}.md"
        if not notizen:
            try:
                await ablage.weg(datei)                       # in der Kellerwolke: in den Papierkorb
            except AblageFehler as f:
                raise MarkdownFehler(f.meldung) from f
            return None
        return await self._schreiben(ablage, datei, notizen_md(titel, buch_name, verweis(self._adresse(), buch, pfad), notizen))

    async def nach_aenderung(self, konto: str, n: Notiz) -> None:
        """Nach dem Anlegen, Ändern oder Löschen einer Notiz: die Datei ihres Artikels neu (nur, wenn eingeschaltet).
        Ein Fehler steht im Log und hält die Notiz nie auf."""
        if not self._an():
            return
        try:
            notizen = [x for x in await self._notizen(konto, n.buch, n.pfad) if x.buch_name == n.buch_name and x.pfad == n.pfad]
            await self.artikel_ablegen(self._ablage(), n.buch, n.buch_name, n.pfad, n.titel, notizen)
        except MarkdownFehler as f:
            logger.warning("Notizen als Markdown nicht abgelegt (%s): %s", n.titel, f.meldung)

    async def alle_ablegen(self, konto: str) -> tuple[int, str]:
        """Den ganzen Bestand: je Artikel eine Datei; Ergebnis: Zahl der Dateien und der Ordner (für Menschen)."""
        ablage = self._ablage()
        je_artikel: dict[tuple[str, str], list[Notiz]] = {}
        for n in await self._notizen(konto, "", ""):
            je_artikel.setdefault((n.buch_name, n.pfad), []).append(n)
        for liste in je_artikel.values():
            n = liste[0]
            await self.artikel_ablegen(ablage, n.buch, n.buch_name, n.pfad, n.titel, liste)
        return len(je_artikel), await ablage.ort("Notizen")

    async def thema_ablegen(self, konto: str, t: Thema, literatur: str) -> str:
        artikel = {(e.buch_name, e.pfad) for e in t.eintraege}
        notizen = [n for n in await self._notizen(konto, "", "") if (n.buch_name, n.pfad) in artikel]
        return await self._schreiben(self._ablage(), f"Themen/{ordnername(t.titel)}.md",
                                     thema_md(t, notizen, literatur, self._adresse()))
