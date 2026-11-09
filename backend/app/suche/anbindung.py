"""Anbindung der Bedeutungssuche an den Fundus (WIKI-56): welche Sammlung und welches Buch gelten. Gewählt wird in den
Einstellungen (Suche), die Sammlung aus der Liste des Fundus. Solange dort nichts steht, findet Nachschlag beides
selbst: die Sammlung, in die die Lexikon-Quelle des Fundus schreibt, und das Buch, dessen Datei der Fundus gerade
einliest. Das Gefundene gilt bis zum nächsten Abgleich (beim Start, nach jedem Neuaufbau der Zugänge, dann alle zehn
Minuten); ohne Fundus bleibt die Suche beim Index.

Der Abgleich läuft immer im Hintergrund, auch der erste (WIKI-86): die Liste der Sammlungen braucht beim Fundus bisweilen
eine halbe Minute und länger (gemessen 09.11.2026: 25 bis 50 s), und solange der Start nicht fertig ist, nimmt die App
keine Anfrage an. Bis zum ersten Abgleich sucht Nachschlag nur im Index, wie ohne Fundus."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

from appkern.app import Begleiter
from appkern.einstellungen import Angebot, Option
from appkern.verbund import Verbund, VerbundFehler

logger = logging.getLogger(__name__)

TAKT_S = 600.0
LEXIKON = "lexikon"                     # Art der Quelle, mit der der Fundus ein Buch der Bibliothek einliest
ZIM = re.compile(r"\.zim$")


class Bedeutungsanbindung(Begleiter):
    def __init__(self, verbund: Callable[[], Verbund], adresse: Callable[[], str], sammlung_gewaehlt: Callable[[], str],
                 buch_gewaehlt: Callable[[], str], buecher: Callable[[], Awaitable[list[str]]],
                 juengste_fassung: Callable[[str], Awaitable[str]], takt_s: float = TAKT_S) -> None:
        """`buecher()`: Kennungen der Bücher in der Bibliothek; `juengste_fassung(kennung)`: dieselbe Ausgabe im
        jüngsten Stand."""
        self._verbund, self._adresse = verbund, adresse
        self._sammlung_gewaehlt, self._buch_gewaehlt = sammlung_gewaehlt, buch_gewaehlt
        self._buecher, self._juengste = buecher, juengste_fassung
        self._takt_s = takt_s
        self._sammlungen: list[dict[str, Any]] = []
        self._auto_sammlung = ""
        self._auto_buch = ""
        self._aufgabe: asyncio.Task | None = None
        self._anstoss = asyncio.Event()          # neu abgleichen, ohne den Takt abzuwarten (etwa nach neuen Zugängen)
        self._abgeglichen = False                # der erste Abgleich ist durch

    # --- was gilt ----------------------------------------------------------------------------------------------------

    def sammlung(self) -> str:
        return self._sammlung_gewaehlt().strip() or self._auto_sammlung

    async def buch(self) -> str:
        gewaehlt = self._buch_gewaehlt().strip()
        return await self._juengste(gewaehlt) if gewaehlt else self._auto_buch

    # --- Abgleich mit dem Fundus -------------------------------------------------------------------------------------

    async def abgleichen(self) -> None:
        if not self._adresse().strip():
            self._sammlungen, self._auto_sammlung, self._auto_buch = [], "", ""
            return
        try:
            antwort = await self._verbund().anfrage("GET", self._adresse(), "/api/v1/sammlungen", params={"anzahl": 200})
            self._sammlungen = antwort.json().get("eintraege", [])
            dateien = (await self._verbund().anfrage("GET", self._adresse(), "/api/v1/quellenstand/dateien")).json()
        except (VerbundFehler, ValueError) as f:
            logger.info("Bedeutungssuche: Fundus für den Abgleich nicht erreichbar (%s)", getattr(f, "meldung", f))
            return
        lexikon = [s["sammlung"]["kennung"] for s in self._sammlungen if any(q.get("art") == LEXIKON for q in s.get("quellen", []))]
        self._auto_sammlung = lexikon[0] if len(lexikon) == 1 else ""
        vorhanden = set(await self._buecher())
        gelesen = sorted({ZIM.sub("", d) for d in dateien.get("dateien", [])} & vorhanden)
        self._auto_buch = await self._juengste(gelesen[-1]) if gelesen else ""

    async def _takt(self) -> None:
        """Gleicht ab, dann wieder nach dem Takt oder sobald etwas anstößt; ein Anstoß während eines Abgleichs gilt für
        den nächsten, einer davor erledigt sich mit ihm."""
        while True:
            self._anstoss.clear()
            try:
                await self.abgleichen()
            except Exception:  # noqa: BLE001 - die Anbindung versucht es zum nächsten Takt wieder
                logger.exception("Bedeutungssuche: Abgleich gescheitert")
            self._abgeglichen = True
            try:
                await asyncio.wait_for(self._anstoss.wait(), self._takt_s)
            except TimeoutError:
                pass

    async def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._takt(), name="bedeutungsanbindung")

    async def verbunden(self) -> None:
        """Neue Zugänge: bald neu abgleichen. Beim Start nicht, dort stehen die Zugänge vor dem ersten Abgleich fest (ein
        zweiter hieße noch einmal eine halbe Minute Arbeit für den Fundus)."""
        if self._abgeglichen:
            self._anstoss.set()

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()

    # --- Einstellungen: die Sammlungen des Fundus als Auswahl -------------------------------------------------------

    async def angebot(self) -> Angebot:
        await self.abgleichen()
        optionen = [Option(wert=s["sammlung"]["kennung"], titel=s["sammlung"]["name"],
                           hinweis=f"{s['sammlung'].get('dokumente', 0)} Dokumente") for s in self._sammlungen]
        if not self._adresse().strip():
            stand = "kein Fundus angebunden (Verbindungen)"
        elif not self._sammlungen:
            stand = "Fundus antwortet nicht oder hat keine Sammlung"
        elif self._sammlung_gewaehlt().strip():
            stand = f"{len(optionen)} Sammlungen"
        elif self._auto_sammlung:
            name = next((o.titel for o in optionen if o.wert == self._auto_sammlung), self._auto_sammlung)
            stand = f"leer, darum von selbst: {name}"
        else:
            stand = "leer, keine eindeutige Sammlung des Lexikons: bitte wählen"
        return Angebot(optionen=optionen, eigener_wert=True, stand=stand)
