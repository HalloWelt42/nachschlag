"""Index-Dienst auf dem Mac (WIKI-17, docs/SUCHE.md Punkte 4 und 15): holt sich bei Nachschlag auf dem Pi den
laufenden Index-Auftrag ab, baut den Index aus dem Buch, das er über die Freigabe liest, meldet den Fortschritt und
lädt die fertige Datei in Stücken hoch. Er ruft nur an; am Mac lauscht nichts im Netz.

Fehlertolerant (der Mac ist ein Laptop mit WLAN):
- Lesefehler über die Freigabe (Netz weg, Ruhezustand, Netzwechsel): Bau anhalten, "wartet auf Netz" melden, Freigabe
  neu einhängen, mit wachsendem Abstand dort fortsetzen, wo die Indexdatei steht.
- Pi nicht erreichbar: weiterbauen, später melden; das Hochladen setzt dort fort, wo die Datei auf dem Pi endet.
- Bricht der Pi den Auftrag ab (410), lässt der Dienst ihn fallen; der halbe Index bleibt für einen neuen Anlauf."""

from __future__ import annotations

import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import httpx

from ..artikel import wege
from ..bibliothek import Bibliothek, BuchFehlt
from ..eigenindex import aufbau, schema
from ..eigenindex.auftrag import Abholung

logger = logging.getLogger("nachschlag.indexdienst")

#: Abstände der Versuche nach einem Fehler (Sekunden); danach bleibt es beim letzten
ABSTAENDE = (5, 10, 20, 40, 80, 160, 300)
#: So lange Pause, wenn kein Auftrag läuft
RUHE_S = 30.0
#: Stück der Übertragung
STUECK = 8 << 20


class PiFehlt(Exception):
    """Nachschlag auf dem Pi antwortet nicht (Netz, Neustart)."""


class AuftragWeg(Exception):
    """Der Pi kennt den Auftrag nicht mehr (abgebrochen, fertig)."""


def einhaengen_mit(freigabe: str, ordner: Path) -> Callable[[], None]:
    """Hängt die Freigabe (//guest@rechner/name) nur lesend unter `ordner` ein, wenn sie dort fehlt oder hängt."""
    def einhaengen() -> None:
        if ordner.is_mount():
            try:
                next(ordner.iterdir(), None)
                return
            except OSError:
                subprocess.run(["umount", "-f", str(ordner)], capture_output=True, timeout=30)
        ordner.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["mount_smbfs", "-N", "-o", "rdonly", freigabe, str(ordner)], capture_output=True, text=True,
                           timeout=60)
        if r.returncode:
            logger.warning("Freigabe ließ sich nicht einhängen: %s", r.stderr.strip())
    return einhaengen


class Arbeiter:
    def __init__(self, pi: httpx.Client, buecher: Path, ziel: Path, einhaengen: Callable[[], None] | None = None, *,
                 abstaende: tuple[float, ...] = ABSTAENDE, ruhe_s: float = RUHE_S, stueck: int = STUECK) -> None:
        """`pi`: Verbindung zu Nachschlag auf dem Pi (Adresse, Schlüssel, Zertifikatsstelle schon eingestellt)."""
        self._pi, self._buecher, self._ziel, self._einhaengen = pi, buecher, ziel, einhaengen
        self._abstaende, self._ruhe, self._stueck = abstaende, ruhe_s, stueck
        self._bibliothek = Bibliothek(lambda: str(buecher))

    def _abstand(self, versuch: int) -> float:
        return self._abstaende[min(versuch, len(self._abstaende) - 1)]

    # ----- Anrufe beim Pi --------------------------------------------------------------------------------------------

    def _anruf(self, methode: str, pfad: str, **weiter) -> httpx.Response:
        try:
            antwort = self._pi.request(methode, f"/api/v1/indexdienst{pfad}", **weiter)
        except httpx.TransportError as f:
            raise PiFehlt(type(f).__name__) from f
        if antwort.status_code == 410:
            raise AuftragWeg(pfad)
        if antwort.status_code >= 500:
            raise PiFehlt(f"Status {antwort.status_code}")
        return antwort

    def _melden(self, a: Abholung, **stand) -> None:
        """Fortschritt an den Pi; ist er gerade weg, baut der Dienst trotzdem weiter."""
        try:
            self._anruf("PUT", f"/{a.auftrag}/stand", json=stand)
        except PiFehlt:
            pass

    # ----- Ablauf ----------------------------------------------------------------------------------------------------

    def laufen(self, halt: threading.Event) -> None:
        versuch = 0
        while not halt.is_set():
            try:
                antwort = self._anruf("POST", "/abholen")
                antwort.raise_for_status()
                versuch = 0
                if antwort.status_code == 204:
                    halt.wait(self._ruhe)
                    continue
                self.erledigen(Abholung.model_validate(antwort.json()), halt)
            except PiFehlt as f:
                logger.info("Pi nicht erreichbar (%s), nächster Versuch in %s s", f, self._abstand(versuch))
                halt.wait(self._abstand(versuch))
                versuch += 1
            except AuftragWeg:
                logger.info("Der Pi hat den Auftrag beendet; nächster")
            except httpx.HTTPStatusError as f:      # etwa 401: falscher Schlüssel; nicht in schneller Folge wiederholen
                logger.error("Pi lehnt ab: %s %s", f.response.status_code, f.response.text[:200])
                halt.wait(self._abstaende[-1])

    def erledigen(self, a: Abholung, halt: threading.Event) -> None:
        """Ein Auftrag: bauen (oder fortsetzen), hochladen, fertig melden."""
        datei = self._ziel / schema.dateiname(a.buch)
        self._ziel.mkdir(parents=True, exist_ok=True)
        stand = self._bauen(a, datei, halt)
        if stand is None or not stand.fertig:
            return
        self._hochladen(a, datei, halt)
        if halt.is_set():
            return
        summe = datei.with_suffix(".sha256").read_text().strip()
        self._anruf("POST", f"/{a.auftrag}/fertig",
                    json={"pruefsumme": summe, "groesse": datei.stat().st_size, "seiten": stand.seiten}).raise_for_status()
        logger.info("Index %s übergeben (%d Seiten)", a.buch, stand.seiten)

    def _bauen(self, a: Abholung, datei: Path, halt: threading.Event) -> aufbau.Stand | None:
        weg = threading.Event()                     # der Pi hat den Auftrag beendet

        def melden(s: aufbau.Stand) -> None:
            try:
                self._melden(a, zustand="laeuft", erledigt=s.erledigt, gesamt=s.gesamt, seiten=s.seiten)
            except AuftragWeg:
                weg.set()

        versuch = 0
        while not (halt.is_set() or weg.is_set()):
            try:
                archiv, buch = self._bibliothek.geoeffnet(a.buch)
                stand = aufbau.bauen(archiv, buch, wege(self._bibliothek), datei, melden=melden,
                                     abbrechen=lambda: halt.is_set() or weg.is_set())
                return stand
            except (OSError, RuntimeError, BuchFehlt) as f:
                abstand = self._abstand(versuch)
                versuch += 1
                logger.warning("Lesen von %s gestört (%s), nächster Versuch in %s s", a.buch, f, abstand)
                self._melden(a, zustand="wartet_auf_netz", meldung=f"wartet auf Netz, nächster Versuch in {abstand:g} s")
                self._bibliothek = Bibliothek(lambda: str(self._buecher))   # offene Dateien sind nach Netzwechsel tot
                if halt.wait(abstand):
                    return None
                if self._einhaengen:
                    self._einhaengen()
            except Exception as f:   # noqa: BLE001 - ein Fehler im Baustein geht als Meldung an den Auftrag
                logger.exception("Index von %s gescheitert", a.buch)
                self._anruf("POST", f"/{a.auftrag}/fehler", json={"meldung": (str(f) or type(f).__name__)[:500]})
                return None
        return None

    def _hochladen(self, a: Abholung, datei: Path, halt: threading.Event) -> None:
        """In Stücken ab dem Stand auf dem Pi; ein Abbruch (Netz, Neustart) setzt beim nächsten Abholen dort fort."""
        gesamt = datei.stat().st_size
        da = a.da if a.da <= gesamt else 0
        with open(datei, "rb") as f:
            while da < gesamt and not halt.is_set():
                f.seek(da)
                antwort = self._anruf("PUT", f"/{a.auftrag}/datei", params={"ab": da, "gesamt": gesamt},
                                      content=f.read(self._stueck), headers={"Content-Type": "application/octet-stream"})
                if antwort.status_code == 409:              # der Pi hat einen anderen Stand: ab dort weiter
                    da = self._anruf("GET", f"/{a.auftrag}/datei").json()["da"]
                    da = 0 if da > gesamt else da
                    continue
                antwort.raise_for_status()
                da = antwort.json()["da"]
