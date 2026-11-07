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

from ..modell.buecherlader import (Abo, Durchgang, Katalogfilter, Ladefortschritt, Laderstand, NeueQuelle, Platz,
                                   QuellAenderung, Quellstand, Quellvorschlag, Regeln as Regelanzeige, Rueckfall, Variante,
                                   Verzeichnisbuch, Verzeichnisseite, Zustand)
from ..zeitfenster import ZONE, nachts
from .ablage import Ablage, Lokal
from .bestand import Bestand, Buchzeile, Wechsel, jetzt
from .bibliotheksliste import Bibliotheksliste
from .katalog import ladedatei_aus
from .quellen import Ergebnis, Quelle, quelle_aus, rechnername, vereinigen
from .verzeichnis import AUSGABEN, basis_und_ausgabe, ordner_aus, zerlegen

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
    pruefsummen: str
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


class BezugFehlt(Exception):
    """Eine Bezugsquelle liefert die Datei gerade nicht; das Laden versucht die nächste (WIKI-62)."""


def gb(n: int) -> str:
    """Bytes für Menschen: ab 1 GB in GB mit einer Stelle, darunter in MB (deutsches Komma, Punkt für Tausender)."""
    text = f"{n / GB:,.1f} GB" if n >= GB else f"{max(1, round(n / 1024**2)):,} MB"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


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
                 uhr: Callable[[], datetime] = lambda: datetime.now(timezone.utc), zeitplan: bool = True,
                 in_gebrauch: Callable[[], Awaitable[set[str] | None]] | None = None) -> None:
        """`von_hand_aktiv(kennung)`: hat der Nutzer diese Fassung von Hand aktiv gesetzt (Archiv der Quellen)? Dann
        bleibt sie über die Frist hinaus. `zeitplan`: ohne ihn (Tests) läuft `takt` nur, wenn man ihn ruft.
        `in_gebrauch()`: Dateinamen, die andere Dienste noch lesen (der Fundus, WIKI-58); None heißt unbekannt (er
        antwortet nicht), dann wird nichts gelöscht."""
        self._bestand, self._auftraege, self._regeln = Bestand(db), auftraege, regeln
        self._von_hand_aktiv, self._transport, self._uhr, self._mit_zeitplan = von_hand_aktiv, transport, uhr, zeitplan
        self._in_gebrauch = in_gebrauch
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
        """Was der Zeitplan tut: vorige Fassungen nach der Frist entfernen, Abos nachholen, die zuletzt nicht laden
        konnten (etwa weil der Platz fehlte oder die Regel nur melden hieß), und eine fällige Durchsicht anstoßen."""
        r = self._regeln()
        if await self._grund(r):
            return
        await self._aufraeumen(r)
        await self._abos_pruefen("Zeitplan")
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

    async def _grund(self, r: Regeln) -> str:
        if not Ablage(r.ordner).beschreibbar():
            return f"In den Ordner der Bücher ({r.ordner}) lässt sich nicht schreiben"
        if not await self._bestand.quellen(nur_an=True):
            return "Keine Quelle eingeschaltet (Bibliothek, Fassungen und Laden, Quellen)"
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
        if grund := await self._grund(r):
            raise LaderFehler(grund)
        offen = await self._offene(DURCHSEHEN)
        return offen[0] if offen else await self._auftraege.einreihen(DURCHSEHEN, von=von)

    async def _durchsehen(self, k: Kontext) -> Durchgang:
        """Alle eingeschalteten Quellen durchsehen und ihre Vereinigungsmenge eintragen (WIKI-62). Eine Quelle, die nicht
        antwortet, fehlt in diesem Durchgang mit Hinweis; antwortet keine, ist der Durchgang gescheitert."""
        r = self._regeln()
        begonnen, hinweise = jetzt(), []
        quellen = [quelle_aus(q.nr, q.art, q.name, q.adresse) for q in await self._bestand.quellen(nur_an=True)]
        ergebnisse: list[tuple[Quelle, Ergebnis]] = []
        async with self._client() as c:
            for i, quelle in enumerate(quellen):
                async def melden(schritt: str, i: int = i) -> None:
                    await k.pruefen()
                    await k.fortschritt(i / len(quellen), f"Quelle {i + 1} von {len(quellen)}: {schritt}")
                try:
                    ergebnis = await quelle.durchsehen(c, r.sprachen, melden)
                except (httpx.HTTPError, ET.ParseError, ValueError) as f:
                    hinweise.append(f"{quelle.name}: {f}")
                    await self._bestand.quelle_gelaufen(quelle.nr, 0, str(f))
                    continue
                hinweise += ergebnis.hinweise
                ergebnisse.append((quelle, ergebnis))
                await self._bestand.quelle_gelaufen(quelle.nr, len(ergebnis.funde), "; ".join(ergebnis.hinweise))
        if not ergebnisse:
            raise AuftragFehler("Keine Quelle hat geantwortet: " + "; ".join(hinweise))
        await k.fortschritt(None, "Vereinigen, eintragen und vergleichen")
        vereint = vereinigen(ergebnisse)
        durchgang = await self._bestand.durchgang_eintragen(
            Durchgang(begonnen=begonnen, beendet=jetzt(), quellen=len(ergebnisse),
                      ordner=len({v.ordner for v in vereint}), dateien=len(vereint), buecher=len({v.stamm for v in vereint}),
                      neue_buecher=0, neue_fassungen=0, erstaufnahme=False, hinweise=hinweise), vereint)
        await self._abos_pruefen("Durchsicht")
        return durchgang

    # ----- Abos -------------------------------------------------------------------------------------------------------

    async def _abos_pruefen(self, von: str, nur: str = "") -> None:
        """Für jedes Abo, das fehlt oder eine neuere Fassung hat, einen Auftrag zum Laden (einmal je Buch)."""
        r = self._regeln()
        if await self._grund(r):
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
        if grund := await self._grund(r):
            raise AuftragFehler(grund)
        ablage = Ablage(r.ordner)
        ablage.laden.mkdir(exist_ok=True)
        teil = ablage.teil(e.datei)
        name = zerlegen(e.datei)
        bezuege = await self._bestand.bezuege(e.stamm, name.stand) if name else []
        async with self._client() as c:
            # Prüfsumme und Spiegel der Ladedatei, solange einer fehlt (auch ein Auftrag aus der Zeit vor den Quellen,
            # der nur die Prüfsumme kennt und noch keine Bezugsquellen hat)
            if not k.zwischenstand.get("soll") or "spiegel" not in k.zwischenstand:
                soll, spiegel = await self._pruefsumme(c, r, e, next((b.ladedatei for b in bezuege if b.ladedatei), ""))
                await k.merken(soll=k.zwischenstand.get("soll") or soll, spiegel=spiegel)
            adressen = list(dict.fromkeys([b.adresse for b in bezuege] + k.zwischenstand.get("spiegel", [])))
            if not adressen:
                raise AuftragFehler(f"Keine Quelle nennt {e.datei} (mehr); Jetzt durchsehen oder eine Quelle einschalten")
            fehler = []
            for adresse in adressen:
                try:
                    await self._herunterladen(k, c, r, ablage, adresse, teil)
                    break
                except BezugFehlt as f:
                    fehler.append(f"{rechnername(adresse)}: {f}")
                    logger.info("%s von %s: %s; nächste Bezugsquelle", e.datei, rechnername(adresse), f)
            else:
                raise AuftragFehler(f"Keine Bezugsquelle lieferte {e.datei}; Wiederholen setzt fort. " + "; ".join(fehler))
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
    async def _pruefsumme(c: httpx.AsyncClient, r: Regeln, e: LadeEingabe, ladedatei: str) -> tuple[str, list[str]]:
        """Prüfsumme und weitere Spiegel aus der Ladedatei (meta4) der Quelle, sonst der Quelle der Prüfsummen; geht
        beides nicht, die Prüfsumme allein (.sha256). Ohne Prüfsumme lädt nichts."""
        for adresse in dict.fromkeys(filter(None, [ladedatei, urljoin(r.pruefsummen, f"{e.ordner}/{e.datei}.meta4")])):
            try:
                antwort = await c.get(adresse)
                antwort.raise_for_status()
                l = ladedatei_aus(antwort.content)
            except (httpx.HTTPError, ET.ParseError):
                continue
            if l.sha256:
                return l.sha256, [a for a, _ in l.spiegel]
        adresse = urljoin(r.pruefsummen, f"{e.ordner}/{e.datei}.sha256")
        try:
            antwort = await c.get(adresse)
            antwort.raise_for_status()
            soll = antwort.text.split()[0].lower() if antwort.text.strip() else ""
        except httpx.HTTPError as f:
            raise AuftragFehler(f"Keine Prüfsumme für {e.datei} ({f}); ohne Prüfsumme lädt der Bücherlader nicht") from f
        if not _SHA256.match(soll):
            raise AuftragFehler(f"Die Prüfsumme für {e.datei} ist unlesbar; ohne Prüfsumme lädt der Bücherlader nicht")
        return soll, []

    async def _herunterladen(self, k: Kontext, c: httpx.AsyncClient, r: Regeln, ablage: Ablage, adresse: str,
                             teil: Path) -> None:
        """Fortsetzbar in die angefangene Datei (auch von einer anderen Bezugsquelle: gleiche Bytes, die Prüfsumme
        entscheidet am Ende); hält an, sobald der freie Platz unter die Reserve fiele. `BezugFehlt`: diese Quelle
        liefert gerade nicht, die nächste ist dran."""
        try:
            kopf = await c.head(adresse)
            kopf.raise_for_status()
            gesamt = int(kopf.headers["content-length"])
        except (httpx.HTTPError, KeyError, ValueError) as f:
            raise BezugFehlt(f"antwortet nicht ({f})") from f
        schon = teil.stat().st_size if teil.exists() else 0
        if schon > gesamt:
            teil.unlink()
            schon = 0
        if schon == gesamt:
            return
        if fehlt := self._platz_fehlt(r, ablage, gesamt - schon):
            raise AuftragFehler(fehlt)
        quelle = rechnername(adresse)
        await k.fortschritt(schon / gesamt, f"{gb(schon)} von {gb(gesamt)} · von {quelle}", phase="laden")
        beginn, ab, seit_pruefung = time.monotonic(), schon, 0
        try:
            async with c.stream("GET", adresse, headers={"Range": f"bytes={schon}-"} if schon else {}) as antwort:
                if antwort.status_code == 200:
                    schon = ab = 0                                 # der Server setzt nicht fort: von vorn
                elif antwort.status_code != 206:
                    raise BezugFehlt(f"antwortet mit {antwort.status_code}")
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
                                                             f"noch {dauer((gesamt - schon) / max(tempo, 1))} · von {quelle}")
        except httpx.HTTPError as f:
            raise BezugFehlt(f"unterbrochen bei {gb(schon)} von {gb(gesamt)} ({f})") from f
        if schon != gesamt:
            raise BezugFehlt(f"unterbrochen bei {gb(schon)} von {gb(gesamt)}")

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

    async def _gebraucht(self) -> set[str] | None:
        return await self._in_gebrauch() if self._in_gebrauch else set()

    async def _bleibt(self, w: Wechsel, r: Regeln, gebraucht: set[str] | None) -> str:
        """Warum eine vorige Fassung über die Frist hinaus bleibt; leer: sie darf weg."""
        if await self._von_hand_aktiv(w.alt):
            return "von Hand wieder aktiv gesetzt"
        if not (r.ordner / f"{w.neu}.zim").is_file():
            return "die neue Fassung fehlt"
        if gebraucht is None:
            return "die Bedeutungssuche (Fundus) antwortet nicht; gelöscht wird erst, wenn sie die Datei freigibt"
        if f"{w.alt}.zim" in gebraucht:
            return "die Bedeutungssuche (Fundus) liest sie noch ein"
        return ""

    async def _aufraeumen(self, r: Regeln) -> None:
        ablage = Ablage(r.ordner)
        faellig = [w for w in await self._bestand.offene_wechsel()
                   if self._uhr() >= datetime.fromisoformat(w.am) + timedelta(days=r.vorige_tage)]
        gebraucht = await self._gebraucht() if faellig else set()
        for w in faellig:
            if await self._bleibt(w, r, gebraucht):
                continue
            if ablage.entfernen(w.alt):
                logger.info("Vorige Fassung %s entfernt (%s Tage nach dem Umschalten)", w.alt, r.vorige_tage)
            await self._liste(r, austragen=f"{w.alt}.zim")
            await self._bestand.wechsel_beenden(w, "entfernt")

    # ----- Stand und Verzeichnis --------------------------------------------------------------------------------------

    # ----- Quellen verwalten (WIKI-62) ---------------------------------------------------------------------------------

    async def quellen(self) -> list[Quellstand]:
        return await self._bestand.quellen()

    async def quelle_anlegen(self, neu: NeueQuelle) -> list[Quellstand]:
        """Eine Quelle hinzufügen; ein Verzeichnis wird dabei gelesen, damit eine falsche Adresse gleich auffällt."""
        adresse = neu.adresse.strip()
        if neu.art == "verzeichnis":
            adresse = adresse if adresse.endswith("/") else adresse + "/"
            async with self._client() as c:
                try:
                    antwort = await c.get(adresse)
                    antwort.raise_for_status()
                except httpx.HTTPError as f:
                    raise LaderFehler(f"Die Adresse antwortet nicht: {f}") from f
            if not ordner_aus(antwort.text):
                raise LaderFehler("Unter der Adresse steht kein Verzeichnis mit Bereichen (Ordner je Bereich, darin ZIM-Dateien)")
        try:
            await self._bestand.quelle_anlegen(neu.art, neu.name.strip() or rechnername(adresse), adresse)
        except ValueError as f:
            raise LaderFehler(str(f)) from f
        return await self._bestand.quellen()

    async def quelle_aendern(self, nr: int, aenderung: QuellAenderung) -> list[Quellstand]:
        await self._bestand.quelle_aendern(nr, aenderung.model_dump(exclude_none=True))
        return await self._bestand.quellen()

    async def quelle_entfernen(self, nr: int) -> list[Quellstand]:
        await self._bestand.quelle_entfernen(nr)
        return await self._bestand.quellen()

    async def vorschlaege(self) -> list[Quellvorschlag]:
        """Spiegel aus der Ladedatei eines bekannten Buchs, die noch keine Quelle sind (Adresse bis zum Bereich)."""
        r = self._regeln()
        z = next(iter(await self._bestand.buecher(set(r.sprachen))), None)
        if z is None:
            return []
        async with self._client() as c:
            try:
                antwort = await c.get(urljoin(r.pruefsummen, f"{z.ordner}/{z.datei}.meta4"))
                antwort.raise_for_status()
                spiegel = ladedatei_aus(antwort.content).spiegel
            except (httpx.HTTPError, ET.ParseError):
                return []
        bekannt = {q.adresse for q in await self._bestand.quellen()}
        aus = []
        for adresse, land in spiegel:
            basis = adresse.removesuffix(f"{z.ordner}/{z.datei}")
            if basis != adresse and basis not in bekannt and all(v.adresse != basis for v in aus):
                aus.append(Quellvorschlag(name=rechnername(basis), adresse=basis, land=land))
        return aus

    async def gesehen(self) -> None:
        """Die Neuigkeiten des letzten Durchgangs sind angesehen."""
        letzter = await self._bestand.letzter_durchgang()
        if letzter:
            await self._bestand.merken("gesehen_bis", str(letzter[0]))

    async def stand(self) -> Laderstand:
        r = self._regeln()
        grund = await self._grund(r)
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
            neu_ungesehen=neu, abos=abos, platz=platz, quellen=await self._bestand.quellen(),
            regeln=Regelanzeige(sprachen=sorted(r.sprachen), durchsicht=r.durchsicht, neue_fassung=r.neue_fassung,
                                laden_wann=r.laden_wann, vorige_tage=r.vorige_tage))

    async def _abos(self, r: Regeln, ablage: Ablage) -> list[Abo]:
        aktive, wartende, ladende = ablage.aktive(), ablage.wartende(), await self._ladende()
        wechsel = {w.stamm: w for w in await self._bestand.offene_wechsel()}
        faellig = [w for w in wechsel.values() if self._uhr() >= datetime.fromisoformat(w.am) + timedelta(days=r.vorige_tage)]
        gebraucht = await self._gebraucht() if faellig else set()      # nur fragen, wenn eine Frist um ist
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
                bleibt = await self._bleibt(w, r, gebraucht) if w in faellig else ""
                rueckfall = Rueckfall(kennung=w.alt, entfernt_ab=ab.astimezone(ZONE).date().isoformat(), bleibt=bleibt)
            aus.append(Abo(stamm=stamm, titel=(z.titel if z else "") or stamm, seit=seit,
                           lokal_stand=lokal.stand if lokal else "", neuester_stand=z.stand if z else "",
                           neueste_groesse=z.groesse if z else 0, zustand=zustand,
                           wartet=wartend.kennung if zustand == "wartet_auf_umschalten" and wartend else "",
                           rueckfall=rueckfall, hinweis=hinweis,
                           laden=self._ladefortschritt(ladende.get(stamm))))
        return aus

    @staticmethod
    def _ladefortschritt(a: Auftrag | None) -> Ladefortschritt | None:
        if a is None or a.zustand not in ("wartet", "laeuft"):
            return None
        return Ladefortschritt(auftrag=a.id, zustand=a.zustand, fortschritt=a.fortschritt, schritt=a.schritt,
                               zurueckgestellt=a.zurueckgestellt)

    async def verzeichnis(self, f: Katalogfilter | None = None, *, grenze: int = 50, versatz: int = 0) -> Verzeichnisseite:
        """Die Bücher des Verzeichnisses in den gewählten Sprachen, je Buch mit seinen Ausgaben, gefiltert und
        seitenweise (WIKI-61)."""
        f = f or Katalogfilter()
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
                zustand=zustand_aus(z, aktive.get(z.stamm), wartende.get(z.stamm), z.stamm in ladende),
                quellen=z.bezuege) for z in teile]
            buecher.append(Verzeichnisbuch(basis=basis, ordner=erste.ordner, sprache=erste.sprache,
                                           titel=erste.titel or basis, beschreibung=erste.beschreibung,
                                           eintraege=max(z.eintraege for z in teile), angaben=erste.angaben_lesen(),
                                           varianten=varianten))
        bereiche = sorted({b.ordner for b in buecher})
        sprachen = sorted({b.sprache for b in buecher})
        kategorien = sorted({b.angaben.kategorie for b in buecher if b.angaben.kategorie})
        passend = [g for b in buecher if (g := self._gefiltert(b, f))]
        passend.sort(key=self._ordnung(f))
        grenze = max(1, min(grenze, 200))
        return Verzeichnisseite(eintraege=passend[versatz:versatz + grenze], gesamt=len(passend), bereiche=bereiche,
                                sprachen=sprachen, kategorien=kategorien)

    @staticmethod
    def _gefiltert(b: Verzeichnisbuch, f: Katalogfilter) -> Verzeichnisbuch | None:
        """Das Buch mit den Ausgaben, die zum Filter passen; keine passt: None."""
        frage = f.suche.strip().lower()
        text = f"{b.titel} {b.basis} {b.beschreibung} {b.angaben.autor} {' '.join(b.angaben.schlagworte)}".lower()
        if (frage and frage not in text) or (f.bereich and b.ordner != f.bereich) or (f.sprache and b.sprache != f.sprache) \
                or (f.kategorie and b.angaben.kategorie != f.kategorie) or (f.ausgabe == "einzeln" and len(b.varianten) > 1):
            return None
        bibliothek = {"da": lambda v: bool(v.lokal_stand), "nicht_da": lambda v: not v.lokal_stand and v.zustand != "laedt",
                      "neuer_da": lambda v: v.zustand in ("neuer_da", "wartet_auf_umschalten")}.get(f.bibliothek)
        varianten = [v for v in b.varianten
                     if (f.ausgabe in ("", "einzeln") or v.ausgabe == f.ausgabe) and (not f.groesse_bis or v.groesse <= f.groesse_bis)
                     and (not f.nur_neu or v.neu) and (not f.nur_abonniert or v.abonniert) and (bibliothek is None or bibliothek(v))]
        return b.model_copy(update={"varianten": varianten}) if varianten else None

    @staticmethod
    def _ordnung(f: Katalogfilter) -> Callable[[Verzeichnisbuch], tuple]:
        """Neues vorn, dann nach der gewählten Sortierung (bei Größe zählt die größte bzw. kleinste Ausgabe)."""
        def schluessel(b: Verzeichnisbuch) -> tuple:
            vorn = not any(v.neu for v in b.varianten)
            if f.sortierung == "neueste":
                return vorn, -int(max(v.stand for v in b.varianten).replace("-", "")), b.titel.lower()   # JJJJMM
            if f.sortierung == "groesste":
                return vorn, -max(v.groesse for v in b.varianten), b.titel.lower()
            if f.sortierung == "kleinste":
                return vorn, min(v.groesse for v in b.varianten), b.titel.lower()
            return vorn, b.titel.lower(), b.basis
        return schluessel
