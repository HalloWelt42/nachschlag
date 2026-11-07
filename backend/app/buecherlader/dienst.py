"""Der Bücherlader (WIKI-57, Entscheidungen am Ticket 07.11.2026; Entwurf WIKI-2 "Katalog" und "Fassungen und Laden").

- Durchsicht: nach Zeitplan (Vorgabe wöchentlich) oder auf Knopfdruck das ganze Verzeichnis, nur die gewählten
  Sprachen. Was seit dem letzten Durchgang neu ist (ein Buch oder eine Fassung), meldet Nachschlag in der Bibliothek.
- Abos: ein abonniertes Buch wird geladen, wenn es fehlt oder das Verzeichnis eine neuere Fassung hat als die eigene
  (Einstellung: laden oder nur melden). Immer ein Buch zugleich, fortsetzbar, Prüfsumme (SHA-256) vor allem anderen.
- Platz: frei bleibt immer die Reserve aus den Einstellungen; geprüft vor dem Laden und laufend währenddessen
  (Nutzer 07.11.2026: "achte darauf, Speicherreserve im System zu halten").
- Neue Fassung eines vorhandenen Buchs: wartet geprüft auf das Umschalten (von Hand); die vorige bleibt danach als
  Rückfall und wird nach der Frist entfernt, nie, wenn sie von Hand wieder aktiv gesetzt ist.

Durchsicht und Laden sind Aufträge des Appkerns (Seite Aufträge, Fußleiste). Nachschlag liest die Bücher nur; schreiben
in den Ordner der Bücher tut allein dieser Dienst (ablage.py)."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx
from libzim.reader import Archive
from pydantic import BaseModel

from appkern.app.begleiter import Begleiter
from appkern.auftraege import Art, AuftragFehler, Auftraege, Herkunft, Kontext, Phase
from appkern.auftraege.modelle import Auftrag
from appkern.datenbank import Datenbank

from ..modell.buecherlader import (Abo, Durchgang, Laderstand, Platz, Regeln as Regelanzeige, Rueckfall, Variante,
                                   Verzeichnisbuch, Verzeichnisseite, Zustand)
from ..zeitfenster import ZONE, nachts
from .ablage import Ablage, Lokal
from .bestand import Bestand, Buchzeile, jetzt
from .bibliotheksliste import Bibliotheksliste
from .katalog import KATALOGSPRACHE, Katalogeintrag, eintraege_aus
from .verzeichnis import AUSGABEN, Datei, basis_und_ausgabe, dateien_aus, ordner_aus

logger = logging.getLogger("nachschlag.buecherlader")

DURCHSEHEN = "verzeichnis_durchsehen"
LADEN = "buch_laden"
TAGE = {"taeglich": 1, "woechentlich": 7, "monatlich": 30}
#: so oft sieht der Zeitplan nach, ob eine Durchsicht fällig ist und ob eine vorige Fassung weg kann
WECKER_S = 900
STUECK = 1 << 20
#: so oft prüft das Laden den freien Platz gegen die Reserve
PLATZ_PRUEFEN = 256 << 20
PRUEFSUMME_BLOCK = 64 << 20
BEREICHE_GLEICHZEITIG = 4
GB = 1024**3
PHASEN = (Phase(schluessel="laden", titel="Laden", symbol="download"),
          Phase(schluessel="pruefsumme", titel="Prüfsumme", symbol="fingerprint"),
          Phase(schluessel="oeffnen", titel="Öffnen und zählen", symbol="book-open"),
          Phase(schluessel="ablegen", titel="In die Bibliothek", symbol="box-archive"))
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class Regeln:
    """Die Regeln aus den Einstellungen, bei jedem Gebrauch neu gelesen (Änderungen gelten sofort)."""
    ordner: Path
    verzeichnis: str
    pruefsummen: str
    katalog: str
    sprachen: frozenset[str]
    durchsicht: str
    neue_fassung: str
    laden_wann: str
    fenster: tuple[int, int]
    reserve: int
    hoechstens: int
    vorige_tage: int
    liste: Path | None


class LadeEingabe(BaseModel):
    stamm: str
    ordner: str
    datei: str


class LaderFehler(LookupError):
    """Etwas, das der Nutzer verlangt, geht so nicht (für die Schnittstelle: 409)."""


def gb(n: int) -> str:
    return f"{n / GB:,.1f} GB".replace(",", "X").replace(".", ",").replace("X", ".")


def dauer(sekunden: float) -> str:
    if sekunden < 90:
        return "unter 2 Minuten"
    if sekunden < 5400:
        return f"etwa {round(sekunden / 60)} Minuten"
    return f"etwa {sekunden / 3600:.1f} Stunden".replace(".", ",")


def zustand_aus(neueste: Buchzeile | None, lokal: Lokal | None, wartend: Lokal | None, laedt: bool) -> Zustand:
    """Wie ein Buch zur eigenen Bibliothek steht; eine Regel für Verzeichnis und Abos."""
    if laedt:
        return "laedt"
    if wartend and (not lokal or wartend.stand > lokal.stand):
        return "wartet_auf_umschalten"
    if not lokal:
        return "nicht_da"
    if neueste and neueste.stand > lokal.stand:
        return "neuer_da"
    return "aktuell"


class Buecherlader(Begleiter):
    def __init__(self, db: Datenbank, auftraege: Auftraege, regeln: Callable[[], Regeln],
                 von_hand_aktiv: Callable[[str], Awaitable[bool]], *, transport: httpx.AsyncBaseTransport | None = None,
                 uhr: Callable[[], datetime] = lambda: datetime.now(timezone.utc), zeitplan: bool = True) -> None:
        """`von_hand_aktiv(kennung)`: hat der Nutzer diese Fassung von Hand aktiv gesetzt (Archiv der Quellen)? Dann
        bleibt sie über die Frist hinaus. `zeitplan`: ohne ihn (Tests) läuft `takt` nur, wenn man ihn ruft."""
        self._bestand, self._auftraege, self._regeln = Bestand(db), auftraege, regeln
        self._von_hand_aktiv, self._transport, self._uhr, self._mit_zeitplan = von_hand_aktiv, transport, uhr, zeitplan
        self._wecker: asyncio.Task | None = None
        auftraege.anmelden(
            Art(name=DURCHSEHEN, titel="Verzeichnis der Bücher durchsehen", arbeit=self._durchsehen, hoechstens=1,
                nach_neustart="fortsetzen", herkunft=lambda _e: Herkunft(titel="Zum Katalog", ziel="bibliothek/katalog")),
            Art(name=LADEN, titel="Buch laden", arbeit=self._laden, eingabe=LadeEingabe, phasen=PHASEN, fortsetzbar=True,
                nach_neustart="fortsetzen", hoechstens=1,
                herkunft=lambda _e: Herkunft(titel="Zu Fassungen und Laden", ziel="bibliothek/laden")))

    # ----- Lebenszyklus -----------------------------------------------------------------------------------------------

    async def starten(self) -> None:
        await self._bestand.einrichten()
        if self._mit_zeitplan:
            self._wecker = asyncio.create_task(self._zeitplan(), name="buecherlader")

    async def stoppen(self) -> None:
        if self._wecker:
            self._wecker.cancel()
            await asyncio.gather(self._wecker, return_exceptions=True)

    async def _zeitplan(self) -> None:
        await self._auftraege.gestartet.wait()
        while True:
            try:
                await self.takt()
            except Exception:                                    # noqa: BLE001 - der Zeitplan läuft weiter
                logger.exception("Zeitplan des Bücherladers")
            await asyncio.sleep(WECKER_S)

    async def takt(self) -> None:
        """Was der Zeitplan tut: fällige Durchsicht anstoßen, vorige Fassungen nach der Frist entfernen."""
        r = self._regeln()
        if self._grund(r):
            return
        await self._aufraeumen(r)
        letzter = await self._bestand.letzter_durchgang()
        if letzter and self._uhr() < self._naechste(letzter[1], r):
            return
        if not await self._offene(DURCHSEHEN):
            await self._auftraege.einreihen(DURCHSEHEN, von="Zeitplan")

    def zurueckstellen(self, a: Auftrag) -> str:
        """Regel für die Aufträge: mit "nur nachts" wartet Laden auf das Nachtfenster."""
        if a.art != LADEN:
            return ""
        r = self._regeln()
        if r.laden_wann == "nachts" and not nachts(self._uhr().astimezone(ZONE), *r.fenster):
            return f"lädt nur nachts ({r.fenster[0]} bis {r.fenster[1]} Uhr)"
        return ""

    # ----- Hilfen -----------------------------------------------------------------------------------------------------

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=self._transport, follow_redirects=True, headers={"User-Agent": "Nachschlag"},
                                 timeout=httpx.Timeout(60, connect=15))

    @staticmethod
    def _grund(r: Regeln) -> str:
        if not r.verzeichnis:
            return "Kein Verzeichnis der Bücher eingestellt (Einstellungen, Bücherlader)"
        if not Ablage(r.ordner).beschreibbar():
            return f"In den Ordner der Bücher ({r.ordner}) lässt sich nicht schreiben"
        return ""

    @staticmethod
    def _naechste(d: Durchgang, r: Regeln) -> datetime:
        return datetime.fromisoformat(d.begonnen) + timedelta(days=TAGE[r.durchsicht])

    async def _offene(self, art: str) -> list[Auftrag]:
        return (await self._auftraege.liste(zustand=("wartet", "laeuft"), art=art, grenze=500)).eintraege

    async def _ladende(self) -> dict[str, Auftrag]:
        return {a.eingabe["stamm"]: a for a in await self._offene(LADEN)}

    @staticmethod
    def _platz_fehlt(r: Regeln, ablage: Ablage, noch: int) -> str:
        """Warum `noch` Bytes nicht mehr passen; leer: es passt (Reserve und Grenze für Bücher eingehalten)."""
        frei, _ = ablage.platz()
        if frei - noch < r.reserve:
            return f"Zu wenig Platz: frei {gb(frei)}, gebraucht {gb(noch)}, frei bleiben sollen {gb(r.reserve)}"
        if r.hoechstens:
            buecher, laden = ablage.belegt()
            if buecher + laden + noch > r.hoechstens:
                return f"Grenze für Bücher erreicht: belegt {gb(buecher + laden)}, gebraucht {gb(noch)}, höchstens {gb(r.hoechstens)}"
        return ""

    async def _liste(self, r: Regeln, eintragen: Path | None = None, austragen: str = "") -> None:
        """Die Liste für den Bücherserver nachziehen (wahlweise); ein Fehler dort hält die Bibliothek nicht auf."""
        if not r.liste:
            return
        liste = Bibliotheksliste(r.liste)
        try:
            if eintragen:
                await asyncio.to_thread(liste.eintragen, eintragen)
            if austragen:
                await asyncio.to_thread(liste.austragen, austragen)
        except (OSError, RuntimeError, ET.ParseError) as f:
            logger.warning("Liste der Bücher (%s) nicht nachgezogen: %s", r.liste, f)

    # ----- Durchsicht -------------------------------------------------------------------------------------------------

    async def durchsehen(self, von: str) -> Auftrag:
        """Eine Durchsicht jetzt; läuft schon eine, ist es diese."""
        r = self._regeln()
        if grund := self._grund(r):
            raise LaderFehler(grund)
        offen = await self._offene(DURCHSEHEN)
        return offen[0] if offen else await self._auftraege.einreihen(DURCHSEHEN, von=von)

    async def _durchsehen(self, k: Kontext) -> Durchgang:
        r = self._regeln()
        begonnen, hinweise = jetzt(), []
        async with self._client() as c:
            await k.fortschritt(None, "Verzeichnis lesen")
            try:
                bereiche = ordner_aus(await self._text(c, r.verzeichnis))
            except httpx.HTTPError as f:
                raise AuftragFehler(f"Das Verzeichnis antwortet nicht: {f}") from f
            if not bereiche:
                raise AuftragFehler("Im Verzeichnis stehen keine Bereiche; stimmt die Adresse?")
            dateien = await self._bereiche_lesen(k, c, r, bereiche, hinweise)
            gewaehlt = [d for d in dateien if d.sprache in r.sprachen]
            katalog = await self._katalog_lesen(k, c, r, hinweise)
        await k.fortschritt(None, "Eintragen und vergleichen")
        durchgang = await self._bestand.durchgang_eintragen(
            Durchgang(begonnen=begonnen, beendet=jetzt(), ordner=len(bereiche), dateien=len(gewaehlt),
                      buecher=len({d.stamm for d in gewaehlt}), neue_buecher=0, neue_fassungen=0, erstaufnahme=False,
                      hinweise=hinweise), gewaehlt, katalog)
        await self._abos_pruefen("Durchsicht")
        return durchgang

    @staticmethod
    async def _text(c: httpx.AsyncClient, adresse: str) -> str:
        antwort = await c.get(adresse)
        antwort.raise_for_status()
        return antwort.text

    async def _bereiche_lesen(self, k: Kontext, c: httpx.AsyncClient, r: Regeln, bereiche: list[str],
                              hinweise: list[str]) -> list[Datei]:
        sperre, fertig = asyncio.Semaphore(BEREICHE_GLEICHZEITIG), 0

        async def bereich(name: str) -> list[Datei]:
            nonlocal fertig
            async with sperre:
                await k.pruefen()
                try:
                    html = await self._text(c, urljoin(r.verzeichnis, f"{name}/"))
                except httpx.HTTPError as f:
                    hinweise.append(f"Bereich {name}: {f}")
                    html = ""
            fertig += 1
            await k.fortschritt(fertig / len(bereiche), f"Bereich {fertig} von {len(bereiche)}: {name}")
            return dateien_aus(name, html)

        return [d for teil in await asyncio.gather(*(bereich(b) for b in bereiche)) for d in teil]

    async def _katalog_lesen(self, k: Kontext, c: httpx.AsyncClient, r: Regeln,
                             hinweise: list[str]) -> dict[str, Katalogeintrag]:
        katalog: dict[str, Katalogeintrag] = {}
        if not r.katalog:
            return katalog
        for sprache in sorted(r.sprachen):
            await k.fortschritt(None, f"Titel aus dem Katalog ({sprache})")
            adresse = f"{r.katalog.rstrip('/')}/entries?lang={KATALOGSPRACHE.get(sprache, sprache)}&count=-1"
            try:
                antwort = await c.get(adresse)
                antwort.raise_for_status()
                katalog |= eintraege_aus(antwort.content)
            except (httpx.HTTPError, ET.ParseError) as f:
                hinweise.append(f"Katalog ({sprache}): {f}")
        return katalog

    # ----- Abos -------------------------------------------------------------------------------------------------------

    async def _abos_pruefen(self, von: str, nur: str = "") -> None:
        """Für jedes Abo, das fehlt oder eine neuere Fassung hat, einen Auftrag zum Laden (einmal je Buch)."""
        r = self._regeln()
        if self._grund(r):
            return
        ablage = Ablage(r.ordner)
        aktive, wartende, ladende = ablage.aktive(), ablage.wartende(), await self._ladende()
        for stamm in await self._bestand.abos():
            if (nur and stamm != nur) or stamm in ladende:
                continue
            z = await self._bestand.neueste(stamm)
            lokal, wartend = aktive.get(stamm), wartende.get(stamm)
            vorhanden = max((x.stand for x in (lokal, wartend) if x), default="")
            if not z or z.stand <= vorhanden or (lokal and r.neue_fassung == "melden"):
                continue
            if fehlt := self._platz_fehlt(r, ablage, z.groesse):
                logger.info("%s %s lädt nicht: %s", stamm, z.stand, fehlt)
                continue
            await self._auftraege.einreihen(LADEN, LadeEingabe(stamm=stamm, ordner=z.ordner, datei=z.datei),
                                            titel=f"{z.titel or stamm} laden ({z.stand})", von=von)

    async def abonnieren(self, stamm: str, von: str) -> None:
        if not await self._bestand.neueste(stamm):
            raise LookupError(f"Ein Buch {stamm} steht nicht im Verzeichnis")
        await self._bestand.abonnieren([stamm])
        await self._abos_pruefen(von, nur=stamm)

    async def bestand_abonnieren(self, von: str) -> int:
        """Alle Bücher der eigenen Bibliothek abonnieren (Entscheidung 07.11.2026); liefert, wie viele."""
        staemme = sorted(Ablage(self._regeln().ordner).aktive())
        await self._bestand.abonnieren(staemme)
        await self._abos_pruefen(von)
        return len(staemme)

    async def abbestellen(self, stamm: str) -> None:
        """Kein Abo mehr; lädt es gerade, wird das abgebrochen und die angefangene Datei gelöscht."""
        await self._bestand.abbestellen(stamm)
        laedt = (await self._ladende()).get(stamm)
        if laedt:
            await self._auftraege.abbrechen(laedt.id)
            Ablage(self._regeln().ordner).teil(laedt.eingabe["datei"]).unlink(missing_ok=True)

    # ----- Laden ------------------------------------------------------------------------------------------------------

    async def _laden(self, k: Kontext) -> dict:
        e: LadeEingabe = k.eingabe
        r = self._regeln()
        if grund := self._grund(r):
            raise AuftragFehler(grund)
        ablage = Ablage(r.ordner)
        ablage.laden.mkdir(exist_ok=True)
        teil = ablage.teil(e.datei)
        async with self._client() as c:
            if not k.zwischenstand.get("soll"):
                await k.merken(soll=await self._pruefsumme(c, r, e))
            await self._herunterladen(k, c, r, ablage, urljoin(r.verzeichnis, f"{e.ordner}/{e.datei}"), teil)
        if not k.zwischenstand.get("geprueft"):
            await self._pruefen(k, teil, k.zwischenstand["soll"])
            await k.merken(geprueft=True)
        await k.fortschritt(None, "Datei öffnen und zählen", phase="oeffnen")
        artikel = await asyncio.to_thread(self._oeffnen, teil)
        await k.fortschritt(None, "In die Bibliothek legen", phase="ablegen")
        wartend = e.stamm in ablage.aktive()
        ziel = ablage.ablegen(teil, wartend)
        if not wartend:
            await self._liste(r, eintragen=ziel)
        return {"datei": e.datei, "artikel": artikel, "ort": "wartet aufs Umschalten" if wartend else "Bibliothek"}

    @staticmethod
    async def _pruefsumme(c: httpx.AsyncClient, r: Regeln, e: LadeEingabe) -> str:
        adresse = urljoin(r.pruefsummen, f"{e.ordner}/{e.datei}.sha256")
        try:
            antwort = await c.get(adresse)
            antwort.raise_for_status()
            soll = antwort.text.split()[0].lower() if antwort.text.strip() else ""
        except httpx.HTTPError as f:
            raise AuftragFehler(f"Keine Prüfsumme für {e.datei} ({f}); ohne Prüfsumme lädt der Bücherlader nicht") from f
        if not _SHA256.match(soll):
            raise AuftragFehler(f"Die Prüfsumme für {e.datei} ist unlesbar; ohne Prüfsumme lädt der Bücherlader nicht")
        return soll

    async def _herunterladen(self, k: Kontext, c: httpx.AsyncClient, r: Regeln, ablage: Ablage, adresse: str,
                             teil: Path) -> None:
        """Fortsetzbar in die angefangene Datei; hält an, sobald der freie Platz unter die Reserve fiele."""
        try:
            kopf = await c.head(adresse)
            kopf.raise_for_status()
            gesamt = int(kopf.headers["content-length"])
        except (httpx.HTTPError, KeyError, ValueError) as f:
            raise AuftragFehler(f"Die Datei antwortet nicht: {f}") from f
        schon = teil.stat().st_size if teil.exists() else 0
        if schon > gesamt:
            teil.unlink()
            schon = 0
        if schon == gesamt:
            return
        if fehlt := self._platz_fehlt(r, ablage, gesamt - schon):
            raise AuftragFehler(fehlt)
        await k.fortschritt(schon / gesamt, f"{gb(schon)} von {gb(gesamt)}", phase="laden")
        beginn, ab, seit_pruefung = time.monotonic(), schon, 0
        try:
            async with c.stream("GET", adresse, headers={"Range": f"bytes={schon}-"} if schon else {}) as antwort:
                if antwort.status_code == 200:
                    schon = ab = 0                                 # der Server setzt nicht fort: von vorn
                elif antwort.status_code != 206:
                    raise AuftragFehler(f"Die Datei antwortet mit {antwort.status_code}")
                with teil.open("ab" if schon else "wb") as f:
                    async for stueck in antwort.aiter_bytes(STUECK):
                        await asyncio.to_thread(f.write, stueck)
                        schon += len(stueck)
                        seit_pruefung += len(stueck)
                        await k.pruefen()
                        if seit_pruefung >= PLATZ_PRUEFEN:
                            seit_pruefung = 0
                            frei, _ = ablage.platz()
                            if frei < r.reserve:
                                raise AuftragFehler(f"Laden angehalten: frei nur noch {gb(frei)}, frei bleiben sollen "
                                                    f"{gb(r.reserve)}; Wiederholen setzt fort")
                        tempo = (schon - ab) / max(time.monotonic() - beginn, 0.001)
                        await k.fortschritt(schon / gesamt, f"{gb(schon)} von {gb(gesamt)} · {tempo / 1024**2:.0f} MB/s · "
                                                             f"noch {dauer((gesamt - schon) / max(tempo, 1))}")
        except httpx.HTTPError as f:
            raise AuftragFehler(f"Laden unterbrochen bei {gb(schon)} von {gb(gesamt)}: {f}; Wiederholen setzt fort") from f
        if schon != gesamt:
            raise AuftragFehler(f"Laden unterbrochen bei {gb(schon)} von {gb(gesamt)}; Wiederholen setzt fort")

    @staticmethod
    async def _pruefen(k: Kontext, teil: Path, soll: str) -> None:
        gesamt, gelesen, h = teil.stat().st_size, 0, hashlib.sha256()
        await k.fortschritt(0, "Prüfsumme berechnen", phase="pruefsumme")
        with teil.open("rb") as f:
            while block := await asyncio.to_thread(f.read, PRUEFSUMME_BLOCK):
                await asyncio.to_thread(h.update, block)
                gelesen += len(block)
                await k.pruefen()
                await k.fortschritt(gelesen / gesamt, f"Prüfsumme: {gb(gelesen)} von {gb(gesamt)}")
        if h.hexdigest() != soll:
            teil.unlink()
            raise AuftragFehler("Die Prüfsumme stimmt nicht; die Datei ist gelöscht, Wiederholen lädt sie neu")

    @staticmethod
    def _oeffnen(teil: Path) -> int:
        try:
            return Archive(str(teil)).article_count
        except RuntimeError as f:
            raise AuftragFehler(f"Die geladene Datei lässt sich nicht öffnen: {f}") from f

    # ----- Umschalten, Rückfall, Aufräumen ----------------------------------------------------------------------------

    async def umschalten(self, stamm: str) -> None:
        """Die wartende neue Fassung wird aktiv; die vorige bleibt als Rückfall bis zum Ende der Frist."""
        r = self._regeln()
        ablage = Ablage(r.ordner)
        alt = ablage.aktive().get(stamm)
        try:
            neu = ablage.umschalten(stamm)
        except KeyError:
            raise LaderFehler("Für dieses Buch wartet keine neue Fassung") from None
        await self._liste(r, eintragen=neu.pfad)
        if alt:
            await self._bestand.wechsel_eintragen(stamm, alt.kennung, neu.kennung)

    async def zurueck(self, stamm: str) -> None:
        """Zurück auf die vorige Fassung: die neue wartet wieder aufs Umschalten."""
        r = self._regeln()
        w = next((w for w in await self._bestand.offene_wechsel() if w.stamm == stamm), None)
        if not w or not (r.ordner / f"{w.alt}.zim").is_file():
            raise LaderFehler("Für dieses Buch gibt es keine vorige Fassung mehr")
        Ablage(r.ordner).zuruecklegen(w.neu)
        await self._liste(r, austragen=f"{w.neu}.zim")
        await self._bestand.wechsel_beenden(w, "zurueck")

    async def _aufraeumen(self, r: Regeln) -> None:
        ablage = Ablage(r.ordner)
        for w in await self._bestand.offene_wechsel():
            if self._uhr() < datetime.fromisoformat(w.am) + timedelta(days=r.vorige_tage):
                continue
            if await self._von_hand_aktiv(w.alt) or not (r.ordner / f"{w.neu}.zim").is_file():
                continue
            if ablage.entfernen(w.alt):
                logger.info("Vorige Fassung %s entfernt (%s Tage nach dem Umschalten)", w.alt, r.vorige_tage)
            await self._liste(r, austragen=f"{w.alt}.zim")
            await self._bestand.wechsel_beenden(w, "entfernt")

    # ----- Stand und Verzeichnis --------------------------------------------------------------------------------------

    async def gesehen(self) -> None:
        """Die Neuigkeiten des letzten Durchgangs sind angesehen."""
        letzter = await self._bestand.letzter_durchgang()
        if letzter:
            await self._bestand.merken("gesehen_bis", str(letzter[0]))

    async def stand(self) -> Laderstand:
        r = self._regeln()
        grund = self._grund(r)
        letzter = await self._bestand.letzter_durchgang()
        abos: list[Abo] = []
        platz = None
        if not grund:
            ablage = Ablage(r.ordner)
            abos = await self._abos(r, ablage)
            frei, gesamt = ablage.platz()
            buecher, laden = ablage.belegt()
            platz = Platz(ordner=str(r.ordner), frei=frei, gesamt=gesamt, reserve=r.reserve, buecher=buecher,
                          im_laden=laden, hoechstens=r.hoechstens)
        gesehen = int(await self._bestand.merker("gesehen_bis") or 0)
        neu = 0
        if letzter and letzter[0] > gesehen:
            neu = letzter[1].neue_buecher + letzter[1].neue_fassungen
        return Laderstand(
            bereit=not grund, grund=grund, letzter_durchgang=letzter[1] if letzter else None,
            naechster_durchgang=self._naechste(letzter[1], r).isoformat(timespec="minutes") if letzter else "",
            neu_ungesehen=neu, abos=abos, platz=platz,
            regeln=Regelanzeige(sprachen=sorted(r.sprachen), durchsicht=r.durchsicht, neue_fassung=r.neue_fassung,
                                laden_wann=r.laden_wann, vorige_tage=r.vorige_tage))

    async def _abos(self, r: Regeln, ablage: Ablage) -> list[Abo]:
        aktive, wartende, ladende = ablage.aktive(), ablage.wartende(), await self._ladende()
        wechsel = {w.stamm: w for w in await self._bestand.offene_wechsel()}
        aus = []
        for stamm, seit in sorted((await self._bestand.abos()).items()):
            z = await self._bestand.neueste(stamm)
            lokal, wartend = aktive.get(stamm), wartende.get(stamm)
            zustand = zustand_aus(z, lokal, wartend, stamm in ladende)
            hinweis = ""
            if zustand == "neuer_da" and z:
                hinweis = "nur gemeldet (Einstellung)" if r.neue_fassung == "melden" else self._platz_fehlt(r, ablage, z.groesse)
            rueckfall = None
            if (w := wechsel.get(stamm)) and (r.ordner / f"{w.alt}.zim").is_file():
                ab = datetime.fromisoformat(w.am) + timedelta(days=r.vorige_tage)
                rueckfall = Rueckfall(kennung=w.alt, entfernt_ab=ab.astimezone(ZONE).date().isoformat())
            aus.append(Abo(stamm=stamm, titel=(z.titel if z else "") or stamm, seit=seit,
                           lokal_stand=lokal.stand if lokal else "", neuester_stand=z.stand if z else "",
                           neueste_groesse=z.groesse if z else 0, zustand=zustand,
                           wartet=wartend.kennung if zustand == "wartet_auf_umschalten" and wartend else "",
                           rueckfall=rueckfall, hinweis=hinweis))
        return aus

    async def verzeichnis(self, *, suche: str = "", bereich: str = "", nur_neu: bool = False, nur_abonniert: bool = False,
                          grenze: int = 50, versatz: int = 0) -> Verzeichnisseite:
        """Die Bücher des Verzeichnisses in den gewählten Sprachen, je Buch mit seinen Ausgaben, seitenweise."""
        r = self._regeln()
        zeilen = await self._bestand.buecher(set(r.sprachen))
        letzter = await self._bestand.letzter_durchgang()
        nr = letzter[0] if letzter and not letzter[1].erstaufnahme else 0
        abos = await self._bestand.abos()
        ablage = Ablage(r.ordner)
        aktive, wartende = (ablage.aktive(), ablage.wartende()) if ablage.ordner.is_dir() else ({}, {})
        ladende = await self._ladende()
        gruppen: dict[str, list[Buchzeile]] = {}
        for z in zeilen:
            gruppen.setdefault(basis_und_ausgabe(z.stamm)[0], []).append(z)
        buecher = []
        for basis, teile in gruppen.items():
            teile.sort(key=lambda z: AUSGABEN.index(a) if (a := basis_und_ausgabe(z.stamm)[1]) in AUSGABEN else -1)
            erste = next((z for z in teile if z.titel), teile[0])
            varianten = [Variante(
                stamm=z.stamm, ausgabe=basis_und_ausgabe(z.stamm)[1], stand=z.stand, groesse=z.groesse,
                neu="buch" if nr and z.zuerst == nr else "fassung" if nr and z.stand_zuerst == nr else "",
                abonniert=z.stamm in abos, lokal_stand=aktive[z.stamm].stand if z.stamm in aktive else "",
                zustand=zustand_aus(z, aktive.get(z.stamm), wartende.get(z.stamm), z.stamm in ladende)) for z in teile]
            buecher.append(Verzeichnisbuch(basis=basis, ordner=erste.ordner, sprache=erste.sprache,
                                           titel=erste.titel or basis, beschreibung=erste.beschreibung,
                                           eintraege=max(z.eintraege for z in teile), varianten=varianten))
        bereiche = sorted({b.ordner for b in buecher})
        frage = suche.strip().lower()
        passend = [b for b in buecher
                   if (not frage or frage in f"{b.titel} {b.basis} {b.beschreibung}".lower())
                   and (not bereich or b.ordner == bereich)
                   and (not nur_neu or any(v.neu for v in b.varianten))
                   and (not nur_abonniert or any(v.abonniert for v in b.varianten))]
        passend.sort(key=lambda b: (not any(v.neu for v in b.varianten), b.titel.lower(), b.basis))
        grenze = max(1, min(grenze, 200))
        return Verzeichnisseite(eintraege=passend[versatz:versatz + grenze], gesamt=len(passend), bereiche=bereiche)
