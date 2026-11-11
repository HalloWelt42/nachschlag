"""Was der Bücherlader sich merkt (WIKI-57): die Bücher und Fassungen des Verzeichnisses mit dem Durchgang, in dem sie
zuerst auftauchten (daraus ergibt sich, was neu ist), die Durchgänge, die Abos und die Wechsel auf eine neue Fassung
(für Rückfall und Aufräumen). Dazu die Quellen und je Fassung ihre Bezugsquellen (WIKI-62). Eine Wahrheit für alle
Konten: die Bibliothek ist gemeinsam."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from appkern.datenbank import Datenbank

from ..modell.buecherlader import Durchgang
from ..modell.buecherlader import Angaben, Quellstand
from .quellen import Art, Bezug, Vereint

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
""", """
CREATE TABLE buecherlader_quelle (
    nr      INTEGER PRIMARY KEY,
    art     TEXT NOT NULL CHECK (art IN ('verzeichnis', 'katalog')),
    name    TEXT NOT NULL,
    adresse TEXT NOT NULL UNIQUE,
    an      INTEGER NOT NULL DEFAULT 1,
    rang    INTEGER NOT NULL,
    zuletzt TEXT NOT NULL DEFAULT '',
    funde   INTEGER NOT NULL DEFAULT 0,
    meldung TEXT NOT NULL DEFAULT ''
);
CREATE TABLE buecherlader_bezug (
    stamm     TEXT NOT NULL,
    stand     TEXT NOT NULL,
    quelle    INTEGER NOT NULL,
    adresse   TEXT NOT NULL,
    ladedatei TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (stamm, stand, quelle)
);
ALTER TABLE buecherlader_buch ADD COLUMN angaben TEXT NOT NULL DEFAULT '';
INSERT INTO buecherlader_quelle (art, name, adresse, rang) VALUES
    ('katalog', 'Katalog der Bücher', 'https://opds.library.kiwix.org/catalog/v2', 1),
    ('verzeichnis', 'Uni Erlangen', 'https://ftp.uni-erlangen.de/kiwix/zim/', 2),
    ('verzeichnis', 'dotsrc.org (Uni Aalborg)', 'https://mirrors.dotsrc.org/kiwix/zim/', 3),
    ('verzeichnis', 'Academic Computer Club Umeå', 'https://mirror.accum.se/mirror/kiwix.org/zim/', 4),
    ('verzeichnis', 'NLUUG', 'https://ftp.nluug.nl/pub/kiwix/zim/', 5);
""", """
-- WIKI-87: eigene Bücher aus einem Ordner auf dem Rechner der App (SQLite ändert keine Prüfung: Tabelle neu)
CREATE TABLE buecherlader_quelle_neu (
    nr      INTEGER PRIMARY KEY,
    art     TEXT NOT NULL CHECK (art IN ('verzeichnis', 'katalog', 'ordner')),
    name    TEXT NOT NULL,
    adresse TEXT NOT NULL UNIQUE,
    an      INTEGER NOT NULL DEFAULT 1,
    rang    INTEGER NOT NULL,
    zuletzt TEXT NOT NULL DEFAULT '',
    funde   INTEGER NOT NULL DEFAULT 0,
    meldung TEXT NOT NULL DEFAULT ''
);
INSERT INTO buecherlader_quelle_neu SELECT nr, art, name, adresse, an, rang, zuletzt, funde, meldung FROM buecherlader_quelle;
DROP TABLE buecherlader_quelle;
ALTER TABLE buecherlader_quelle_neu RENAME TO buecherlader_quelle;
"""]
#: Die ersten Quellen (Stufe 2, WIKI-62): der offizielle Katalog und Spiegel an Hochschulen und bei gemeinnützigen
#: Betreibern, alle mit lesbarem Verzeichnis (geprüft am 07.11.2026). Weitere fügt man in der Bibliothek hinzu.


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
    angaben: str = ""   # Angaben als JSON (WIKI-62)
    bezuege: int = 0    # aus so vielen Quellen ladbar

    def angaben_lesen(self) -> Angaben:
        return Angaben.model_validate_json(self.angaben) if self.angaben else Angaben(titel=self.titel,
                                                                                     beschreibung=self.beschreibung,
                                                                                     artikel=self.eintraege)


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

    async def durchgang_eintragen(self, durchgang: Durchgang, vereint: list[Vereint]) -> Durchgang:
        """Einen fertigen Durchgang mit der Vereinigungsmenge aller Quellen in einem Zug eintragen; zählt, was neu ist.
        Beim ersten Durchgang gilt nichts als neu (Erstaufnahme). Die Bezugsquellen gelten danach so, wie dieser
        Durchgang sie fand."""

        def arbeit(v: sqlite3.Connection) -> Durchgang:
            erst = v.execute("SELECT count(*) FROM buecherlader_durchgang").fetchone()[0] == 0
            nr = v.execute("INSERT INTO buecherlader_durchgang (begonnen, inhalt) VALUES (?, '{}')",
                           (durchgang.begonnen,)).lastrowid
            bekannt = {z[0] for z in v.execute("SELECT stamm FROM buecherlader_buch")}
            staende = {(z[0], z[1]) for z in v.execute("SELECT stamm, stand FROM buecherlader_fassung")}
            v.execute("DELETE FROM buecherlader_bezug")
            neue_buecher = neue_fassungen = 0
            for d in vereint:
                if d.stamm not in bekannt:
                    neue_buecher += 1
                    bekannt.add(d.stamm)
                    v.execute("INSERT INTO buecherlader_buch (stamm, ordner, sprache, zuerst) VALUES (?,?,?,?)",
                              (d.stamm, d.ordner, d.sprache, nr))
                elif (d.stamm, d.stand) not in staende:
                    neue_fassungen += 1
                if d.angaben:
                    a = d.angaben
                    v.execute("UPDATE buecherlader_buch SET titel=?, beschreibung=?, eintraege=?, angaben=? WHERE stamm=?",
                              (a.titel, a.beschreibung, a.artikel, a.model_dump_json(), d.stamm))
                if (d.stamm, d.stand) not in staende:
                    staende.add((d.stamm, d.stand))
                    v.execute("INSERT INTO buecherlader_fassung (stamm, stand, datei, groesse, zuerst) VALUES (?,?,?,?,?)",
                              (d.stamm, d.stand, d.datei, d.groesse, nr))
                else:
                    v.execute("UPDATE buecherlader_fassung SET groesse=max(groesse, ?) WHERE stamm=? AND stand=?",
                              (d.groesse, d.stamm, d.stand))
                v.executemany("INSERT OR REPLACE INTO buecherlader_bezug (stamm, stand, quelle, adresse, ladedatei) "
                              "VALUES (?,?,?,?,?)", [(d.stamm, d.stand, b.quelle, b.adresse, b.ladedatei) for b in d.bezuege])
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
            "SELECT b.*, f.stand, f.datei, f.groesse, f.zuerst AS stand_zuerst, "
            "(SELECT count(*) FROM buecherlader_bezug z WHERE z.stamm = f.stamm AND z.stand = f.stand) AS bezuege "
            "FROM buecherlader_buch b JOIN buecherlader_fassung f ON f.stamm = b.stamm AND f.stand = "
            "(SELECT max(stand) FROM buecherlader_fassung WHERE stamm = b.stamm) "
            f"WHERE b.sprache IN ({','.join('?' * len(sprachen))})", sorted(sprachen))
        return [Buchzeile(**z) for z in zeilen]

    async def neueste(self, stamm: str) -> Buchzeile | None:
        zeilen = await self._db.zeilen(
            "SELECT b.*, f.stand, f.datei, f.groesse, f.zuerst AS stand_zuerst, "
            "(SELECT count(*) FROM buecherlader_bezug z WHERE z.stamm = f.stamm AND z.stand = f.stand) AS bezuege "
            "FROM buecherlader_buch b JOIN buecherlader_fassung f ON f.stamm = b.stamm WHERE b.stamm = ? "
            "ORDER BY f.stand DESC LIMIT 1", (stamm,))
        return Buchzeile(**zeilen[0]) if zeilen else None

    # ----- Quellen (WIKI-62) -------------------------------------------------------------------------------------------

    async def quellen(self, nur_an: bool = False) -> list[Quellstand]:
        wo = "WHERE an = 1 " if nur_an else ""
        return [Quellstand(**{**z, "an": bool(z["an"])}) for z in
                await self._db.zeilen(f"SELECT * FROM buecherlader_quelle {wo}ORDER BY rang, nr")]

    async def quelle_anlegen(self, art: Art, name: str, adresse: str) -> int:
        rang = (await self._db.zeile("SELECT coalesce(max(rang), 0) + 1 AS r FROM buecherlader_quelle"))["r"]
        try:
            await self._db.ausfuehren("INSERT INTO buecherlader_quelle (art, name, adresse, rang) VALUES (?,?,?,?)",
                                      (art, name, adresse, rang))
        except sqlite3.IntegrityError:
            raise ValueError("Diese Adresse ist schon eine Quelle") from None
        return (await self._db.zeile("SELECT nr FROM buecherlader_quelle WHERE adresse=?", (adresse,)))["nr"]

    async def quelle_aendern(self, nr: int, werte: dict) -> None:
        erlaubt = {k: (int(w) if k == "an" else w) for k, w in werte.items() if k in ("an", "rang", "name") and w is not None}
        if not await self._db.zeile("SELECT 1 FROM buecherlader_quelle WHERE nr=?", (nr,)):
            raise LookupError(f"Eine Quelle {nr} gibt es nicht")
        for k, w in erlaubt.items():
            await self._db.ausfuehren(f"UPDATE buecherlader_quelle SET {k}=? WHERE nr=?", (w, nr))

    async def quelle_entfernen(self, nr: int) -> None:
        await self._db.ausfuehren("DELETE FROM buecherlader_bezug WHERE quelle=?", (nr,))
        await self._db.ausfuehren("DELETE FROM buecherlader_quelle WHERE nr=?", (nr,))

    async def quelle_gelaufen(self, nr: int, funde: int, meldung: str) -> None:
        await self._db.ausfuehren("UPDATE buecherlader_quelle SET zuletzt=?, funde=?, meldung=? WHERE nr=?",
                                  (jetzt(), funde, meldung[:300], nr))

    async def bezuege(self, stamm: str, stand: str) -> list[Bezug]:
        """Wo eine Fassung zu laden ist, in der Reihenfolge der eingeschalteten Quellen."""
        return [Bezug(z["quelle"], z["adresse"], z["ladedatei"]) for z in await self._db.zeilen(
            "SELECT z.quelle, z.adresse, z.ladedatei FROM buecherlader_bezug z JOIN buecherlader_quelle q ON q.nr = z.quelle "
            "WHERE z.stamm=? AND z.stand=? AND q.an = 1 ORDER BY q.rang, q.nr", (stamm, stand))]

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

    async def wechsel_eintragen(self, stamm: str, alt: str, neu: str, am: datetime) -> None:
        """`am`: wann umgeschaltet wurde, nach der Uhr des Laders (an ihr misst sich die Frist der vorigen Fassung)."""
        await self._db.ausfuehren(
            "INSERT INTO buecherlader_wechsel (stamm, alt, neu, am) VALUES (?,?,?,?) ON CONFLICT(stamm, neu) DO UPDATE SET "
            "alt=excluded.alt, am=excluded.am, entfernt='', zurueck=''", (stamm, alt, neu, am.isoformat(timespec="seconds")))

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

