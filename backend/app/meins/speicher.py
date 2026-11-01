"""Speicher für Meins in der Datenbank der App (je Konto): Merkzettel, Verlauf mit Lesestand, Vorlieben. Bücher stehen
hier mit ihrem Namen ohne Datum; welche Datei heute dazu gehört, sagt die Bibliothek."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from appkern.app.begleiter import Begleiter
from appkern.datenbank import Datenbank

from ..modell.meins import Lesestand, Merkeintrag, Merken, Suchmeldung, Verlaufseintrag

STUFEN = ["""
CREATE TABLE merkzettel (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, buch_name TEXT NOT NULL, pfad TEXT NOT NULL, titel TEXT NOT NULL,
  bild TEXT NOT NULL DEFAULT '', abschnitt TEXT NOT NULL DEFAULT '', angelegt TEXT NOT NULL);
CREATE UNIQUE INDEX merkzettel_einmal ON merkzettel (konto, buch_name, pfad, abschnitt);
CREATE TABLE verlauf (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, art TEXT NOT NULL, buch_name TEXT NOT NULL DEFAULT '', pfad TEXT NOT NULL DEFAULT '',
  titel TEXT NOT NULL DEFAULT '', bild TEXT NOT NULL DEFAULT '', abschnitt TEXT NOT NULL DEFAULT '', anteil REAL NOT NULL DEFAULT 0,
  sekunden INTEGER NOT NULL DEFAULT 0, frage TEXT NOT NULL DEFAULT '', treffer INTEGER NOT NULL DEFAULT 0, zuletzt TEXT NOT NULL);
CREATE UNIQUE INDEX verlauf_einmal ON verlauf (konto, art, buch_name, pfad, frage);
CREATE INDEX verlauf_zuletzt ON verlauf (konto, zuletzt DESC);
CREATE TABLE vorlieben (konto TEXT NOT NULL, schluessel TEXT NOT NULL, wert TEXT NOT NULL, PRIMARY KEY (konto, schluessel));
"""]

#: Wie viele Einträge der Verlauf je Konto höchstens behält (älteste fallen beim Schreiben weg)
VERLAUF_HOECHSTENS = 5000


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")   # fein genug, dass die Reihenfolge stimmt


class Meins(Begleiter):
    def __init__(self, db: Datenbank, name_von: Callable[[str], Awaitable[str]],
                 kennung_von: Callable[[str], Awaitable[str]]) -> None:
        """`name_von`: Name eines Buchs zu seiner Kennung; `kennung_von`: Kennung des Buchs, das heute zum Namen gehört."""
        self._db, self._name_von, self._kennung_von = db, name_von, kennung_von

    async def starten(self) -> None:
        """Begleiter des Gerüsts: das eigene Schema beim Start einrichten (nach der Datenbank, vor den Aufträgen)."""
        await self._db.einrichten("nachschlag_meins", STUFEN)

    # --- Merkzettel -----------------------------------------------------------------------------------------------
    async def merkzettel(self, konto: str) -> list[Merkeintrag]:
        zeilen = await self._db.zeilen(
            "SELECT m.*, COALESCE(v.anteil, 0) AS anteil FROM merkzettel m LEFT JOIN verlauf v ON v.konto=m.konto "
            "AND v.art='artikel' AND v.buch_name=m.buch_name AND v.pfad=m.pfad WHERE m.konto=? ORDER BY m.angelegt DESC", (konto,))
        return [Merkeintrag(**{k: z[k] for k in Merkeintrag.model_fields if k in z}, buch=await self._kennung_von(z["buch_name"]))
                for z in zeilen]

    async def merken(self, konto: str, eingabe: Merken) -> Merkeintrag:
        name = await self._name_von(eingabe.buch)
        neu = str(uuid.uuid4())
        await self._db.ausfuehren(
            "INSERT INTO merkzettel (id, konto, buch_name, pfad, titel, bild, abschnitt, angelegt) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(konto, buch_name, pfad, abschnitt) DO UPDATE SET titel=excluded.titel, bild=excluded.bild",
            (neu, konto, name, eingabe.pfad, eingabe.titel, eingabe.bild, eingabe.abschnitt, _jetzt()))
        z = await self._db.zeile("SELECT * FROM merkzettel WHERE konto=? AND buch_name=? AND pfad=? AND abschnitt=?",
                                 (konto, name, eingabe.pfad, eingabe.abschnitt))
        return Merkeintrag(**{k: z[k] for k in Merkeintrag.model_fields if k in z}, buch=eingabe.buch)

    async def vergessen(self, konto: str, kennung: str) -> bool:
        return await self._db.ausfuehren("DELETE FROM merkzettel WHERE konto=? AND id=?", (konto, kennung)) > 0

    # --- Verlauf --------------------------------------------------------------------------------------------------
    async def lesestand(self, konto: str, stand: Lesestand) -> None:
        """Lesestand einer Seite: Anteil und Stelle zuletzt, Lesezeit zusammengezählt; jüngster Besuch vorn."""
        name = await self._name_von(stand.buch)
        await self._db.ausfuehren(
            "INSERT INTO verlauf (id, konto, art, buch_name, pfad, titel, bild, abschnitt, anteil, sekunden, zuletzt) "
            "VALUES (?,?,'artikel',?,?,?,?,?,?,?,?) ON CONFLICT(konto, art, buch_name, pfad, frage) DO UPDATE SET "
            "titel=excluded.titel, bild=excluded.bild, abschnitt=excluded.abschnitt, anteil=excluded.anteil, "
            "sekunden=verlauf.sekunden+excluded.sekunden, zuletzt=excluded.zuletzt",
            (str(uuid.uuid4()), konto, name, stand.pfad, stand.titel, stand.bild, stand.abschnitt, stand.anteil,
             stand.sekunden, _jetzt()))
        await self._kuerzen(konto)

    async def gesucht(self, konto: str, meldung: Suchmeldung) -> None:
        await self._db.ausfuehren(
            "INSERT INTO verlauf (id, konto, art, frage, treffer, zuletzt) VALUES (?,?,'suche',?,?,?) "
            "ON CONFLICT(konto, art, buch_name, pfad, frage) DO UPDATE SET treffer=excluded.treffer, zuletzt=excluded.zuletzt",
            (str(uuid.uuid4()), konto, meldung.frage.strip(), meldung.treffer, _jetzt()))
        await self._kuerzen(konto)

    async def _kuerzen(self, konto: str) -> None:
        await self._db.ausfuehren(
            "DELETE FROM verlauf WHERE konto=? AND id NOT IN (SELECT id FROM verlauf WHERE konto=? ORDER BY zuletzt DESC LIMIT ?)",
            (konto, konto, VERLAUF_HOECHSTENS))

    async def verlauf(self, konto: str, anzahl: int = 50, ab: int = 0, art: str = "") -> list[Verlaufseintrag]:
        filter_art = " AND art=?" if art else ""
        werte = (konto, art, anzahl, ab) if art else (konto, anzahl, ab)
        zeilen = await self._db.zeilen(f"SELECT * FROM verlauf WHERE konto=?{filter_art} ORDER BY zuletzt DESC LIMIT ? OFFSET ?", werte)
        return [Verlaufseintrag(**{k: z[k] for k in Verlaufseintrag.model_fields if k in z},
                                buch=await self._kennung_von(z["buch_name"]) if z["buch_name"] else "") for z in zeilen]

    async def verlauf_leeren(self, konto: str) -> int:
        return await self._db.ausfuehren("DELETE FROM verlauf WHERE konto=?", (konto,))

    # --- Vorlieben ------------------------------------------------------------------------------------------------
    async def vorlieben(self, konto: str) -> dict[str, str]:
        return {z["schluessel"]: z["wert"] for z in await self._db.zeilen("SELECT schluessel, wert FROM vorlieben WHERE konto=?", (konto,))}

    async def vorliebe(self, konto: str, schluessel: str, wert: str) -> None:
        if wert:
            await self._db.ausfuehren("INSERT INTO vorlieben (konto, schluessel, wert) VALUES (?,?,?) ON CONFLICT(konto, schluessel) "
                                      "DO UPDATE SET wert=excluded.wert", (konto, schluessel, wert))
        else:
            await self._db.ausfuehren("DELETE FROM vorlieben WHERE konto=? AND schluessel=?", (konto, schluessel))
