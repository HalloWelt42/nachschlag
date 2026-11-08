"""Die Datenabzüge von Wikimedia für die Kategorien eines Wikis holen und aufbereiten (auf dem Mac, im Index-Dienst).

Gebraucht werden fünf Tabellen des Wikis (dumps.wikimedia.org/<wiki>/latest/): `page` (Seiten mit Titel), `linktarget`
(Ziele von Verweisen, darunter die Kategorien), `categorylinks` (wer in welcher Kategorie steht), `page_props` (welche
Kategorien versteckt sind) und die Namen der Namensräume (wie "Kategorie" im Wiki heißt). Zusammen gut 1 GB.

Geladen wird fortsetzbar in einen eigenen Ordner; ein Abzug gilt `ALTER_TAGE` Tage, danach holt der nächste Bau einen
neuen. Aus den Rohdateien entsteht je Wiki eine kompakte Datei (`<wiki>.sqlite`), aus der jedes Buch dieses Wikis seine
Kategorien zieht (alle Teilbücher wie Medizin oder Geschichte teilen sich einen Abzug):

- `seite(titel, id)`: Artikel (Namensraum 0, ohne Weiterleitungen)
- `kat(id, titel)`: sichtbare Kategorien (Ziele im Namensraum 14 ohne versteckte)
- `kseite(seite, kat)`: Artikel in Kategorie
- `kante(unter, ober)`: Kategorie in Kategorie"""

from __future__ import annotations

import gzip
import json
import logging
import os
import re
import sqlite3
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

logger = logging.getLogger("nachschlag.kategorien")

QUELLE = "https://dumps.wikimedia.org"
TABELLEN = ("page", "linktarget", "categorylinks", "page_props")
#: so lange gilt ein geladener Abzug
ALTER_TAGE = 30
#: Fassung der aufbereiteten Datei je Wiki (neu aufbereiten, wenn sie sich ändert)
FASSUNG = 1
STUECK = 1 << 20
#: oberste Kategorie je Wiki, wo es eine gibt (Einstieg in den Baum)
WURZELN = {"dewiki": "!Hauptkategorie", "enwiki": "Contents"}

_ZEILE = {
    "page": re.compile(rb"\((\d+),(0|14),'((?:[^'\\]|\\.)*)',([01]),"),
    "linktarget": re.compile(rb"\((\d+),14,'((?:[^'\\]|\\.)*)'\)"),
    "categorylinks": re.compile(rb"\((\d+),'(?:[^'\\]|\\.)*','[^']*','(?:[^'\\]|\\.)*','(page|subcat)',\d+,(\d+)\)"),
    "page_props": re.compile(rb"\((\d+),'hiddencat',"),
}
_MASKE = re.compile(rb"\\(.)")


def _titel(roh: bytes) -> str:
    return _MASKE.sub(rb"\1", roh).decode("utf-8", "replace")


@dataclass
class Fortschritt:
    schritt: str
    erledigt: int
    gesamt: int


class Abzuege:
    def __init__(self, ordner: Path, client: httpx.Client | None = None, *, quelle: str = QUELLE,
                 alter_tage: float = ALTER_TAGE) -> None:
        self._ordner, self._quelle, self._alter = ordner, quelle.rstrip("/"), alter_tage * 86400
        self._client = client or httpx.Client(timeout=httpx.Timeout(30.0, read=120.0), follow_redirects=True,
                                              headers={"User-Agent": "Nachschlag-Indexdienst/1"})

    def datei(self, wiki: str) -> Path:
        return self._ordner / f"{wiki}.sqlite"

    def bereit(self, wiki: str, melden: Callable[[Fortschritt], None] = lambda _f: None,
               abbrechen: Callable[[], bool] = lambda: False) -> Path | None:
        """Die aufbereitete Datei des Wikis, wenn nötig vorher geladen und aufbereitet; abgebrochen: None."""
        roh = self._ordner / wiki
        roh.mkdir(parents=True, exist_ok=True)
        neu = False
        for tabelle in (*TABELLEN, "siteinfo-namespaces"):
            pfad = roh / self._name(wiki, tabelle)
            if not pfad.exists() or time.time() - pfad.stat().st_mtime > self._alter:
                if not self._laden(wiki, tabelle, pfad, melden, abbrechen):
                    return None
                neu = True
        ziel = self.datei(wiki)
        if neu or not self._gueltig(ziel):
            if not self._aufbereiten(wiki, roh, ziel, melden, abbrechen):
                return None
        return ziel

    # ----- Laden -----------------------------------------------------------------------------------------------------

    @staticmethod
    def _name(wiki: str, tabelle: str) -> str:
        return f"{wiki}-latest-{tabelle}.json.gz" if tabelle == "siteinfo-namespaces" else f"{wiki}-latest-{tabelle}.sql.gz"

    def _laden(self, wiki: str, tabelle: str, pfad: Path, melden: Callable[[Fortschritt], None],
               abbrechen: Callable[[], bool]) -> bool:
        """Fortsetzbar: eine Teildatei wächst, bis sie vollständig ist, und ersetzt dann die alte."""
        teil = pfad.with_name(pfad.name + ".teil")
        adresse = f"{self._quelle}/{wiki}/latest/{pfad.name}"
        da = teil.stat().st_size if teil.exists() else 0
        kopf = {"Range": f"bytes={da}-"} if da else {}
        with self._client.stream("GET", adresse, headers=kopf) as antwort:
            if antwort.status_code == 416:                 # schon ganz da
                teil.replace(pfad)
                return True
            antwort.raise_for_status()
            if antwort.status_code == 200:
                da = 0
            gesamt = da + int(antwort.headers.get("content-length", 0))
            with open(teil, "ab" if da else "wb") as f:
                for stueck in antwort.iter_bytes(STUECK):
                    f.write(stueck)
                    da += len(stueck)
                    melden(Fortschritt(f"lädt {pfad.name}", da, gesamt))
                    if abbrechen():
                        return False
            stand = antwort.headers.get("last-modified")
        teil.replace(pfad)
        if stand:                                           # die Datei trägt den Tag des Abzugs, nicht den des Ladens
            zeit = parsedate_to_datetime(stand).timestamp()
            if time.time() - zeit < self._alter:
                os.utime(pfad, (zeit, zeit))
        logger.info("Datenabzug geladen: %s (%d MB)", pfad.name, da >> 20)
        return True

    # ----- Aufbereiten -----------------------------------------------------------------------------------------------

    @staticmethod
    def _gueltig(ziel: Path) -> bool:
        try:
            v = sqlite3.connect(f"file:{ziel}?mode=ro", uri=True)
            try:
                z = dict(v.execute("SELECT schluessel, wert FROM angaben").fetchall())
            finally:
                v.close()
            return z.get("fertig") == "1" and z.get("fassung") == str(FASSUNG)
        except sqlite3.DatabaseError:
            return False

    @staticmethod
    def _zeilen(pfad: Path, muster: re.Pattern[bytes], melden: Callable[[Fortschritt], None],
                abbrechen: Callable[[], bool]) -> Iterator:
        gesamt = pfad.stat().st_size
        with open(pfad, "rb") as roh, gzip.open(roh) as f:
            for n, zeile in enumerate(f):      # alle Werte hinter einem INSERT oder (heute) eine Zeile je Datensatz
                if zeile.startswith((b"(", b"INSERT INTO")):
                    yield from muster.findall(zeile)
                if n % 100_000 == 0:
                    melden(Fortschritt(f"liest {pfad.name}", roh.tell(), gesamt))
                    if abbrechen():
                        raise InterruptedError

    def _aufbereiten(self, wiki: str, roh: Path, ziel: Path, melden: Callable[[Fortschritt], None],
                     abbrechen: Callable[[], bool]) -> bool:
        teil = ziel.with_name(ziel.name + ".teil")
        teil.unlink(missing_ok=True)
        v = sqlite3.connect(teil)
        v.executescript("""
            PRAGMA journal_mode = OFF; PRAGMA synchronous = OFF; PRAGMA cache_size = -400000;
            CREATE TABLE angaben (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
            CREATE TABLE p (id INTEGER PRIMARY KEY, ns INTEGER NOT NULL, titel TEXT NOT NULL);
            CREATE TABLE lt (id INTEGER PRIMARY KEY, titel TEXT NOT NULL);
            CREATE TABLE cl (von INTEGER NOT NULL, ziel INTEGER NOT NULL, unter INTEGER NOT NULL);
            CREATE TABLE versteckt (seite INTEGER PRIMARY KEY);""")
        quelle = lambda t: roh / self._name(wiki, t)   # noqa: E731
        try:
            v.executemany("INSERT INTO p VALUES (?, ?, ?)",
                          ((int(i), int(ns), _titel(t)) for i, ns, t, umleitung
                           in self._zeilen(quelle("page"), _ZEILE["page"], melden, abbrechen) if umleitung == b"0" or ns == b"14"))
            v.executemany("INSERT INTO lt VALUES (?, ?)", ((int(i), _titel(t)) for i, t
                                                            in self._zeilen(quelle("linktarget"), _ZEILE["linktarget"], melden, abbrechen)))
            v.executemany("INSERT INTO cl VALUES (?, ?, ?)", ((int(von), int(ziel), art == b"subcat") for von, art, ziel
                                                              in self._zeilen(quelle("categorylinks"), _ZEILE["categorylinks"], melden, abbrechen)))
            v.executemany("INSERT OR IGNORE INTO versteckt VALUES (?)",   # ein Muster mit einer Gruppe liefert die Gruppe selbst
                          ((int(i),) for i in self._zeilen(quelle("page_props"), _ZEILE["page_props"], melden, abbrechen)))
        except InterruptedError:
            v.close()
            return False
        melden(Fortschritt("ordnet die Kategorien", 0, 0))
        namen = json.loads(gzip.decompress(quelle("siteinfo-namespaces").read_bytes()))
        namensraum = namen["query"]["namespaces"]["14"]["*"]
        stand = time.strftime("%Y-%m-%d", time.localtime(quelle("categorylinks").stat().st_mtime))
        v.executescript("""
            CREATE INDEX p_titel ON p (ns, titel);
            CREATE INDEX lt_titel ON lt (titel);
            -- versteckte Kategorien als Ziele (über den Titel ihrer Kategorieseite)
            CREATE TABLE vz (id INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO vz SELECT lt.id FROM versteckt v JOIN p ON p.id = v.seite AND p.ns = 14 JOIN lt ON lt.titel = p.titel;
            CREATE TABLE kat (id INTEGER PRIMARY KEY, titel TEXT NOT NULL);
            INSERT INTO kat SELECT id, titel FROM lt WHERE id NOT IN (SELECT id FROM vz);
            CREATE TABLE seite (titel TEXT PRIMARY KEY, id INTEGER NOT NULL) WITHOUT ROWID;
            INSERT OR IGNORE INTO seite SELECT titel, id FROM p WHERE ns = 0;
            CREATE TABLE kseite (seite INTEGER NOT NULL, kat INTEGER NOT NULL, PRIMARY KEY (seite, kat)) WITHOUT ROWID;
            INSERT OR IGNORE INTO kseite SELECT cl.von, cl.ziel FROM cl JOIN p ON p.id = cl.von AND p.ns = 0
                WHERE cl.unter = 0 AND cl.ziel IN (SELECT id FROM kat);
            -- Kategorie in Kategorie: die Kategorieseite (von) als Ziel über ihren Titel
            CREATE TABLE kante (unter INTEGER NOT NULL, ober INTEGER NOT NULL, PRIMARY KEY (unter, ober)) WITHOUT ROWID;
            INSERT OR IGNORE INTO kante SELECT k.id, cl.ziel FROM cl JOIN p ON p.id = cl.von AND p.ns = 14
                JOIN kat k ON k.titel = p.titel WHERE cl.unter = 1 AND cl.ziel IN (SELECT id FROM kat);
            DROP TABLE cl; DROP TABLE p; DROP TABLE lt; DROP TABLE versteckt; DROP TABLE vz;
            CREATE INDEX kseite_kat ON kseite (kat);""")
        with v:
            v.executemany("INSERT INTO angaben VALUES (?, ?)", [("wiki", wiki), ("stand", stand), ("namensraum", namensraum),
                                                                ("wurzel", WURZELN.get(wiki, "")), ("fassung", str(FASSUNG)),
                                                                ("fertig", "1")])
        v.execute("VACUUM")
        v.close()
        teil.replace(ziel)
        logger.info("Datenabzug %s aufbereitet (Stand %s)", wiki, stand)
        return True
