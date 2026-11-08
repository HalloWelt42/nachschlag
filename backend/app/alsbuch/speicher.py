"""Was Als Buch in der Datenbank der App hält (WIKI-45): die fertigen Bücher je Konto (mit ihrem Inhalt für Leseansicht
und Nachbau), den Zwischenspeicher der Umformungen (gleiche Anfrage, gleiches Ergebnis: ein Nachbau formt nur Neues um),
das gemessene Tempo je Modell, das letzte Probekapitel und die letzte Bestellung je Thema und den Stand laufender Bauten.
Die Dateien der Bücher liegen in der Kellerwolke."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from appkern.datenbank import Datenbank

from ..modell.alsbuch import Baustand, Bestellung, Buchformat, Buchinhalt, Probe, Satzhinweis

STUFEN = ["""
CREATE TABLE alsbuch_buecher (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, thema TEXT NOT NULL, vorlage TEXT NOT NULL, titel TEXT NOT NULL,
  vorlage_titel TEXT NOT NULL, bestellung TEXT NOT NULL, eintraege TEXT NOT NULL, artikel INTEGER NOT NULL,
  seiten INTEGER NOT NULL, zeichen INTEGER NOT NULL, formate TEXT NOT NULL, titelbild TEXT NOT NULL, hinweise TEXT NOT NULL,
  inhalt TEXT NOT NULL, gebaut TEXT NOT NULL);
CREATE UNIQUE INDEX alsbuch_buecher_einmal ON alsbuch_buecher (konto, thema, vorlage);
CREATE TABLE alsbuch_umformungen (schluessel TEXT PRIMARY KEY, ergebnis TEXT NOT NULL, zeichen INTEGER NOT NULL,
  sekunden REAL NOT NULL, angelegt TEXT NOT NULL);
CREATE TABLE alsbuch_tempo (modell TEXT PRIMARY KEY, zeichen_je_s REAL NOT NULL, gemessen TEXT NOT NULL);
CREATE TABLE alsbuch_proben (konto TEXT NOT NULL, thema TEXT NOT NULL, probe TEXT NOT NULL, PRIMARY KEY (konto, thema));
CREATE TABLE alsbuch_bau (auftrag TEXT PRIMARY KEY, konto TEXT NOT NULL, stand TEXT NOT NULL);
CREATE TABLE alsbuch_bestellungen (konto TEXT NOT NULL, thema TEXT NOT NULL, bestellung TEXT NOT NULL,
  PRIMARY KEY (konto, thema));
"""]

KOPF = ("id, konto, thema, vorlage, titel, vorlage_titel, bestellung, eintraege, artikel, seiten, zeichen, formate, titelbild, "
        "hinweise, gebaut")


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Buchsatz(BaseModel):
    """Ein fertiges Buch, wie es in der Datenbank steht."""
    id: str
    konto: str
    thema: str
    vorlage: str
    titel: str
    vorlage_titel: str
    bestellung: Bestellung
    eintraege: list[str] = Field(description="Kennungen der Einträge des Themas im Buch (Vergleich nach Änderungen)")
    artikel: int
    seiten: int
    zeichen: int = Field(description="Text der Artikel in Zeichen (Schätzung des Nachbaus)")
    formate: list[Buchformat]
    titelbild: str = ""
    hinweise: list[Satzhinweis] = Field(default_factory=list)
    gebaut: str
    inhalt: Buchinhalt | None = None


def _satz(z: dict[str, Any]) -> Buchsatz:
    werte = dict(z)
    for feld in ("bestellung", "eintraege", "formate", "hinweise"):
        werte[feld] = json.loads(werte[feld])
    if "inhalt" in werte:
        werte["inhalt"] = Buchinhalt.model_validate_json(werte["inhalt"])
    return Buchsatz.model_validate(werte)


class Buchspeicher:
    def __init__(self, db: Datenbank) -> None:
        self._db = db

    async def einrichten(self) -> None:
        await self._db.einrichten("nachschlag_alsbuch", STUFEN)

    # --- Zwischenspeicher der Umformungen ------------------------------------------------------------------------------
    async def umformung(self, schluessel: str) -> dict[str, Any] | None:
        z = await self._db.zeile("SELECT ergebnis FROM alsbuch_umformungen WHERE schluessel=?", (schluessel,))
        return json.loads(z["ergebnis"]) if z else None

    async def umformung_merken(self, schluessel: str, ergebnis: dict[str, Any], zeichen: int, sekunden: float) -> None:
        await self._db.ausfuehren(
            "INSERT INTO alsbuch_umformungen (schluessel, ergebnis, zeichen, sekunden, angelegt) VALUES (?,?,?,?,?) "
            "ON CONFLICT(schluessel) DO UPDATE SET ergebnis=excluded.ergebnis",
            (schluessel, json.dumps(ergebnis, ensure_ascii=False), zeichen, sekunden, _jetzt()))

    # --- Tempo je Modell -----------------------------------------------------------------------------------------------
    async def tempo(self, modell: str) -> float | None:
        z = await self._db.zeile("SELECT zeichen_je_s FROM alsbuch_tempo WHERE modell=?", (modell,))
        return float(z["zeichen_je_s"]) if z else None

    async def tempo_merken(self, modell: str, zeichen_je_s: float) -> None:
        await self._db.ausfuehren(
            "INSERT INTO alsbuch_tempo (modell, zeichen_je_s, gemessen) VALUES (?,?,?) ON CONFLICT(modell) DO UPDATE SET "
            "zeichen_je_s=excluded.zeichen_je_s, gemessen=excluded.gemessen", (modell, zeichen_je_s, _jetzt()))

    # --- Probekapitel und letzte Bestellung je Thema -------------------------------------------------------------------
    async def probe(self, konto: str, thema: str) -> Probe | None:
        z = await self._db.zeile("SELECT probe FROM alsbuch_proben WHERE konto=? AND thema=?", (konto, thema))
        return Probe.model_validate_json(z["probe"]) if z else None

    async def probe_merken(self, konto: str, p: Probe) -> None:
        await self._db.ausfuehren("INSERT INTO alsbuch_proben (konto, thema, probe) VALUES (?,?,?) ON CONFLICT(konto, thema) "
                                  "DO UPDATE SET probe=excluded.probe", (konto, p.thema, p.model_dump_json()))

    async def letzte(self, konto: str, thema: str) -> Bestellung | None:
        z = await self._db.zeile("SELECT bestellung FROM alsbuch_bestellungen WHERE konto=? AND thema=?", (konto, thema))
        return Bestellung.model_validate_json(z["bestellung"]) if z else None

    async def letzte_merken(self, konto: str, b: Bestellung) -> None:
        await self._db.ausfuehren("INSERT INTO alsbuch_bestellungen (konto, thema, bestellung) VALUES (?,?,?) ON CONFLICT"
                                  "(konto, thema) DO UPDATE SET bestellung=excluded.bestellung", (konto, b.thema, b.model_dump_json()))

    # --- Stand laufender Bauten ----------------------------------------------------------------------------------------
    async def baustand_merken(self, konto: str, s: Baustand) -> None:
        await self._db.ausfuehren("INSERT INTO alsbuch_bau (auftrag, konto, stand) VALUES (?,?,?) ON CONFLICT(auftrag) DO "
                                  "UPDATE SET stand=excluded.stand", (s.auftrag, konto, s.model_dump_json()))

    async def baustaende(self, konto: str) -> dict[str, Baustand]:
        zeilen = await self._db.zeilen("SELECT auftrag, stand FROM alsbuch_bau WHERE konto=?", (konto,))
        return {z["auftrag"]: Baustand.model_validate_json(z["stand"]) for z in zeilen}

    async def bau_vergessen(self, auftrag: str) -> None:
        await self._db.ausfuehren("DELETE FROM alsbuch_bau WHERE auftrag=?", (auftrag,))

    # --- Fertige Bücher ------------------------------------------------------------------------------------------------
    async def buch_merken(self, b: Buchsatz) -> None:
        werte = b.model_dump(mode="json")
        felder = [f for f in KOPF.split(", ")] + ["inhalt"]
        zeile = [json.dumps(werte[f], ensure_ascii=False) if f in ("bestellung", "eintraege", "formate", "hinweise") else werte[f]
                 for f in felder[:-1]] + [b.inhalt.model_dump_json() if b.inhalt else "{}"]
        aendern = ", ".join(f"{f}=excluded.{f}" for f in felder if f not in ("konto", "thema", "vorlage"))
        await self._db.ausfuehren(
            f"INSERT INTO alsbuch_buecher ({', '.join(felder)}) VALUES ({','.join('?' * len(felder))}) "
            f"ON CONFLICT(konto, thema, vorlage) DO UPDATE SET {aendern}", tuple(zeile))

    async def buecher(self, konto: str) -> list[Buchsatz]:
        zeilen = await self._db.zeilen(f"SELECT {KOPF} FROM alsbuch_buecher WHERE konto=? ORDER BY gebaut DESC", (konto,))
        return [_satz(z) for z in zeilen]

    async def buch(self, konto: str, kennung: str, mit_inhalt: bool = False) -> Buchsatz | None:
        spalten = KOPF + (", inhalt" if mit_inhalt else "")
        z = await self._db.zeile(f"SELECT {spalten} FROM alsbuch_buecher WHERE konto=? AND id=?", (konto, kennung))
        return _satz(z) if z else None

    async def buch_zu(self, konto: str, thema: str, vorlage: str) -> Buchsatz | None:
        z = await self._db.zeile(f"SELECT {KOPF} FROM alsbuch_buecher WHERE konto=? AND thema=? AND vorlage=?",
                                 (konto, thema, vorlage))
        return _satz(z) if z else None

    async def buch_loeschen(self, konto: str, kennung: str) -> bool:
        return await self._db.ausfuehren("DELETE FROM alsbuch_buecher WHERE konto=? AND id=?", (konto, kennung)) > 0
