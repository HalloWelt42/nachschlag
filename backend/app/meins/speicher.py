"""Speicher für Meins in der Datenbank der App (je Konto): Merkzettel, Notizen, eigene Beispiele, Verlauf mit Lesestand,
Vorlieben. Bücher stehen hier mit ihrem Namen ohne Datum; welche Datei heute dazu gehört, sagt die Bibliothek."""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from appkern.app.begleiter import Begleiter
from appkern.datenbank import Datenbank

from ..modell.meins import (Beispiel, BeispielAenderung, BeispielNeu, Bewertung, BewertungNeu, Lesestand, Merkeintrag, Merken, Notiz, NotizAenderung,
                            Notizbild, NotizNeu, Suchmeldung, Verlaufseintrag)

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
""", """
CREATE TABLE notizen (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, buch_name TEXT NOT NULL, pfad TEXT NOT NULL, titel TEXT NOT NULL,
  bild TEXT NOT NULL DEFAULT '', abschnitt TEXT NOT NULL DEFAULT '', zitat TEXT NOT NULL DEFAULT '', davor TEXT NOT NULL DEFAULT '',
  text TEXT NOT NULL DEFAULT '', angelegt TEXT NOT NULL, geaendert TEXT NOT NULL);
CREATE INDEX notizen_artikel ON notizen (konto, buch_name, pfad);
CREATE INDEX notizen_neu ON notizen (konto, geaendert DESC);
""", """
-- Recherchemodus (WIKI-31): Belege der Stelle (JSON) und der Artikel im Netz
ALTER TABLE notizen ADD COLUMN belege TEXT NOT NULL DEFAULT '[]';
ALTER TABLE notizen ADD COLUMN quelle_url TEXT NOT NULL DEFAULT '';
""", """
-- Eigene Beispiele (WIKI-48): behaltene Kopien aus Ausprobieren, je Artikel hinter dem Codeblock, aus dem sie stammen
CREATE TABLE beispiele (
  id TEXT PRIMARY KEY, konto TEXT NOT NULL, buch_name TEXT NOT NULL, pfad TEXT NOT NULL, titel TEXT NOT NULL,
  sprache TEXT NOT NULL, code TEXT NOT NULL, vorlage TEXT NOT NULL DEFAULT '', block INTEGER NOT NULL DEFAULT -1,
  angelegt TEXT NOT NULL, geaendert TEXT NOT NULL);
CREATE INDEX beispiele_artikel ON beispiele (konto, buch_name, pfad);
""", """
-- PHP-Fassung, in der ein eigenes Beispiel lief (WIKI-52)
ALTER TABLE beispiele ADD COLUMN fassung TEXT NOT NULL DEFAULT '';
""", """
-- Bilder an Notizen (WIKI-51): Liste als JSON, die Dateien liegen in der Ablage (Kellerwolke oder Datenordner)
ALTER TABLE notizen ADD COLUMN bilder TEXT NOT NULL DEFAULT '[]';
""", """
-- Eigene Bewertungen (WIKI-71): je Seite 1 bis 5 Sterne, über Fassungen des Buchs hinweg (Name ohne Stand)
CREATE TABLE bewertungen (
  konto TEXT NOT NULL, buch_name TEXT NOT NULL, pfad TEXT NOT NULL, sterne INTEGER NOT NULL CHECK (sterne BETWEEN 1 AND 5),
  geaendert TEXT NOT NULL, PRIMARY KEY (konto, buch_name, pfad));
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

    async def artikel_aller(self) -> list[tuple[str, str]]:
        """Gelesene und gemerkte Artikel aller Konten als (Kennung der heutigen Fassung, Pfad), etwa für den Bildholer."""
        zeilen = await self._db.zeilen("SELECT DISTINCT buch_name, pfad FROM verlauf WHERE art='artikel' AND pfad != '' "
                                       "UNION SELECT buch_name, pfad FROM merkzettel")
        return [(k, z["pfad"]) for z in zeilen if (k := await self._kennung_von(z["buch_name"]))]

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

    # --- Bewertungen (WIKI-71) -------------------------------------------------------------------------------------
    async def bewertungen(self, konto: str, buch: str) -> list[Bewertung]:
        """Die eigenen Bewertungen der Seiten eines Buchs (über alle Fassungen, die zum Namen gehören)."""
        name = await self._name_von(buch)
        return [Bewertung(**z) for z in await self._db.zeilen(
            "SELECT buch_name, pfad, sterne, geaendert FROM bewertungen WHERE konto=? AND buch_name=?", (konto, name))]

    async def bewerten(self, konto: str, eingabe: BewertungNeu) -> Bewertung | None:
        """Sterne setzen; 0 nimmt die Bewertung weg (dann None)."""
        name = await self._name_von(eingabe.buch)
        if not eingabe.sterne:
            await self._db.ausfuehren("DELETE FROM bewertungen WHERE konto=? AND buch_name=? AND pfad=?", (konto, name, eingabe.pfad))
            return None
        jetzt = _jetzt()
        await self._db.ausfuehren(
            "INSERT INTO bewertungen (konto, buch_name, pfad, sterne, geaendert) VALUES (?,?,?,?,?) "
            "ON CONFLICT(konto, buch_name, pfad) DO UPDATE SET sterne=excluded.sterne, geaendert=excluded.geaendert",
            (konto, name, eingabe.pfad, eingabe.sterne, jetzt))
        return Bewertung(buch_name=name, pfad=eingabe.pfad, sterne=eingabe.sterne, geaendert=jetzt)

    # --- Notizen ---------------------------------------------------------------------------------------------------
    async def notizen(self, konto: str, buch: str = "", pfad: str = "") -> list[Notiz]:
        """Alle Notizen des Kontos, zuletzt geänderte zuerst; mit Buch und Pfad nur die eines Artikels."""
        bedingung, werte = "konto=?", [konto]
        if buch:
            bedingung += " AND buch_name=? AND pfad=?"
            werte += [await self._name_von(buch), pfad]
        zeilen = await self._db.zeilen(f"SELECT * FROM notizen WHERE {bedingung} ORDER BY geaendert DESC", werte)
        kennungen = {n: await self._kennung_von(n) for n in {z["buch_name"] for z in zeilen}}
        return [self._notiz(z, kennungen[z["buch_name"]]) for z in zeilen]

    async def notieren(self, konto: str, eingabe: NotizNeu) -> Notiz:
        jetzt, neu = _jetzt(), str(uuid.uuid4())
        await self._db.ausfuehren(
            "INSERT INTO notizen (id, konto, buch_name, pfad, titel, bild, abschnitt, zitat, davor, text, belege, quelle_url, "
            "angelegt, geaendert) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (neu, konto, await self._name_von(eingabe.buch), eingabe.pfad, eingabe.titel, eingabe.bild, eingabe.abschnitt,
             eingabe.zitat.strip(), eingabe.davor, eingabe.text, json.dumps([b.model_dump() for b in eingabe.belege]),
             eingabe.quelle_url, jetzt, jetzt))
        return await self._notiz_holen(konto, neu)  # type: ignore[return-value]

    async def notiz_aendern(self, konto: str, kennung: str, aenderung: NotizAenderung) -> Notiz | None:
        if not await self._db.ausfuehren("UPDATE notizen SET text=?, geaendert=? WHERE konto=? AND id=?",
                                         (aenderung.text, _jetzt(), konto, kennung)):
            return None
        return await self._notiz_holen(konto, kennung)

    async def notiz_loeschen(self, konto: str, kennung: str) -> bool:
        return await self._db.ausfuehren("DELETE FROM notizen WHERE konto=? AND id=?", (konto, kennung)) > 0

    async def notiz(self, konto: str, kennung: str) -> Notiz | None:
        return await self._notiz_holen(konto, kennung)

    async def bild_anfuegen(self, konto: str, kennung: str, bild: Notizbild) -> Notiz | None:
        """Ein Bild an die Notiz hängen (die Datei liegt schon in der Kellerwolke); die Notiz gilt als geändert."""
        notiz = await self._notiz_holen(konto, kennung)
        if notiz is None:
            return None
        bilder = [b.model_dump() for b in [*notiz.bilder, bild]]
        await self._db.ausfuehren("UPDATE notizen SET bilder=?, geaendert=? WHERE konto=? AND id=?",
                                  (json.dumps(bilder, ensure_ascii=False), _jetzt(), konto, kennung))
        return await self._notiz_holen(konto, kennung)

    async def bild_entfernen(self, konto: str, kennung: str, bild_id: str) -> Notizbild | None:
        """Das Bild aus der Liste der Notiz nehmen; gibt es zurück, damit seine Datei weg kann."""
        notiz = await self._notiz_holen(konto, kennung)
        bild = next((b for b in notiz.bilder if b.id == bild_id), None) if notiz else None
        if bild is None:
            return None
        bilder = [b.model_dump() for b in notiz.bilder if b.id != bild_id]
        await self._db.ausfuehren("UPDATE notizen SET bilder=?, geaendert=? WHERE konto=? AND id=?",
                                  (json.dumps(bilder, ensure_ascii=False), _jetzt(), konto, kennung))
        return bild

    async def _notiz_holen(self, konto: str, kennung: str) -> Notiz | None:
        z = await self._db.zeile("SELECT * FROM notizen WHERE konto=? AND id=?", (konto, kennung))
        return self._notiz(z, await self._kennung_von(z["buch_name"])) if z else None

    @staticmethod
    def _notiz(z: dict, buch: str) -> Notiz:
        werte = {k: z[k] for k in Notiz.model_fields if k in z}
        werte["belege"] = json.loads(z.get("belege") or "[]")
        werte["bilder"] = json.loads(z.get("bilder") or "[]")
        return Notiz(**werte, buch=buch)

    # --- Eigene Beispiele -----------------------------------------------------------------------------------------
    async def beispiele(self, konto: str, buch: str, pfad: str) -> list[Beispiel]:
        """Die eigenen Beispiele eines Artikels, in der Reihenfolge des Anlegens."""
        zeilen = await self._db.zeilen("SELECT * FROM beispiele WHERE konto=? AND buch_name=? AND pfad=? ORDER BY angelegt",
                                       (konto, await self._name_von(buch), pfad))
        return [self._beispiel(z, buch) for z in zeilen]

    async def beispiel_anlegen(self, konto: str, eingabe: BeispielNeu) -> Beispiel:
        jetzt, neu = _jetzt(), str(uuid.uuid4())
        await self._db.ausfuehren(
            "INSERT INTO beispiele (id, konto, buch_name, pfad, titel, sprache, code, vorlage, block, fassung, angelegt, geaendert) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (neu, konto, await self._name_von(eingabe.buch), eingabe.pfad, eingabe.titel.strip(), eingabe.sprache, eingabe.code,
             eingabe.vorlage, eingabe.block, eingabe.fassung, jetzt, jetzt))
        return await self._beispiel_holen(konto, neu)  # type: ignore[return-value]

    async def beispiel_aendern(self, konto: str, kennung: str, aenderung: BeispielAenderung) -> Beispiel | None:
        if not await self._db.ausfuehren("UPDATE beispiele SET titel=?, code=?, fassung=?, geaendert=? WHERE konto=? AND id=?",
                                         (aenderung.titel.strip(), aenderung.code, aenderung.fassung, _jetzt(), konto, kennung)):
            return None
        return await self._beispiel_holen(konto, kennung)

    async def beispiel_loeschen(self, konto: str, kennung: str) -> bool:
        return await self._db.ausfuehren("DELETE FROM beispiele WHERE konto=? AND id=?", (konto, kennung)) > 0

    async def _beispiel_holen(self, konto: str, kennung: str) -> Beispiel | None:
        z = await self._db.zeile("SELECT * FROM beispiele WHERE konto=? AND id=?", (konto, kennung))
        return self._beispiel(z, await self._kennung_von(z["buch_name"])) if z else None

    @staticmethod
    def _beispiel(z: dict, buch: str) -> Beispiel:
        return Beispiel(**{k: z[k] for k in Beispiel.model_fields if k in z}, buch=buch)

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

    async def lesestand_von(self, konto: str, buch: str, pfad: str) -> Verlaufseintrag | None:
        """Der Lesestand einer Seite (etwa der Schritt einer Anleitung in der Werkstatt, WIKI-64); `buch` ist die Kennung,
        gilt über Fassungen hinweg (Name)."""
        z = await self._db.zeile("SELECT * FROM verlauf WHERE konto=? AND art='artikel' AND buch_name=? AND pfad=?",
                                 (konto, await self._name_von(buch), pfad))
        return Verlaufseintrag(**{k: z[k] for k in Verlaufseintrag.model_fields if k in z}, buch=buch) if z else None

    async def gelesen(self, konto: str, buch: str, pfad: str) -> bool:
        """Hat das Konto die Seite schon geöffnet (steht sie im Verlauf)? `buch` ist die Kennung."""
        return await self._db.zeile("SELECT 1 AS ja FROM verlauf WHERE konto=? AND art='artikel' AND buch_name=? AND pfad=?",
                                    (konto, await self._name_von(buch), pfad)) is not None

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
