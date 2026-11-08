"""Vorlagen der Bücher (WIKI-45): mitgelieferte liegen als TOML im Paket und sind fest, eigene sind je eine TOML-Datei
im Ordner Vorlagen der Ablage der App (Kellerwolke oder Datenordner, WIKI-11; weitergebbar, was dort abgelegt wird,
erscheint). Eigene entstehen als Kopie. Lesen und Schreiben der Datei ist reine Umformung (`aus_toml`, `als_toml`); die
Ablage spricht allein mit `appkern.ablage`."""

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

from appkern.ablage import Ablage, AblageFehler

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
    def __init__(self, ablage: Callable[[], Ablage]) -> None:
        self._ablage = ablage
        self._fest = {v.kennung: v for v in mitgelieferte()}

    async def ordner(self) -> str:
        """Der Ordner der eigenen Vorlagen, wie Menschen ihn finden."""
        return await self._ablage().ort(ORDNER)

    async def _eigene(self) -> tuple[list[Vorlage], list[str]]:
        ablage = self._ablage()
        vorlagen, kaputt = [], []
        for e in await ablage.liste(ORDNER):
            if e.ordner or not e.name.endswith(ENDUNG):
                continue
            kennung = e.name[: -len(ENDUNG)]
            if kennung in self._fest:
                kaputt.append(f"{e.name}: der Name gehört einer mitgelieferten Vorlage")
                continue
            try:
                vorlagen.append(aus_toml(kennung, (await ablage.lesen_ganz(e.kennung)).decode("utf-8")))
            except (ValueError, UnicodeDecodeError) as f:
                kaputt.append(f"{e.name}: {f}")
        return sorted(vorlagen, key=lambda v: v.titel.casefold()), kaputt

    async def liste(self) -> Vorlagenliste:
        hinweis = ""
        try:
            eigene, kaputt = await self._eigene()
            hinweis = "; ".join(kaputt)
        except AblageFehler as f:
            eigene, hinweis = [], f"Eigene Vorlagen ließen sich nicht lesen: {f.meldung}"
        return Vorlagenliste(vorlagen=[*self._fest.values(), *eigene], ordner=await self.ordner(), hinweis=hinweis)

    async def holen(self, kennung: str) -> Vorlage | None:
        if kennung in self._fest:
            return self._fest[kennung]
        try:
            ablage = self._ablage()
            e = await ablage.finden(f"{ORDNER}/{kennung}{ENDUNG}")
            if e is None:
                return None
            return aus_toml(kennung, (await ablage.lesen_ganz(e.kennung)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as f:
            raise VorlagenFehler(f"Die Vorlage {kennung} ließ sich nicht lesen: {f}") from f
        except AblageFehler as f:
            raise VorlagenFehler(f"Die Vorlage {kennung} ließ sich nicht lesen: {f.meldung}") from f

    async def speichern(self, v: Vorlage) -> Vorlage:
        """Eine eigene Vorlage schreiben (neue Fassung der Datei); mitgelieferte sind fest."""
        if v.kennung in self._fest:
            raise VorlagenFehler("Mitgelieferte Vorlagen sind fest; zum Ändern kopieren")
        v = v.model_copy(update={"mitgeliefert": False})
        try:
            await self._ablage().schreiben(f"{ORDNER}/{v.kennung}{ENDUNG}", als_toml(v).encode(), inhaltstyp="application/toml")
        except AblageFehler as f:
            raise VorlagenFehler(f"Die Vorlage ließ sich nicht ablegen: {f.meldung}") from f
        return v

    async def kopieren(self, kennung: str, titel: str, heute: date | None = None) -> Vorlage:
        quelle = await self.holen(kennung)
        if quelle is None:
            raise LookupError(kennung)
        try:
            eigene, _ = await self._eigene()
        except AblageFehler as f:
            raise VorlagenFehler(f"Eigene Vorlagen ließen sich nicht lesen: {f.meldung}") from f
        neu = quelle.model_copy(update={
            "kennung": kennung_fuer(titel, set(self._fest) | {v.kennung for v in eigene}), "titel": titel.strip(),
            "mitgeliefert": False, "kopiert_aus": quelle.titel, "kopiert_am": (heute or date.today()).isoformat()})
        return await self.speichern(neu)

    async def loeschen(self, kennung: str) -> bool:
        """Eine eigene Vorlage löschen (in der Kellerwolke: in den Papierkorb)."""
        if kennung in self._fest:
            raise VorlagenFehler("Mitgelieferte Vorlagen lassen sich nicht löschen")
        try:
            return await self._ablage().weg(f"{ORDNER}/{kennung}{ENDUNG}")
        except AblageFehler as f:
            raise VorlagenFehler(f"Die Vorlage ließ sich nicht löschen: {f.meldung}") from f
