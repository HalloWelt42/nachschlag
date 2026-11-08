"""Nachschlag und der Bildholer: Ablage lesen, vormerken, Regeln schicken, Stand holen."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from urllib.parse import unquote

import httpx

from appkern.app.begleiter import Begleiter
from appkern.app.geruest import Verbindung
from bildholer import ablage
from bildholer.ablage import Angaben
from bildholer.modelle import Regeln, Stand, Vormerkung

from ..artikel import Artikelleser
from ..bibliothek import BuchFehlt, EintragFehlt
from ..kategorien.wikis import host
from ..modell.artikel import Artikel

logger = logging.getLogger("nachschlag.bilder")

#: so oft gehen die Regeln an den Bildholer (er merkt sich die letzten; nach seinem Neustart gelten sie so bald wieder)
TAKT_S = 60.0
#: so oft kommen neu Gelesenes, Gemerktes und Themen dazu
STUFE_S = 3600.0

_GROSS = re.compile(r'<img\b[^>]*\bdata-gross="\d+"[^>]*>')
_SRC = re.compile(r'\bsrc="/api/v1/inhalt/medien/[^/"]+/([^"]+)"')


def wiki_name(pfad: str) -> str | None:
    """Der Dateiname im Wiki zu einem Bild im Buch (`_assets_/<Prüfsumme>/<Name>`); kein solches Bild: None. Eine als
    PNG gerechnete SVG heißt im Wiki wie die SVG, ein umgewandeltes WebP wie das Original."""
    teile = pfad.split("/")
    if len(teile) != 3 or teile[0] != "_assets_" or not teile[2]:
        return None
    name = unquote(teile[2])
    klein = name.lower()
    if klein.endswith(".svg.png"):
        return name[:-4]
    if klein.endswith(".webp") and "." in name[:-5]:
        return name[:-5]
    return name


def grosse_bilder(html: str) -> list[str]:
    """Pfade im Buch der Bilder eines aufbereiteten Artikels, zu denen es ein deutlich größeres Original gibt."""
    return [unquote(m.group(1)) for img in _GROSS.finditer(html) if (m := _SRC.search(img.group(0)))]


class Grossbilder(Begleiter):
    def __init__(self, ordner: Callable[[], str], adresse: Callable[[], str], regeln: Callable[[], Regeln],
                 beim_oeffnen: Callable[[], bool], leser: Artikelleser,
                 artikelquellen: list[Callable[[], Awaitable[list[tuple[str, str]]]]],
                 client: httpx.AsyncClient | None = None, *, takt_s: float = TAKT_S, stufe_s: float = STUFE_S) -> None:
        """`artikelquellen`: liefern (Buch, Pfad) gelesener, gemerkter und thematisierter Artikel (Vorrang 1)."""
        self._ordner, self._adresse, self._regeln = ordner, adresse, regeln
        self._beim_oeffnen, self._leser, self._quellen = beim_oeffnen, leser, artikelquellen
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(5.0))
        self._takt, self._stufe = takt_s, stufe_s
        self._geschickt: Regeln | None = None
        self._erledigt: set[tuple[str, str]] = set()
        self._aufgabe: asyncio.Task | None = None
        self._erreicht = False

    # ----- Ablage ----------------------------------------------------------------------------------------------------

    def finden(self, buch: str, pfad: str) -> tuple[Path, Angaben] | None:
        """Das große Bild zu einem Bild im Buch, wenn der Bildholer es schon geholt hat."""
        quelle, name, ordner = host(buch), wiki_name(pfad), self._ordner()
        if not (quelle and name and ordner):
            return None
        return ablage.lesen(Path(ordner), quelle, name)

    # ----- Gespräch mit dem Bildholer --------------------------------------------------------------------------------

    async def _anruf(self, methode: str, weg: str, **weiter) -> httpx.Response | None:
        adresse = self._adresse().rstrip("/")
        if not adresse:
            return None
        try:
            antwort = await self._client.request(methode, f"{adresse}/api/v1{weg}", **weiter)
            antwort.raise_for_status()
            self._erreicht = True
            return antwort
        except httpx.HTTPError as f:
            if self._erreicht:
                logger.info("Bildholer nicht erreichbar: %s", f)
            self._erreicht = False
            self._geschickt = None                  # nach seiner Rückkehr die Regeln erneut schicken
            return None

    async def regeln_schicken(self) -> None:
        regeln = self._regeln()
        if regeln != self._geschickt and await self._anruf("PUT", "/regeln", json=regeln.model_dump()):
            self._geschickt = regeln

    async def vormerken(self, buch: str, pfade: list[str], vorrang: int) -> int:
        quelle = host(buch)
        namen = list(dict.fromkeys(n for p in pfade if (n := wiki_name(p))))
        if not (quelle and namen):
            return 0
        await self.regeln_schicken()
        antwort = await self._anruf("POST", "/vormerken",
                                    json=Vormerkung(quelle=quelle, namen=namen, vorrang=vorrang).model_dump())
        return antwort.json().get("vorgemerkt", 0) if antwort else 0

    async def geoeffnet(self, artikel: Artikel) -> None:
        """Ein Artikel wurde geöffnet: seine großen Bilder als Nächstes (wenn eingestellt)."""
        if self._beim_oeffnen() and host(artikel.buch):
            pfade = grosse_bilder(artikel.html)
            if pfade:
                await self.vormerken(artikel.buch, pfade, 0)
            self._erledigt.add((artikel.buch, artikel.pfad))

    async def stand(self) -> Stand | None:
        antwort = await self._anruf("GET", "/stand")
        return Stand.model_validate(antwort.json()) if antwort else None

    async def anhalten(self, an: bool) -> Stand | None:
        antwort = await self._anruf("POST", "/anhalten" if an else "/fortsetzen")
        return Stand.model_validate(antwort.json()) if antwort else None

    async def verbindung(self) -> Verbindung:
        if not self._adresse():
            return Verbindung(name="Bildholer", ok=False, meldung="nicht eingerichtet")
        s = await self.stand()
        if s is None:
            return Verbindung(name="Bildholer", ok=False, meldung="antwortet nicht")
        return Verbindung(name="Bildholer", ok=True, meldung=s.grund or "holt große Bilder")

    # ----- Begleiter: Regeln und Vorrang 1 ---------------------------------------------------------------------------

    async def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._regelmaessig())

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()
        await self._client.aclose()

    async def _regelmaessig(self) -> None:
        naechste_stufe = 0.0
        while True:
            try:
                await self.regeln_schicken()
                if self._erreicht and asyncio.get_running_loop().time() >= naechste_stufe:
                    await self.gelesene_vormerken()
                    naechste_stufe = asyncio.get_running_loop().time() + self._stufe
            except Exception:  # noqa: BLE001 - beim nächsten Takt wieder
                logger.exception("Bilder vormerken gescheitert")
            await asyncio.sleep(self._takt)

    async def gelesene_vormerken(self) -> int:
        """Gelesenes, Gemerktes und Themen (Vorrang 1): je Artikel einmal je Lauf von Nachschlag."""
        neu = 0
        for quelle in self._quellen:
            for buch, pfad in await quelle():
                if (buch, pfad) in self._erledigt or not host(buch):
                    continue
                try:
                    artikel = await self._leser.lesen(buch, pfad)
                except (BuchFehlt, EintragFehlt):
                    self._erledigt.add((buch, pfad))
                    continue
                neu += await self.vormerken(buch, grosse_bilder(artikel.html), 1)
                if not self._erreicht:              # Bildholer weg: beim nächsten Mal weiter
                    return neu
                self._erledigt.add((buch, pfad))
        return neu
