"""Vorlagen der Bücher (WIKI-45): mitgelieferte liegen als TOML im Paket und sind fest, eigene sind je eine TOML-Datei
im Ordner Vorlagen der App in der Kellerwolke (weitergebbar; was dort abgelegt wird, erscheint). Eigene entstehen als
Kopie. Lesen und Schreiben der Datei ist reine Umformung (`aus_toml`, `als_toml`); die Ablage spricht allein mit der
Kellerwolke."""

from __future__ import annotations

import logging
import re
import tomllib
import unicodedata
from collections.abc import Callable
from datetime import date
from pathlib import Path

import tomli_w
from pydantic import ValidationError

from appkern.kellerwolke import Kellerwolke, KellerwolkeFehler

from ..modell.alsbuch import Vorlage, Vorlagenliste

logger = logging.getLogger("nachschlag.alsbuch")

MITGELIEFERT = Path(__file__).parent / "vorlagen"
#: Reihenfolge der mitgelieferten in der Auswahl
REIHENFOLGE = ["sachbuch", "lernheft", "nachschlagewerk", "vorlesebuch", "einfache-sprache"]
ORDNER = "Vorlagen"
ENDUNG = ".toml"
#: Felder, die nicht in die Datei gehören (der Name der Datei, mitgeliefert, abgeleitet)
NICHT_IN_DER_DATEI = {"kennung", "mitgeliefert", "ki"}


class VorlagenFehler(Exception):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


# ----- Datei ------------------------------------------------------------------------------------------------------------

def aus_toml(kennung: str, text: str, mitgeliefert: bool = False) -> Vorlage:
    """Eine Vorlage aus ihrer Datei; ValueError mit dem Grund, wenn sie nicht passt."""
    try:
        daten = tomllib.loads(text)
    except tomllib.TOMLDecodeError as f:
        raise ValueError(f"kein gültiges TOML: {f}") from f
    daten = {k: w for k, w in daten.items() if k not in NICHT_IN_DER_DATEI}
    try:
        return Vorlage.model_validate({**daten, "kennung": kennung, "mitgeliefert": mitgeliefert})
    except ValidationError as f:
        fehler = f.errors()[0]
        raise ValueError(f"{'.'.join(str(x) for x in fehler['loc'])}: {fehler['msg']}") from f


def als_toml(v: Vorlage) -> str:
    """Die Datei einer Vorlage (ohne Kennung: die ist ihr Name)."""
    daten = v.model_dump(mode="json", exclude=NICHT_IN_DER_DATEI)
    for platz in ("vorn", "innen", "hinten"):        # leere Angaben eigener Kästen bleiben aus der Datei
        daten["aufbau"][platz] = [{k: w for k, w in t.items() if w} for t in daten["aufbau"][platz]]
    return f"# Vorlage für Bücher aus Nachschlag: {v.titel}\n" + tomli_w.dumps(daten)


def kennung_fuer(titel: str, vergeben: set[str]) -> str:
    """Name der Datei zu einem Titel: klein, ASCII, Bindestriche; eindeutig unter den vergebenen."""
    ersetzt = titel.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    roh = unicodedata.normalize("NFKD", ersetzt).encode("ascii", "ignore").decode()
    grund = re.sub(r"[^a-z0-9]+", "-", roh).strip("-")[:50] or "vorlage"
    kennung, n = grund, 2
    while kennung in vergeben:
        kennung, n = f"{grund}-{n}", n + 1
    return kennung


def mitgelieferte() -> list[Vorlage]:
    return [aus_toml(k, (MITGELIEFERT / f"{k}{ENDUNG}").read_text(encoding="utf-8"), mitgeliefert=True) for k in REIHENFOLGE]


# ----- Ablage -----------------------------------------------------------------------------------------------------------

class Vorlagen:
    def __init__(self, kellerwolke: Callable[[], Kellerwolke | None]) -> None:
        self._kw = kellerwolke
        self._fest = {v.kennung: v for v in mitgelieferte()}

    async def _zweig(self) -> tuple[Kellerwolke, str]:
        kw = self._kw()
        if kw is None:
            raise VorlagenFehler("Kellerwolke nicht eingerichtet (Einstellungen, Verbindungen): eigene Vorlagen liegen dort")
        return kw, f"{(await kw.ich()).zweig}/{ORDNER}"

    async def ordner(self) -> str:
        try:
            return (await self._zweig())[1]
        except (VorlagenFehler, KellerwolkeFehler):
            return f"Apps/Nachschlag/{ORDNER}"

    async def _eigene(self) -> tuple[list[Vorlage], list[str]]:
        kw, ordner = await self._zweig()
        knoten = await kw.finden(ordner)
        if knoten is None:
            return [], []
        vorlagen, kaputt = [], []
        async for k in kw.alle_kinder(knoten.id):
            if k.ist_ordner or not k.name.endswith(ENDUNG):
                continue
            kennung = k.name[: -len(ENDUNG)]
            if kennung in self._fest:
                kaputt.append(f"{k.name}: der Name gehört einer mitgelieferten Vorlage")
                continue
            try:
                vorlagen.append(aus_toml(kennung, (await kw.lesen_ganz(k.id)).decode("utf-8")))
            except (ValueError, UnicodeDecodeError) as f:
                kaputt.append(f"{k.name}: {f}")
        return sorted(vorlagen, key=lambda v: v.titel.casefold()), kaputt

    async def liste(self) -> Vorlagenliste:
        hinweis = ""
        try:
            eigene, kaputt = await self._eigene()
            hinweis = "; ".join(kaputt)
        except VorlagenFehler as f:
            eigene, hinweis = [], f.meldung
        except KellerwolkeFehler as f:
            eigene, hinweis = [], f"Eigene Vorlagen ließen sich nicht lesen: {f}"
        return Vorlagenliste(vorlagen=[*self._fest.values(), *eigene], ordner=await self.ordner(), hinweis=hinweis)

    async def holen(self, kennung: str) -> Vorlage | None:
        if kennung in self._fest:
            return self._fest[kennung]
        if self._kw() is None:
            return None                                # ohne Kellerwolke gibt es keine eigenen
        try:
            kw, ordner = await self._zweig()
            knoten = await kw.finden(f"{ordner}/{kennung}{ENDUNG}")
            if knoten is None:
                return None
            return aus_toml(kennung, (await kw.lesen_ganz(knoten.id)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, KellerwolkeFehler) as f:
            raise VorlagenFehler(f"Die Vorlage {kennung} ließ sich nicht lesen: {f}") from f

    async def speichern(self, v: Vorlage) -> Vorlage:
        """Eine eigene Vorlage schreiben (neue Fassung der Datei); mitgelieferte sind fest."""
        if v.kennung in self._fest:
            raise VorlagenFehler("Mitgelieferte Vorlagen sind fest; zum Ändern kopieren")
        v = v.model_copy(update={"mitgeliefert": False})
        kw, ordner = await self._zweig()
        pfad = f"{ordner}/{v.kennung}{ENDUNG}"
        try:
            await kw.ordner(ordner)
            alt = await kw.finden(pfad)
            await kw.schreiben(pfad, als_toml(v).encode(), stand=alt.etag if alt else None, inhaltstyp="application/toml")
        except KellerwolkeFehler as f:
            raise VorlagenFehler(f"Die Vorlage ließ sich nicht ablegen: {f}") from f
        return v

    async def kopieren(self, kennung: str, titel: str, heute: date | None = None) -> Vorlage:
        quelle = await self.holen(kennung)
        if quelle is None:
            raise LookupError(kennung)
        eigene, _ = await self._eigene()
        neu = quelle.model_copy(update={
            "kennung": kennung_fuer(titel, set(self._fest) | {v.kennung for v in eigene}), "titel": titel.strip(),
            "mitgeliefert": False, "kopiert_aus": quelle.titel, "kopiert_am": (heute or date.today()).isoformat()})
        return await self.speichern(neu)

    async def loeschen(self, kennung: str) -> bool:
        """Eine eigene Vorlage in den Papierkorb der Kellerwolke."""
        if kennung in self._fest:
            raise VorlagenFehler("Mitgelieferte Vorlagen lassen sich nicht löschen")
        kw, ordner = await self._zweig()
        knoten = await kw.finden(f"{ordner}/{kennung}{ENDUNG}")
        if knoten is None:
            return False
        await kw.loeschen(knoten.id)
        return True
