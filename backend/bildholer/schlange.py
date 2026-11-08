"""Warteschlange, Zähler und Regeln des Bildholers in einer SQLite-Datei in seinem Datenordner.

Vorrang 0 (gerade geöffnet) kommt immer zuerst, die jüngste Vormerkung vorn: ein neu geöffneter Artikel springt nach
vorn. Vorrang 1 (gelesen, gemerkt, in Themen) der Reihe nach. Eine Datei, die es in der Quelle nicht gibt, wird nicht
wieder vorgemerkt."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from pathlib import Path

from .modelle import Bildzeile, Regeln

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS warte (quelle TEXT NOT NULL, name TEXT NOT NULL, vorrang INTEGER NOT NULL,
                                  eingereiht REAL NOT NULL, PRIMARY KEY (quelle, name)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS warte_folge ON warte (vorrang, eingereiht);
CREATE TABLE IF NOT EXISTS geholt (quelle TEXT NOT NULL, name TEXT NOT NULL, breite INTEGER NOT NULL,
                                   original INTEGER NOT NULL, bytes INTEGER NOT NULL, am TEXT NOT NULL,
                                   PRIMARY KEY (quelle, name)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS geholt_am ON geholt (am);
CREATE TABLE IF NOT EXISTS fehlt (quelle TEXT NOT NULL, name TEXT NOT NULL, grund TEXT NOT NULL, am TEXT NOT NULL,
                                  PRIMARY KEY (quelle, name)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS zustand (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL);
"""


def _jetzt() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Schlange:
    def __init__(self, datei: Path) -> None:
        datei.parent.mkdir(parents=True, exist_ok=True)
        self._v = sqlite3.connect(datei, check_same_thread=False, isolation_level=None)
        self._v.executescript(SCHEMA)

    def _wert(self, schluessel: str) -> str | None:
        z = self._v.execute("SELECT wert FROM zustand WHERE schluessel=?", (schluessel,)).fetchone()
        return z[0] if z else None

    def _setzen(self, schluessel: str, wert: str) -> None:
        self._v.execute("INSERT INTO zustand VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
                        (schluessel, wert))

    # ----- Regeln und Anhalten ---------------------------------------------------------------------------------------

    def regeln(self) -> Regeln:
        roh = self._wert("regeln")
        return Regeln.model_validate_json(roh) if roh else Regeln()

    def regeln_setzen(self, regeln: Regeln) -> None:
        self._setzen("regeln", regeln.model_dump_json())

    def angehalten(self) -> bool:
        return self._wert("angehalten") == "1"

    def anhalten(self, an: bool) -> None:
        self._setzen("angehalten", "1" if an else "0")

    # ----- Warteschlange ---------------------------------------------------------------------------------------------

    def vormerken(self, quelle: str, namen: list[str], vorrang: int) -> int:
        """Merkt Namen vor (ohne die schon geholten und die, die es in der Quelle nicht gibt); ein höherer Vorrang zieht
        eine Vormerkung nach vorn. Gibt zurück, wie viele neu oder vorgezogen sind."""
        jetzt = time.time()
        vorher = self._v.total_changes
        with self._v:
            self._v.execute("BEGIN")
            for name in dict.fromkeys(namen):
                if self._v.execute("SELECT 1 FROM geholt WHERE quelle=? AND name=? UNION ALL "
                                   "SELECT 1 FROM fehlt WHERE quelle=? AND name=?", (quelle, name, quelle, name)).fetchone():
                    continue
                self._v.execute("INSERT INTO warte VALUES (?, ?, ?, ?) ON CONFLICT(quelle, name) DO UPDATE SET "
                                "vorrang=excluded.vorrang, eingereiht=excluded.eingereiht "
                                "WHERE excluded.vorrang < warte.vorrang OR excluded.vorrang = 0",
                                (quelle, name, vorrang, jetzt))
        return self._v.total_changes - vorher

    def naechste(self, anzahl: int) -> tuple[str, list[str]] | None:
        """Die nächsten Namen aus einer Quelle (die des vordersten Eintrags), in der Reihenfolge der Schlange."""
        erste = self._v.execute("SELECT quelle FROM warte ORDER BY vorrang, "
                                "CASE WHEN vorrang = 0 THEN -eingereiht ELSE eingereiht END LIMIT 1").fetchone()
        if not erste:
            return None
        namen = [z[0] for z in self._v.execute(
            "SELECT name FROM warte WHERE quelle=? ORDER BY vorrang, CASE WHEN vorrang = 0 THEN -eingereiht ELSE eingereiht END "
            "LIMIT ?", (erste[0], anzahl))]
        return erste[0], namen

    def geholt(self, quelle: str, name: str, breite: int, original: int, groesse: int) -> None:
        with self._v:
            self._v.execute("BEGIN")
            self._v.execute("DELETE FROM warte WHERE quelle=? AND name=?", (quelle, name))
            self._v.execute("INSERT OR REPLACE INTO geholt VALUES (?, ?, ?, ?, ?, ?)",
                            (quelle, name, breite, original, groesse, _jetzt()))

    def fehlt(self, quelle: str, name: str, grund: str) -> None:
        with self._v:
            self._v.execute("BEGIN")
            self._v.execute("DELETE FROM warte WHERE quelle=? AND name=?", (quelle, name))
            self._v.execute("INSERT OR REPLACE INTO fehlt VALUES (?, ?, ?, ?)", (quelle, name, grund[:300], _jetzt()))

    # ----- Zahlen für den Stand --------------------------------------------------------------------------------------

    def zahlen(self) -> dict[str, int]:
        heute = datetime.now().astimezone().date().isoformat()
        geladen, belegt = self._v.execute("SELECT COUNT(*), COALESCE(SUM(bytes), 0) FROM geholt").fetchone()
        return {"geladen": geladen, "belegt": belegt,
                "heute": self._v.execute("SELECT COUNT(*) FROM geholt WHERE am >= ?", (heute,)).fetchone()[0],
                "fehlgeschlagen": self._v.execute("SELECT COUNT(*) FROM fehlt").fetchone()[0]}

    def offen(self) -> dict[str, int]:
        return {str(v): n for v, n in self._v.execute("SELECT vorrang, COUNT(*) FROM warte GROUP BY vorrang")}

    def zuletzt(self, anzahl: int = 6) -> list[Bildzeile]:
        return [Bildzeile(quelle=q, name=n, breite=b, original=o, am=am) for q, n, b, o, am in self._v.execute(
            "SELECT quelle, name, breite, original, am FROM geholt ORDER BY am DESC LIMIT ?", (anzahl,))]
