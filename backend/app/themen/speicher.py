"""Speicher der Themen in der Datenbank der App (je Konto): Themen, Bereiche, Einträge und abgelehnte Angebote. Bücher
stehen mit ihrem Namen ohne Datum; welche Datei heute dazu gehört, sagt die Bibliothek. Lesestand und Notizen der
Einträge kommen aus den Tabellen von Meins (dieselbe Datenbank)."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from appkern.app.begleiter import Begleiter
from appkern.datenbank import Datenbank

from ..modell.themen import (
    Bereich, BereichAenderung, EintragNeu, Thema, ThemaAenderung, Themeneintrag, Themenkopf, ThemaNeu, Verschieben, Zuordnung,
)

STUFEN = ["""
CREATE TABLE themen (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, titel TEXT NOT NULL, beschreibung TEXT NOT NULL DEFAULT '',
  regel TEXT NOT NULL DEFAULT '', regel_buch TEXT NOT NULL DEFAULT '', angelegt TEXT NOT NULL);
CREATE INDEX themen_konto ON themen (konto, angelegt);
CREATE TABLE themen_bereiche (
  id TEXT PRIMARY KEY, thema TEXT NOT NULL, titel TEXT NOT NULL, platz INTEGER NOT NULL);
CREATE INDEX themen_bereiche_thema ON themen_bereiche (thema, platz);
CREATE TABLE themen_eintraege (
  id TEXT PRIMARY KEY, thema TEXT NOT NULL, bereich TEXT NOT NULL DEFAULT '', buch_name TEXT NOT NULL, pfad TEXT NOT NULL,
  titel TEXT NOT NULL, bild TEXT NOT NULL DEFAULT '', platz INTEGER NOT NULL, angelegt TEXT NOT NULL);
CREATE UNIQUE INDEX themen_eintraege_einmal ON themen_eintraege (thema, buch_name, pfad);
CREATE TABLE themen_abgelehnt (thema TEXT NOT NULL, buch_name TEXT NOT NULL, pfad TEXT NOT NULL, PRIMARY KEY (thema, buch_name, pfad));
"""]

#: Wie viele Bilder ein Thema in der Liste zeigt
BILDER_IN_DER_LISTE = 4


def _jetzt() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _neu_ordnen(v: sqlite3.Connection, tabelle: str, bedingung: str, werte: tuple[Any, ...], kennung: str, ziel: int) -> None:
    """Plätze in einer Gruppe neu zählen (0, 1, 2 ...), `kennung` an Stelle `ziel` (darüber hinaus: ans Ende)."""
    ids = [z["id"] for z in v.execute(f"SELECT id FROM {tabelle} WHERE {bedingung} AND id<>? ORDER BY platz, id", (*werte, kennung))]
    ids.insert(min(ziel, len(ids)), kennung)
    v.executemany(f"UPDATE {tabelle} SET platz=? WHERE id=?", list(enumerate(ids)))


class Themen(Begleiter):
    def __init__(self, db: Datenbank, name_von: Callable[[str], Awaitable[str]],
                 kennung_von: Callable[[str], Awaitable[str]]) -> None:
        """`name_von`: Name eines Buchs zu seiner Kennung; `kennung_von`: Kennung des Buchs, das heute zum Namen gehört."""
        self._db, self._name_von, self._kennung_von = db, name_von, kennung_von

    async def starten(self) -> None:
        await self._db.einrichten("nachschlag_themen", STUFEN)

    async def _gehoert(self, konto: str, thema: str) -> bool:
        return await self._db.zeile("SELECT 1 AS ja FROM themen WHERE id=? AND konto=?", (thema, konto)) is not None

    async def _kennung(self, name: str) -> str:
        return await self._kennung_von(name) if name else ""

    # --- Themen ---------------------------------------------------------------------------------------------------
    async def liste(self, konto: str) -> list[Themenkopf]:
        themen = await self._db.zeilen("SELECT id, titel, regel FROM themen WHERE konto=? ORDER BY angelegt", (konto,))
        eintraege = await self._db.zeilen(
            "SELECT e.thema, e.buch_name, e.bild FROM themen_eintraege e JOIN themen t ON t.id=e.thema WHERE t.konto=? "
            "ORDER BY e.bereich='' , e.platz", (konto,))
        bereiche = await self._db.zeilen(
            "SELECT b.thema, COUNT(*) AS zahl FROM themen_bereiche b JOIN themen t ON t.id=b.thema WHERE t.konto=? GROUP BY b.thema",
            (konto,))
        zahl_bereiche = {z["thema"]: z["zahl"] for z in bereiche}
        koepfe = []
        for t in themen:
            eigene = [e for e in eintraege if e["thema"] == t["id"]]
            koepfe.append(Themenkopf(id=t["id"], titel=t["titel"], regel=t["regel"], eintraege=len(eigene),
                                     bereiche=zahl_bereiche.get(t["id"], 0), buecher=len({e["buch_name"] for e in eigene}),
                                     bilder=[e["bild"] for e in eigene if e["bild"]][:BILDER_IN_DER_LISTE]))
        return koepfe

    async def anlegen(self, konto: str, neu: ThemaNeu) -> Thema:
        kennung = str(uuid.uuid4())
        await self._db.ausfuehren(
            "INSERT INTO themen (id, konto, titel, beschreibung, regel, regel_buch, angelegt) VALUES (?,?,?,?,?,?,?)",
            (kennung, konto, neu.titel.strip(), neu.beschreibung.strip(), neu.regel.strip(),
             await self._name_von(neu.regel_buch) if neu.regel_buch else "", _jetzt()))
        return await self.thema(konto, kennung)  # type: ignore[return-value]

    async def thema(self, konto: str, kennung: str) -> Thema | None:
        t = await self._db.zeile("SELECT * FROM themen WHERE id=? AND konto=?", (kennung, konto))
        if not t:
            return None
        bereiche = await self._db.zeilen("SELECT id, titel, platz FROM themen_bereiche WHERE thema=? ORDER BY platz", (kennung,))
        zeilen = await self._db.zeilen(
            "SELECT e.*, COALESCE(v.anteil, 0) AS anteil, v.id IS NOT NULL AS gelesen_je, "
            "(SELECT COUNT(*) FROM notizen n WHERE n.konto=? AND n.buch_name=e.buch_name AND n.pfad=e.pfad) AS notizen "
            "FROM themen_eintraege e LEFT JOIN verlauf v ON v.konto=? AND v.art='artikel' AND v.buch_name=e.buch_name "
            "AND v.pfad=e.pfad WHERE e.thema=? ORDER BY e.platz, e.angelegt", (konto, konto, kennung))
        kennungen = {n: await self._kennung(n) for n in {z["buch_name"] for z in zeilen}}
        return Thema(id=t["id"], titel=t["titel"], beschreibung=t["beschreibung"], regel=t["regel"],
                     regel_buch=await self._kennung(t["regel_buch"]), angelegt=t["angelegt"],
                     bereiche=[Bereich(**b) for b in bereiche],
                     eintraege=[Themeneintrag(**{k: z[k] for k in Themeneintrag.model_fields if k in z},
                                              buch=kennungen[z["buch_name"]]) for z in zeilen])

    async def aendern(self, konto: str, kennung: str, aenderung: ThemaAenderung) -> Thema | None:
        werte = aenderung.model_dump(exclude_none=True)
        if "regel_buch" in werte:
            werte["regel_buch"] = await self._name_von(werte["regel_buch"]) if werte["regel_buch"] else ""
        werte = {k: w.strip() if isinstance(w, str) else w for k, w in werte.items()}
        if werte:
            gesetzt = ", ".join(f"{k}=?" for k in werte)
            await self._db.ausfuehren(f"UPDATE themen SET {gesetzt} WHERE id=? AND konto=?", (*werte.values(), kennung, konto))
        return await self.thema(konto, kennung)

    async def loeschen(self, konto: str, kennung: str) -> bool:
        if not await self._gehoert(konto, kennung):
            return False

        def arbeit(v: sqlite3.Connection) -> None:
            for tabelle in ("themen_eintraege", "themen_bereiche", "themen_abgelehnt"):
                v.execute(f"DELETE FROM {tabelle} WHERE thema=?", (kennung,))
            v.execute("DELETE FROM themen WHERE id=?", (kennung,))

        await self._db.transaktion(arbeit)
        return True

    # --- Bereiche -------------------------------------------------------------------------------------------------
    async def bereich_anlegen(self, konto: str, thema: str, titel: str) -> Bereich | None:
        if not await self._gehoert(konto, thema):
            return None
        kennung = str(uuid.uuid4())
        await self._db.ausfuehren(
            "INSERT INTO themen_bereiche (id, thema, titel, platz) "
            "VALUES (?,?,?,(SELECT COALESCE(MAX(platz) + 1, 0) FROM themen_bereiche WHERE thema=?))",
            (kennung, thema, titel.strip(), thema))
        return Bereich(**await self._db.zeile("SELECT id, titel, platz FROM themen_bereiche WHERE id=?", (kennung,)))  # type: ignore[arg-type]

    async def bereich_aendern(self, konto: str, thema: str, kennung: str, aenderung: BereichAenderung) -> bool:
        if not await self._gehoert(konto, thema):
            return False
        if aenderung.titel is not None and not await self._db.ausfuehren(
                "UPDATE themen_bereiche SET titel=? WHERE id=? AND thema=?", (aenderung.titel.strip(), kennung, thema)):
            return False
        if aenderung.platz is not None:
            if not await self._db.zeile("SELECT 1 AS ja FROM themen_bereiche WHERE id=? AND thema=?", (kennung, thema)):
                return False
            await self._db.transaktion(lambda v: _neu_ordnen(v, "themen_bereiche", "thema=?", (thema,), kennung, aenderung.platz))
        return True

    async def bereich_loeschen(self, konto: str, thema: str, kennung: str) -> bool:
        """Der Bereich geht, seine Artikel bleiben im Thema (ohne Bereich)."""
        if not await self._gehoert(konto, thema):
            return False

        def arbeit(v: sqlite3.Connection) -> bool:
            if not v.execute("DELETE FROM themen_bereiche WHERE id=? AND thema=?", (kennung, thema)).rowcount:
                return False
            ende = v.execute("SELECT COALESCE(MAX(platz) + 1, 0) AS ende FROM themen_eintraege WHERE thema=? AND bereich=''",
                             (thema,)).fetchone()["ende"]
            v.execute("UPDATE themen_eintraege SET bereich='', platz=platz+? WHERE thema=? AND bereich=?", (ende, thema, kennung))
            return True

        return await self._db.transaktion(arbeit)

    # --- Einträge -------------------------------------------------------------------------------------------------
    async def eintragen(self, konto: str, thema: str, neu: EintragNeu) -> Themeneintrag | None:
        """Ein Artikel ins Thema (zweimal bleibt einer); ein früher abgelehntes Angebot gilt dann nicht mehr als abgelehnt."""
        if not await self._gehoert(konto, thema):
            return None
        if neu.bereich and not await self._db.zeile("SELECT 1 AS ja FROM themen_bereiche WHERE id=? AND thema=?", (neu.bereich, thema)):
            return None
        name = await self._name_von(neu.buch)

        def arbeit(v: sqlite3.Connection) -> None:
            v.execute(
                "INSERT INTO themen_eintraege (id, thema, bereich, buch_name, pfad, titel, bild, platz, angelegt) VALUES "
                "(?,?,?,?,?,?,?,(SELECT COALESCE(MAX(platz) + 1, 0) FROM themen_eintraege WHERE thema=? AND bereich=?),?) "
                "ON CONFLICT(thema, buch_name, pfad) DO NOTHING",
                (str(uuid.uuid4()), thema, neu.bereich, name, neu.pfad, neu.titel, neu.bild, thema, neu.bereich, _jetzt()))
            v.execute("DELETE FROM themen_abgelehnt WHERE thema=? AND buch_name=? AND pfad=?", (thema, name, neu.pfad))

        await self._db.transaktion(arbeit)
        t = await self.thema(konto, thema)
        return next((e for e in t.eintraege if e.buch_name == name and e.pfad == neu.pfad), None) if t else None

    async def verschieben(self, konto: str, thema: str, kennung: str, ziel: Verschieben) -> bool:
        if not await self._gehoert(konto, thema):
            return False
        if ziel.bereich and not await self._db.zeile("SELECT 1 AS ja FROM themen_bereiche WHERE id=? AND thema=?", (ziel.bereich, thema)):
            return False

        def arbeit(v: sqlite3.Connection) -> bool:
            if not v.execute("UPDATE themen_eintraege SET bereich=? WHERE id=? AND thema=?", (ziel.bereich, kennung, thema)).rowcount:
                return False
            _neu_ordnen(v, "themen_eintraege", "thema=? AND bereich=?", (thema, ziel.bereich), kennung, ziel.platz)
            return True

        return await self._db.transaktion(arbeit)

    async def austragen(self, konto: str, thema: str, kennung: str) -> bool:
        if not await self._gehoert(konto, thema):
            return False
        return await self._db.ausfuehren("DELETE FROM themen_eintraege WHERE id=? AND thema=?", (kennung, thema)) > 0

    # --- Angebote der gespeicherten Suche -------------------------------------------------------------------------
    async def ablehnen(self, konto: str, thema: str, buch: str, pfad: str) -> bool:
        if not await self._gehoert(konto, thema):
            return False
        await self._db.ausfuehren("INSERT OR IGNORE INTO themen_abgelehnt (thema, buch_name, pfad) VALUES (?,?,?)",
                                  (thema, await self._name_von(buch), pfad))
        return True

    async def bekannt(self, thema: str) -> set[tuple[str, str]]:
        """Was kein Angebot mehr ist: schon im Thema oder abgelehnt (Buchname, Pfad)."""
        zeilen = await self._db.zeilen("SELECT buch_name, pfad FROM themen_eintraege WHERE thema=? "
                                       "UNION SELECT buch_name, pfad FROM themen_abgelehnt WHERE thema=?", (thema, thema))
        return {(z["buch_name"], z["pfad"]) for z in zeilen}

    # --- Zuordnung ------------------------------------------------------------------------------------------------
    async def zuordnung(self, konto: str) -> list[Zuordnung]:
        """Jeder Artikel in jedem Thema des Kontos (Artikelkopf und Notizen zeigen damit ihre Themen)."""
        zeilen = await self._db.zeilen(
            "SELECT e.thema, t.titel, e.id AS eintrag, e.buch_name, e.pfad FROM themen_eintraege e JOIN themen t ON t.id=e.thema "
            "WHERE t.konto=? ORDER BY t.angelegt", (konto,))
        return [Zuordnung(**z) for z in zeilen]
