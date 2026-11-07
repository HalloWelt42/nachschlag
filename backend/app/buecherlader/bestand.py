"""Was der Bücherlader sich merkt (WIKI-57): die Bücher und Fassungen des Verzeichnisses mit dem Durchgang, in dem sie
zuerst auftauchten (daraus ergibt sich, was neu ist), die Durchgänge, die Abos und die Wechsel auf eine neue Fassung
(für Rückfall und Aufräumen). Eine Wahrheit für alle Konten: die Bibliothek ist gemeinsam."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from appkern.datenbank import Datenbank

from ..modell.buecherlader import Durchgang
from .katalog import Katalogeintrag
from .verzeichnis import Datei

STUFEN = ["""
CREATE TABLE buecherlader_buch (
    stamm        TEXT PRIMARY KEY,
    ordner       TEXT NOT NULL,
    sprache      TEXT NOT NULL,
    titel        TEXT NOT NULL DEFAULT '',
    beschreibung TEXT NOT NULL DEFAULT '',
    eintraege    INTEGER NOT NULL DEFAULT 0,
    zuerst       INTEGER NOT NULL
);
CREATE TABLE buecherlader_fassung (
    stamm   TEXT NOT NULL,
    stand   TEXT NOT NULL,
    datei   TEXT NOT NULL,
    groesse INTEGER NOT NULL,
    zuerst  INTEGER NOT NULL,
    PRIMARY KEY (stamm, stand)
);
CREATE TABLE buecherlader_durchgang (
    nr       INTEGER PRIMARY KEY,
    begonnen TEXT NOT NULL,
    inhalt   TEXT NOT NULL
);
CREATE TABLE buecherlader_abo (
    stamm TEXT PRIMARY KEY,
    seit  TEXT NOT NULL
);
CREATE TABLE buecherlader_wechsel (
    stamm    TEXT NOT NULL,
    alt      TEXT NOT NULL,
    neu      TEXT NOT NULL,
    am       TEXT NOT NULL,
    entfernt TEXT NOT NULL DEFAULT '',
    zurueck  TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (stamm, neu)
);
CREATE TABLE buecherlader_merker (
    schluessel TEXT PRIMARY KEY,
    wert       TEXT NOT NULL
);
"""]


def jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Buchzeile:
    stamm: str
    ordner: str
    sprache: str
    titel: str
    beschreibung: str
    eintraege: int
    zuerst: int
    stand: str          # jüngster bekannter Stand
    datei: str
    groesse: int
    stand_zuerst: int   # Durchgang, in dem dieser Stand zuerst auftauchte


@dataclass(frozen=True)
class Wechsel:
    stamm: str
    alt: str
    neu: str
    am: str


class Bestand:
    def __init__(self, db: Datenbank) -> None:
        self._db = db

    async def einrichten(self) -> None:
        await self._db.einrichten("nachschlag_buecherlader", STUFEN)

    # ----- Durchgänge -------------------------------------------------------------------------------------------------

    async def durchgang_eintragen(self, durchgang: Durchgang, dateien: list[Datei],
                                  katalog: dict[str, Katalogeintrag]) -> Durchgang:
        """Einen fertigen Durchgang mit allen Dateien in einem Zug eintragen; zählt, was neu ist. Beim ersten Durchgang
        gilt nichts als neu (Erstaufnahme)."""

        def arbeit(v: sqlite3.Connection) -> Durchgang:
            erst = v.execute("SELECT count(*) FROM buecherlader_durchgang").fetchone()[0] == 0
            nr = v.execute("INSERT INTO buecherlader_durchgang (begonnen, inhalt) VALUES (?, '{}')",
                           (durchgang.begonnen,)).lastrowid
            bekannt = {z[0] for z in v.execute("SELECT stamm FROM buecherlader_buch")}
            staende = {(z[0], z[1]) for z in v.execute("SELECT stamm, stand FROM buecherlader_fassung")}
            neue_buecher = neue_fassungen = 0
            for d in dateien:
                k = katalog.get(d.stamm)
                if d.stamm not in bekannt:
                    neue_buecher += 1
                    bekannt.add(d.stamm)
                    v.execute("INSERT INTO buecherlader_buch (stamm, ordner, sprache, zuerst) VALUES (?,?,?,?)",
                              (d.stamm, d.ordner, d.sprache, nr))
                elif (d.stamm, d.stand) not in staende:
                    neue_fassungen += 1
                if k:
                    v.execute("UPDATE buecherlader_buch SET titel=?, beschreibung=?, eintraege=? WHERE stamm=?",
                              (k.titel, k.beschreibung, k.eintraege, d.stamm))
                if (d.stamm, d.stand) not in staende:
                    staende.add((d.stamm, d.stand))
                    v.execute("INSERT INTO buecherlader_fassung (stamm, stand, datei, groesse, zuerst) VALUES (?,?,?,?,?)",
                              (d.stamm, d.stand, d.datei, d.groesse, nr))
            fertig = durchgang.model_copy(update={"erstaufnahme": erst, "neue_buecher": 0 if erst else neue_buecher,
                                                  "neue_fassungen": 0 if erst else neue_fassungen})
            v.execute("UPDATE buecherlader_durchgang SET inhalt=? WHERE nr=?", (fertig.model_dump_json(), nr))
            return fertig

        return await self._db.transaktion(arbeit)

    async def letzter_durchgang(self) -> tuple[int, Durchgang] | None:
        z = await self._db.zeile("SELECT nr, inhalt FROM buecherlader_durchgang ORDER BY nr DESC LIMIT 1")
        return (z["nr"], Durchgang.model_validate_json(z["inhalt"])) if z else None

    # ----- Verzeichnis ------------------------------------------------------------------------------------------------

    async def buecher(self, sprachen: set[str]) -> list[Buchzeile]:
        """Alle bekannten Bücher der Sprachen mit ihrem jüngsten Stand."""
        if not sprachen:
            return []
        zeilen = await self._db.zeilen(
            "SELECT b.*, f.stand, f.datei, f.groesse, f.zuerst AS stand_zuerst FROM buecherlader_buch b "
            "JOIN buecherlader_fassung f ON f.stamm = b.stamm AND f.stand = "
            "(SELECT max(stand) FROM buecherlader_fassung WHERE stamm = b.stamm) "
            f"WHERE b.sprache IN ({','.join('?' * len(sprachen))})", sorted(sprachen))
        return [Buchzeile(**z) for z in zeilen]

    async def neueste(self, stamm: str) -> Buchzeile | None:
        zeilen = await self._db.zeilen(
            "SELECT b.*, f.stand, f.datei, f.groesse, f.zuerst AS stand_zuerst FROM buecherlader_buch b "
            "JOIN buecherlader_fassung f ON f.stamm = b.stamm WHERE b.stamm = ? ORDER BY f.stand DESC LIMIT 1", (stamm,))
        return Buchzeile(**zeilen[0]) if zeilen else None

    # ----- Abos -------------------------------------------------------------------------------------------------------

    async def abos(self) -> dict[str, str]:
        """Stamm -> seit wann."""
        return {z["stamm"]: z["seit"] for z in await self._db.zeilen("SELECT stamm, seit FROM buecherlader_abo")}

    async def abonnieren(self, staemme: list[str]) -> None:
        for stamm in staemme:
            await self._db.ausfuehren("INSERT OR IGNORE INTO buecherlader_abo (stamm, seit) VALUES (?,?)", (stamm, jetzt()))

    async def abbestellen(self, stamm: str) -> None:
        await self._db.ausfuehren("DELETE FROM buecherlader_abo WHERE stamm=?", (stamm,))

    # ----- Wechsel ----------------------------------------------------------------------------------------------------

    async def wechsel_eintragen(self, stamm: str, alt: str, neu: str) -> None:
        await self._db.ausfuehren(
            "INSERT INTO buecherlader_wechsel (stamm, alt, neu, am) VALUES (?,?,?,?) ON CONFLICT(stamm, neu) DO UPDATE SET "
            "alt=excluded.alt, am=excluded.am, entfernt='', zurueck=''", (stamm, alt, neu, jetzt()))

    async def offene_wechsel(self) -> list[Wechsel]:
        """Wechsel, deren vorige Fassung noch als Rückfall da ist (weder entfernt noch zurückgenommen)."""
        return [Wechsel(z["stamm"], z["alt"], z["neu"], z["am"]) for z in await self._db.zeilen(
            "SELECT stamm, alt, neu, am FROM buecherlader_wechsel WHERE entfernt='' AND zurueck='' ORDER BY am")]

    async def wechsel_beenden(self, w: Wechsel, wie: str) -> None:
        """`wie`: entfernt oder zurueck."""
        spalte = {"entfernt": "entfernt", "zurueck": "zurueck"}[wie]
        await self._db.ausfuehren(f"UPDATE buecherlader_wechsel SET {spalte}=? WHERE stamm=? AND neu=?",
                                  (jetzt(), w.stamm, w.neu))

    # ----- Merker -----------------------------------------------------------------------------------------------------

    async def merker(self, schluessel: str) -> str:
        z = await self._db.zeile("SELECT wert FROM buecherlader_merker WHERE schluessel=?", (schluessel,))
        return z["wert"] if z else ""

    async def merken(self, schluessel: str, wert: str) -> None:
        await self._db.ausfuehren("INSERT INTO buecherlader_merker (schluessel, wert) VALUES (?,?) ON CONFLICT(schluessel) "
                                  "DO UPDATE SET wert=excluded.wert", (schluessel, wert))

