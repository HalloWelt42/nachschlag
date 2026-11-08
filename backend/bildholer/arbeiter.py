"""Die Schleife des Bildholers: nimmt die nächsten Namen aus der Schlange, fragt ihre Angaben bei der Bildquelle ab und
lädt die Bilder eins nach dem anderen, mit der eingestellten Pause dazwischen. Holt nichts, wenn er aus oder angehalten
ist, außerhalb der Nacht (Regel "nachts"), wenn die Platzgrenze erreicht ist oder die Schlange leer ist. Drosselt die
Quelle, wartet er ihre Zeit ab und verdoppelt die Pause (bis höchstens zehn Minuten; nach einer Stunde ohne Drosselung
gilt wieder die eingestellte) oder hält an, je nach Regel."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path

import httpx

from . import ablage
from .modelle import Regeln, Stand
from .quelle import JE_ANFRAGE, Abgelehnt, Bildquelle, Gedrosselt
from .schlange import Schlange

logger = logging.getLogger("bildholer")

#: Pause, wenn nichts zu tun ist (Schlange leer, Tag, voll)
RUHE_S = 20.0
LANGSAMER_HOECHSTENS_S = 600.0
ERHOLUNG_S = 3600.0


def in_der_nacht(r: Regeln, stunde: int) -> bool:
    if r.nacht_von <= r.nacht_bis:
        return r.nacht_von <= stunde < r.nacht_bis
    return stunde >= r.nacht_von or stunde < r.nacht_bis


class Arbeiter:
    def __init__(self, schlange: Schlange, quelle: Bildquelle, ordner: Path, *, ruhe_s: float = RUHE_S,
                 schlafen=asyncio.sleep, uhr=datetime.now) -> None:
        self._s, self._q, self._ordner = schlange, quelle, ordner
        self._ruhe, self._schlafen, self._uhr = ruhe_s, schlafen, uhr
        self._abstand_extra = 1.0           # Faktor nach Drosselung
        self._gedrosselt_am = 0.0
        self._grund = ""
        self._abgelehnt = False             # angehalten, weil die Quelle den Absender ablehnte
        self._wecker = asyncio.Event()

    def regeln_geaendert(self) -> None:
        """Neue Regeln (etwa ein Absender mit Kontakt): nach einer Ablehnung gleich wieder versuchen."""
        if self._abgelehnt:
            self.fortsetzen()
        self.wecken()

    def fortsetzen(self) -> None:
        self._abgelehnt = False
        self._grund = ""
        self._abstand_extra = 1.0
        self._s.anhalten(False)
        self.wecken()

    def wecken(self) -> None:
        """Etwas Neues ist vorgemerkt oder die Regeln haben sich geändert: nicht erst die Ruhe abwarten."""
        self._wecker.set()

    def _abstand(self, r: Regeln) -> float:
        if self._abstand_extra > 1 and time.monotonic() - self._gedrosselt_am > ERHOLUNG_S:
            self._abstand_extra = 1.0
        return min(r.abstand_s * self._abstand_extra, max(LANGSAMER_HOECHSTENS_S, r.abstand_s))

    def _hindernis(self, r: Regeln) -> tuple[str, str]:
        """Warum gerade nichts geholt wird (Zustand, Grund); leer: es geht."""
        z = self._s.zahlen()
        if not r.an:
            return "aus", "in den Einstellungen ausgeschaltet"
        if self._s.angehalten():
            return "angehalten", self._grund or "von Hand angehalten"
        if z["belegt"] >= r.platz_gb * 1e9:
            return "voll", f"Platzgrenze von {r.platz_gb:g} GB erreicht"
        if r.wann == "nachts" and not in_der_nacht(r, self._uhr().hour):
            return "ruht", f"holt nur nachts ({r.nacht_von} bis {r.nacht_bis} Uhr)"
        if not self._s.offen():
            return "wartet", "nichts vorgemerkt"
        return "", ""

    def stand(self) -> Stand:
        r = self._s.regeln()
        zustand, grund = self._hindernis(r)
        z = self._s.zahlen()
        return Stand(zustand=zustand or "laeuft", grund=grund, abstand_s=self._abstand(r), geladen=z["geladen"],
                     heute=z["heute"], belegt_bytes=z["belegt"], platz_bytes=int(r.platz_gb * 1e9),
                     fehlgeschlagen=z["fehlgeschlagen"], offen=self._s.offen(), zuletzt=self._s.zuletzt())

    async def _warten(self, sekunden: float) -> None:
        self._wecker.clear()
        try:
            await asyncio.wait_for(self._wecker.wait(), sekunden)
        except TimeoutError:
            pass

    async def laufen(self) -> None:
        while True:
            try:
                if not await self.runde():
                    await self._warten(self._ruhe)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - die Schleife läuft weiter; der Fehler steht im Protokoll
                logger.exception("Runde gescheitert")
                await self._warten(self._ruhe)

    async def runde(self) -> bool:
        """Ein Stapel aus der Schlange; False, wenn es nichts zu tun gab."""
        r = self._s.regeln()
        if self._hindernis(r)[0]:
            return False
        stapel = self._s.naechste(JE_ANFRAGE)
        if not stapel:
            return False
        quelle, namen = stapel
        try:
            angaben = await self._q.angaben(quelle, namen, r.breite, r.absender)
            for name in namen:
                if self._hindernis(self._s.regeln())[0]:
                    return True
                datei = angaben.get(name)
                if datei is None:
                    self._s.fehlt(quelle, name, "nicht in der Quelle")
                    continue
                try:
                    inhalt = await self._q.laden(datei.adresse, r.absender)
                except (httpx.HTTPStatusError, ValueError) as f:
                    self._s.fehlt(quelle, name, str(f))
                    continue
                ablage.ablegen(self._ordner, inhalt, ablage.Angaben(
                    quelle=quelle, name=name, breite=datei.breite, hoehe=datei.hoehe, original=datei.original,
                    bytes=len(inhalt), mime=datei.mime, urheber=datei.urheber, lizenz=datei.lizenz,
                    lizenz_url=datei.lizenz_url, seite_url=datei.seite_url, am=self._uhr().astimezone().isoformat(timespec="seconds")))
                self._s.geholt(quelle, name, datei.breite, datei.original, len(inhalt))
                await self._schlafen(self._abstand(r))
        except Gedrosselt as g:
            self._gedrosselt_am = time.monotonic()
            if r.bei_drosselung == "anhalten":
                self._grund = f"Bildquelle drosselt ({g.warten_s:g} s); angehalten nach Regel"
                self._s.anhalten(True)
            else:
                self._abstand_extra = min(self._abstand_extra * 2, LANGSAMER_HOECHSTENS_S / max(r.abstand_s, 1))
                logger.info("Bildquelle drosselt: %g s warten, Pause jetzt %g s", g.warten_s, self._abstand(r))
                await self._schlafen(g.warten_s)
        except Abgelehnt as f:                       # nicht wieder und wieder anklopfen: anhalten, bis die Regeln passen
            self._grund = str(f)
            self._abgelehnt = True
            self._s.anhalten(True)
        except httpx.TransportError as f:          # Netz weg: später wieder
            logger.info("Bildquelle nicht erreichbar (%s)", f)
            await self._schlafen(self._ruhe)
        return True
