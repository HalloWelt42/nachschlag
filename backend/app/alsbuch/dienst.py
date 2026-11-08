"""Als Buch (WIKI-45): ein Thema wird ein Buch als EPUB und PDF, in der Form, die eine Vorlage bestimmt. Der Dienst
verbindet die Schichten: Plan aus Thema und Bestellung, Quelle je Artikel (`quelle.py`), Umformung über die Leitstelle
(`umformung.py`, nur in Aufträgen, mit Zwischenspeicher), Prüfung (`pruefung.py`), Darstellung und Satz (`darstellung.py`,
`epub.py`, `pdf.py`) und Ablage (Kellerwolke oder Datenordner, `ablage.py`).

Zwei Arten von Aufträgen: das Probekapitel (ein Artikel, sein Anfang, gleich) und der Bau eines Buchs (jetzt oder
nachts im Fenster der Einstellungen). Gleiche Anfragen ans Modell liefern das gespeicherte Ergebnis: ein Bau setzt nach
einem Abbruch dort fort, wo er war, und ein Nachbau nach Änderungen am Thema formt nur Neues um. Nach jedem Bau misst
Nachschlag das Tempo des Modells neu (Zeichen je Sekunde), Grundlage jeder Schätzung."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field

from appkern.app.begleiter import Begleiter
from appkern.auftraege import Art, AuftragFehler, Auftraege, Herkunft, Kontext
from appkern.auftraege.modelle import Auftrag
from appkern.datenbank import Datenbank
from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, Prioritaet, json_lesen

from ..artikel import Artikelleser
from ..bausteine.html import online_adresse
from ..bibliothek import Bibliothek, BuchFehlt, EintragFehlt
from ..eigenindex.schema import sortierschluessel
from ..kategorien.wikis import wiki
from ..modell.alsbuch import (
    Absatz, Baustand, Baustufe, Bestellung, Bild, Buchartikel, Buchformat, Buchinhalt, Buchkapitel, Buchwahl, Eigenbuch,
    Fremdartikel, Glossareintrag, Kapitelangabe, Kapitelwahl, Leseansicht, Probe, Probewunsch, Pruefung, Quellabsatz,
    Quellangabe, Randnotiz, Regal, Satzhinweis, Schaetzung, Veraltet, Vorlage,
)
from ..modell.artikel import Artikel
from ..modell.buch import Buch
from ..modell.meins import Notiz
from ..modell.themen import Thema, Themeneintrag
from ..themen import Themen
from ..uebersetzung.anweisungen import html_sprache
from ..uebersetzung.artikel import Artikeluebersetzer, braucht_uebersetzung
from ..zeitfenster import Nachtfenster
from . import quelle as quellen
from .ablage import AblageFehler, Buchablage
from .bilder import Bilddatei, Bildquelle, fuer_jedes_lesegeraet
from .darstellung import alle_bilder, epub_seiten, lesen_html, pdf_dokument, stil
from .dauer import HAUSMESSUNG_ZEICHEN_JE_S, ZEICHEN_JE_SEITE, probe_sekunden, schaetzen
from .epub import BILDARTEN, Epubangaben, Epubbild, epub_bauen
from .pdf import PdfFehler, pdf_bauen, verfuegbar
from .pruefung import glossar_im_text, kapitel_pruefen, pruefen, zusammen
from .speicher import Buchspeicher, Buchsatz
from .umformung import (
    NEU_AUFGABE, NEU_FORM, TEILE_ZEICHEN, UMFORMEN_AUFGABE, UMFORMEN_FORM, artikelteile_aufgabe, artikelteile_form,
    artikelteile_lesen, kapitel_eingabe, kapitelteile_aufgabe, kapitelteile_form, kapitelteile_lesen, neu_eingabe, neu_lesen,
    schluessel, system, umformen_eingabe, umformung_lesen,
)
from .vorlagen import Vorlagen, VorlagenFehler

logger = logging.getLogger("nachschlag.alsbuch")

ART_BAU = "buchbau"
ART_PROBE = "buchprobe"
#: so viele Bilder je Artikel kommen höchstens in den Text (Gestaltung im Text)
BILDER_JE_ARTIKEL = 12
#: so viele Kennzahlen von Artikeln merkt sich der Dienst (Länge, Bilder) für Schätzungen
KENNZAHLEN_HOECHSTENS = 4_000
#: so viel vom ersten Absatz zeigt die Vorschau einer Seite
AUSZUG_ZEICHEN = 240
#: ein Bau mit weniger Rechenzeit misst das Tempo nicht neu (zu wenig, um etwas zu sagen)
MESSEN_AB_S = 20.0
OFFEN = ("wartet", "laeuft")
UNFERTIG = ("fehler", "abgebrochen", "unterbrochen")


class Bauauftrag(BaseModel):
    """Eingabe des Auftrags Buch bauen: die Bestellung und die Vorlage im Stand beim Bestellen."""
    konto: str = Field(description="Konto, dem das Buch gehört")
    bestellung: Bestellung = Field(description="Was ins Buch kommt")
    vorlage: Vorlage = Field(description="Die Vorlage beim Bestellen")


class Probeauftrag(BaseModel):
    """Eingabe des Auftrags Probekapitel."""
    konto: str = Field(description="Konto")
    wunsch: Probewunsch = Field(description="Bestellung, Artikel und was neu geschrieben werden soll")
    vorlage: Vorlage = Field(description="Die Vorlage beim Anstoßen")


@dataclass
class Plankapitel:
    titel: str
    eintraege: list[Themeneintrag]


@dataclass
class Plan:
    thema: Thema
    kapitel: list[Plankapitel]

    @property
    def eintraege(self) -> list[Themeneintrag]:
        return [x for k in self.kapitel for x in k.eintraege]


@dataclass
class Quellstand:
    q: quellen.Quelltext
    artikel: Artikel
    buch: Buch


@dataclass
class Kennzahlen:
    zeichen: int
    erstes_stueck: int
    bilder: int
    steckbrief: bool
    anfang: str


@dataclass
class Messung:
    """Was das Modell in einem Auftrag geschrieben hat und wie lange es brauchte (nur echte Anfragen)."""
    zeichen: int = 0
    sekunden: float = 0.0

    @property
    def tempo(self) -> float:
        return self.zeichen / self.sekunden if self.sekunden else 0.0


@dataclass
class Notizen:
    """Notizen eines Artikels: mit Text (Randnotizen) und ohne (gemerkte Stellen)."""
    mit_text: list[Notiz] = field(default_factory=list)
    markierungen: list[Notiz] = field(default_factory=list)


def lizenz(buch: Buch) -> tuple[str, str]:
    """Urheber und Lizenz des Texts: bei den Wikis von Wikimedia bekannt, sonst wie in der Quelle."""
    if wiki(buch.kennung):
        return "die Autorinnen und Autoren des Artikels (Versionsgeschichte unter der Adresse)", "CC BY-SA 4.0"
    return "wie in der Quelle angegeben", "wie in der Quelle angegeben"


def _jetzt() -> datetime:
    return datetime.now(UTC)


class Buecher(Begleiter):
    def __init__(self, db: Datenbank, auftraege: Auftraege, themen: Themen, bibliothek: Bibliothek, leser: Artikelleser,
                 uebersetzer: Artikeluebersetzer, notizen: Callable[[str], Awaitable[list[Notiz]]],
                 literatur: Callable[[str, Thema], Awaitable[str]], vorlagen: Vorlagen, ablage: Buchablage,
                 bilder: Bildquelle, leitstelle: Callable[[], Leitstelle | None], modell: Callable[[], str],
                 nacht: Nachtfenster) -> None:
        """`notizen(konto)`: alle Notizen eines Kontos; `literatur(konto, thema)`: Literaturliste als Markdown."""
        self._sp = Buchspeicher(db)
        self._auftraege, self._themen, self._bib, self._leser = auftraege, themen, bibliothek, leser
        self._uebersetzer, self._notizen, self._literatur = uebersetzer, notizen, literatur
        self.vorlagen, self.ablage, self._bilder = vorlagen, ablage, bilder
        self._ls, self._modell, self._nacht = leitstelle, modell, nacht
        self._kennzahlen: dict[tuple[str, str, bool], Kennzahlen] = {}
        auftraege.anmelden(
            Art(name=ART_BAU, titel="Buch bauen", arbeit=self._bauen, eingabe=Bauauftrag, fortsetzbar=True,
                nach_neustart="fortsetzen", hoechstens=1, herkunft=lambda e: Herkunft(titel="Zu den Büchern", ziel="buecher"),
                gegenstand=lambda e: f"{e['konto']}:{e['bestellung']['thema']}:{e['vorlage']['kennung']}"),
            Art(name=ART_PROBE, titel="Probekapitel", arbeit=self._probe, eingabe=Probeauftrag, hoechstens=1,
                herkunft=lambda e: Herkunft(titel="Zum Probekapitel", ziel=f"themen/{e['wunsch']['bestellung']['thema']}/buch/probe")))

    async def starten(self) -> None:
        await self._sp.einrichten()

    def zurueckstellen(self, a: Auftrag) -> str:
        """Für heute Nacht Bestelltes wartet auf das Fenster (geweckt vom Nachtwecker)."""
        if a.art == ART_BAU and a.eingabe.get("bestellung", {}).get("wann") == "nachts":
            return self._nacht.warten()
        return ""

    # ----- Plan und Quellen --------------------------------------------------------------------------------------------

    async def _vorlage(self, kennung: str) -> Vorlage:
        try:
            v = await self.vorlagen.holen(kennung)
        except VorlagenFehler as f:
            raise ValueError(f.meldung) from f
        if v is None:
            raise LookupError("Diese Vorlage gibt es nicht")
        return v

    async def _thema(self, konto: str, thema: str) -> Thema:
        t = await self._themen.thema(konto, thema)
        if t is None:
            raise LookupError("Dieses Thema gibt es nicht")
        return t

    @staticmethod
    def kapitelwahl(t: Thema, b: Bestellung) -> list[Kapitelwahl]:
        """Die Wahl der Bestellung; leer: jeder Bereich, die Artikel ohne Bereich nur, wenn das Thema keine Bereiche hat."""
        if b.kapitel:
            return b.kapitel
        return [Kapitelwahl(bereich=x.id) for x in sorted(t.bereiche, key=lambda x: x.platz)] + \
            [Kapitelwahl(bereich="", an=not t.bereiche)]

    async def _plan(self, konto: str, b: Bestellung, v: Vorlage) -> Plan:
        t = await self._thema(konto, b.thema)
        titel = {x.id: x.titel for x in t.bereiche}
        kapitel: list[Plankapitel] = []
        for wahl in self.kapitelwahl(t, b):
            if not wahl.an or (wahl.bereich and wahl.bereich not in titel):
                continue
            eintraege = sorted((x for x in t.eintraege if x.bereich == wahl.bereich and x.buch), key=lambda x: x.platz)
            name = titel.get(wahl.bereich) or (t.titel if not t.bereiche else "Weitere Artikel")
            if eintraege:
                kapitel.append(Plankapitel(name, eintraege))
        if v.aufbau.gliederung == "abc":
            alle = sorted((x for k in kapitel for x in k.eintraege), key=lambda x: sortierschluessel(x.titel))
            je: dict[str, list[Themeneintrag]] = {}
            for x in alle:
                anfang = (sortierschluessel(x.titel)[:1] or "#").upper()
                je.setdefault(anfang if anfang.isalpha() else "0-9", []).append(x)
            kapitel = [Plankapitel(k, xs) for k, xs in je.items()]
        return Plan(t, kapitel)

    async def _quelle(self, x: Themeneintrag, uebersetzung: bool) -> Quellstand:
        buch = await self._bib.buch(x.buch)
        a = await self._leser.lesen(x.buch, x.pfad)
        ue = await self._uebersetzer.abgelegt(x.buch, a.pfad) if uebersetzung and braucht_uebersetzung(buch) else None
        if ue is not None:
            return Quellstand(quellen.lesen(ue.titel, ue.html, "de"), a, buch)
        return Quellstand(quellen.lesen(a.titel, a.html, html_sprache(buch.sprache) or "de"), a, buch)

    async def _kennzahl(self, x: Themeneintrag, uebersetzung: bool) -> Kennzahlen | None:
        schl = (x.buch, x.pfad, uebersetzung)
        if schl not in self._kennzahlen:
            try:
                qs = await self._quelle(x, uebersetzung)
            except (BuchFehlt, EintragFehlt):
                return None
            erstes = quellen.stuecke(qs.q)
            if len(self._kennzahlen) >= KENNZAHLEN_HOECHSTENS:
                self._kennzahlen.clear()
            self._kennzahlen[schl] = Kennzahlen(qs.q.zeichen, sum(len(b.text) for b in erstes[0]) if erstes else 0,
                                                min(len(qs.q.bilder), BILDER_JE_ARTIKEL), qs.artikel.steckbrief is not None,
                                                qs.q.absaetze[0].text[:AUSZUG_ZEICHEN] if qs.q.absaetze else "")
        return self._kennzahlen[schl]

    async def _notizen_je_artikel(self, konto: str) -> dict[tuple[str, str], Notizen]:
        je: dict[tuple[str, str], Notizen] = {}
        for n in await self._notizen(konto):
            ziel = je.setdefault((n.buch_name, n.pfad), Notizen())
            (ziel.mit_text if n.text.strip() else ziel.markierungen if n.zitat.strip() else []).append(n)
        return je

    async def _tempo(self) -> tuple[float, bool]:
        gemessen = await self._sp.tempo(self._modell())
        return (gemessen, True) if gemessen else (HAUSMESSUNG_ZEICHEN_JE_S, False)

    # ----- Seite Als Buch ----------------------------------------------------------------------------------------------

    async def buchwahl(self, konto: str, thema: str) -> Buchwahl:
        t = await self._thema(konto, thema)
        notizen = await self._notizen_je_artikel(konto)
        im_thema = [notizen.get((x.buch_name, x.pfad), Notizen()) for x in t.eintraege]
        bilder = steckbriefe = 0
        fremd: list[Fremdartikel] = []
        auszug: tuple[str, str] = ("", "")
        for x in sorted(t.eintraege, key=lambda x: (next((b.platz for b in t.bereiche if b.id == x.bereich), 10_000), x.platz)):
            if not x.buch:
                continue
            if (k := await self._kennzahl(x, False)) is not None:
                bilder += k.bilder
                steckbriefe += int(k.steckbrief)
                auszug = auszug if auszug[1] else (x.titel, k.anfang)
            buch = await self._bib.buch(x.buch)
            if braucht_uebersetzung(buch):
                fremd.append(Fremdartikel(titel=x.titel, sprache=buch.sprache,
                                          uebersetzt=await self._uebersetzer.abgelegt(x.buch, x.pfad) is not None))
        gruppen = [(b.id, b.titel) for b in sorted(t.bereiche, key=lambda b: b.platz)]
        gruppen.append(("", "Ohne Bereich" if t.bereiche else t.titel))
        kapitel = []
        for kennung, titel in gruppen:
            xs = sorted((x for x in t.eintraege if x.bereich == kennung), key=lambda x: x.platz)
            if xs or kennung:
                kapitel.append(Kapitelangabe(bereich=kennung, titel=titel, artikel=len(xs), lesbar=sum(1 for x in xs if x.buch),
                                             bilder=[x.bild for x in xs if x.bild][:3]))
        return Buchwahl(thema=t.id, titel=t.titel, artikel=len(t.eintraege), kapitel=kapitel,
                        notizen=sum(len(n.mit_text) for n in im_thema), markierungen=sum(len(n.markierungen) for n in im_thema),
                        bilder=bilder, steckbriefe=steckbriefe, fremd=fremd,
                        titelbilder=list(dict.fromkeys(x.bild for x in t.eintraege if x.bild))[:8], auszug_titel=auszug[0],
                        auszug=auszug[1], modell=self._modell(),
                        leitstelle=self._ls() is not None, pdf=verfuegbar(), ablage=await self.ablage.ordner(t.titel),
                        letzte=await self._sp.letzte(konto, thema))

    async def schaetzen(self, konto: str, b: Bestellung) -> Schaetzung:
        v = await self._vorlage(b.vorlage)
        plan = await self._plan(konto, b, v)
        zahlen = [k for x in plan.eintraege if (k := await self._kennzahl(x, b.uebersetzung)) is not None]
        bilder = {"im_text": sum(k.bilder for k in zahlen), "eins_gross": len(zahlen), "ohne": 0}[v.gestaltung.bilder]
        tempo, gemessen = await self._tempo()
        s = schaetzen([k.zeichen for k in zahlen], len(plan.kapitel), bilder, v, b, tempo, gemessen, self._modell())
        jetzt = self._nacht.jetzt()
        if b.wann == "nachts":
            beginn, nacht_ende = self._nacht.naechste()
            ende = beginn + timedelta(seconds=s.sekunden)
            s.beginn, s.ende, s.nacht_reicht = beginn.isoformat(), ende.isoformat(), ende <= nacht_ende
        else:
            s.ende = (jetzt + timedelta(seconds=s.sekunden)).isoformat()
        if plan.eintraege and zahlen:
            s.probe_titel = plan.eintraege[0].titel
            s.probe_sekunden = probe_sekunden(zahlen[0].erstes_stueck, v, b, tempo)
        return s

    # ----- Anstoßen ----------------------------------------------------------------------------------------------------

    async def bestellen(self, konto: str, wer: str, b: Bestellung) -> Auftrag:
        v = await self._vorlage(b.vorlage)
        if v.ki and self._ls() is None:
            raise ValueError("Die Vorlage braucht die KI, aber die Leitstelle ist nicht eingerichtet (Einstellungen, Verbindungen)")
        if b.pdf and not b.epub and (grund := verfuegbar()):
            raise ValueError(grund)
        t = await self._thema(konto, b.thema)
        await self._sp.letzte_merken(konto, b)
        titel = f"{t.titel} als {v.titel}" + (" (heute Nacht)" if b.wann == "nachts" else "")
        return await self._auftraege.einreihen(ART_BAU, Bauauftrag(konto=konto, bestellung=b, vorlage=v), titel=titel, von=wer)

    async def probe_anstossen(self, konto: str, wer: str, w: Probewunsch) -> Auftrag:
        v = await self._vorlage(w.bestellung.vorlage)
        if v.ki and self._ls() is None:
            raise ValueError("Die Vorlage braucht die KI, aber die Leitstelle ist nicht eingerichtet (Einstellungen, Verbindungen)")
        t = await self._thema(konto, w.bestellung.thema)
        return await self._auftraege.einreihen(ART_PROBE, Probeauftrag(konto=konto, wunsch=w, vorlage=v),
                                               titel=f"Probekapitel: {t.titel} als {v.titel}", von=wer)

    async def probe(self, konto: str, thema: str) -> Probe | None:
        return await self._sp.probe(konto, thema)

    # ----- Umformung über die Leitstelle -------------------------------------------------------------------------------

    async def _fragen(self, system_text: str, nutzer: str, form: dict[str, Any], prio: Prioritaet | None,
                      messung: Messung, titel: str) -> dict[str, Any]:
        """Eine Anfrage ans Modell, oder ihr gespeichertes Ergebnis (gleiche Anfrage, gleiches Ergebnis)."""
        modell = self._modell()
        schl = schluessel(modell, system_text, nutzer, json.dumps(form, sort_keys=True))
        if (alt := await self._sp.umformung(schl)) is not None:
            return alt
        ls = self._ls()
        if ls is None:
            raise AuftragFehler("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        beginn = time.monotonic()
        try:
            antwort = await ls.chat([Nachricht.system(system_text), Nachricht.nutzer(nutzer)], modell=modell, titel=titel,
                                    prioritaet=prio, response_format=form, temperature=0.2)
            daten = json_lesen(antwort.text)
        except LeitstellenFehler as f:
            raise AuftragFehler(f"Die Leitstelle antwortet gerade nicht: {f}") from f
        except ValueError as f:
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück") from f
        if not isinstance(daten, dict):
            raise AuftragFehler("Die Antwort des Modells kam unlesbar zurück")
        dauer = time.monotonic() - beginn
        messung.zeichen += len(antwort.text)
        messung.sekunden += dauer
        await self._sp.umformung_merken(schl, daten, len(antwort.text), dauer)
        return daten

    async def _artikel(self, x: Themeneintrag, qs: Quellstand, v: Vorlage, b: Bestellung, notizen: Notizen,
                       prio: Prioritaet | None, messung: Messung, titel: str,
                       nur_erstes: bool = False) -> tuple[Buchartikel, Pruefung, list[quellen.Quellblock]]:
        """Ein Artikel nach der Vorlage: Text (umgeformt oder wie im Buch), Kästen, Bilder, Notizen; geprüft."""
        innen = [t.art for t in v.aufbau.innen]
        q = qs.q
        teile = quellen.stuecke(q)
        if nur_erstes:
            teile = teile[:1]
        benutzt = [blk for s in teile for blk in s]
        absaetze: list[Absatz] = []
        if "umgeformt" in innen:
            aufgabe = system(v, b.fuer_wen, b.laenge, UMFORMEN_AUFGABE)
            for i, stueck in enumerate(teile):
                roh = await self._fragen(aufgabe, umformen_eingabe(q.titel, stueck, i > 0), UMFORMEN_FORM, prio, messung, titel)
                absaetze += umformung_lesen(roh, {blk.nr for blk in stueck if blk.nr})
        elif "originaltext" in innen:
            ende = max((blk.nr for blk in benutzt), default=0) if nur_erstes else None
            absaetze = _wie_im_buch(q, ende, v.gestaltung.bilder == "im_text" and b.bilder)
        blick = "blick" in innen
        kaesten = [t for t in v.aufbau.innen if t.art == "kasten"]
        blick_kasten, eigene = None, []
        if blick or kaesten:
            grundlage = _gekuerzt(benutzt if nur_erstes else [blk for blk in q.bloecke if blk.nr or blk.art == "ueberschrift"],
                                  TEILE_ZEICHEN)
            roh = await self._fragen(system(v, b.fuer_wen, b.laenge, artikelteile_aufgabe(blick, kaesten)),
                                     umformen_eingabe(q.titel, grundlage, False), artikelteile_form(blick, len(kaesten)),
                                     prio, messung, titel)
            blick_kasten, eigene = artikelteile_lesen(roh, blick, kaesten, {blk.nr for blk in grundlage if blk.nr})
        umgeformt = "umgeformt" in innen
        if umgeformt and b.bilder and v.gestaltung.bilder == "im_text":
            _bilder_einordnen(absaetze, q, max((blk.nr for blk in benutzt), default=0))
        randnotizen: list[Randnotiz] = []
        if "notizen" in innen and b.notizen:
            randnotizen = _notizen_einordnen(absaetze, notizen.mit_text, q, umgeformt)
        if b.markierungen:
            _markierungen_einordnen(absaetze, notizen.markierungen, q, umgeformt)
        leitbild = None
        if b.bilder and v.gestaltung.bilder == "eins_gross":
            adresse = x.bild or qs.artikel.bild or (q.bilder[0].adresse if q.bilder else "")
            unterschrift = next((bl.unterschrift for bl in q.bilder if bl.adresse == adresse), "")
            leitbild = Bild(adresse=adresse, unterschrift=unterschrift) if adresse else None
        urheber, lz = lizenz(qs.buch)
        artikel = Buchartikel(
            eintrag=x.id, titel=q.titel, buch=x.buch, pfad=x.pfad, sprache=q.sprache, leitbild=leitbild,
            quelle=Quellangabe(buch=qs.buch.titel, fassung=qs.buch.stand, adresse=online_adresse(qs.buch, x.pfad),
                               urheber=urheber, lizenz=lz),
            steckbrief=quellen.steckbrief(qs.artikel.steckbrief.html) if b.steckbriefe and qs.artikel.steckbrief else "",
            blick=blick_kasten, kaesten=eigene, absaetze=absaetze, notizen=randnotizen, zeichen_original=q.zeichen)
        artikel, pruefung = pruefen(q, artikel)
        return artikel, pruefung, benutzt

    async def _kapitelteile(self, v: Vorlage, b: Bestellung, k: Buchkapitel, prio: Prioritaet | None, messung: Messung,
                            titel: str) -> tuple[Buchkapitel, list[Glossareintrag], list[Satzhinweis]]:
        teile = {t.art for t in [*v.aufbau.innen, *v.aufbau.vorn, *v.aufbau.hinten]}
        einleitung, fragen, glossar = "kapiteleinleitung" in teile, b.fragen if "fragen" in teile else 0, "glossar" in teile
        if not (einleitung or fragen or glossar) or not k.artikel:
            return k, [], []
        texte = [(a.titel, a.absaetze or [Absatz(text=p.text) for p in (a.blick.punkte if a.blick else [])]) for a in k.artikel]
        roh = await self._fragen(system(v, b.fuer_wen, b.laenge, kapitelteile_aufgabe(k.titel, einleitung, fragen, glossar)),
                                 kapitel_eingabe(k.titel, texte), kapitelteile_form(einleitung, fragen, glossar), prio, messung, titel)
        e, f, g = kapitelteile_lesen(roh, len(k.artikel), fragen)
        neu = k.model_copy(update={"einleitung": e, "fragen": f})
        text = " ".join(x.text or x.html for _, xs in texte for x in xs)
        return neu, glossar_im_text(g, text), kapitel_pruefen(neu, text)

    # ----- Probekapitel ------------------------------------------------------------------------------------------------

    async def _probe(self, k: Kontext) -> dict[str, Any]:
        e: Probeauftrag = k.eingabe
        w, v, b = e.wunsch, e.vorlage, e.wunsch.bestellung
        try:
            plan = await self._plan(e.konto, b, v)
        except LookupError as f:
            raise AuftragFehler(str(f)) from f
        x = next((y for y in plan.eintraege if y.id == w.eintrag), None) if w.eintrag else (plan.eintraege or [None])[0]
        if x is None:
            raise AuftragFehler("Im Buch steht kein Artikel aus einer vorhandenen Quelle" if not w.eintrag
                                else "Dieser Artikel steht nicht im Buch")
        await k.fortschritt(None, f"Liest {x.titel}")
        try:
            qs = await self._quelle(x, b.uebersetzung)
        except (BuchFehlt, EintragFehlt) as f:
            raise AuftragFehler(f"Der Artikel ließ sich nicht lesen: {f}") from f
        messung = Messung()
        beginn = time.monotonic()
        if w.neu:
            alt = await self._sp.probe(e.konto, b.thema)
            if alt is None or alt.eintrag != x.id:
                raise AuftragFehler("Es gibt kein Probekapitel zu diesem Artikel mehr")
            await k.fortschritt(None, "Die KI schreibt neu")
            probe = await self._neu_schreiben(alt, qs, v, b, [n.absatz for n in w.neu], messung)
        else:
            await k.fortschritt(None, "Die KI formt um")
            notizen = (await self._notizen_je_artikel(e.konto)).get((x.buch_name, x.pfad), Notizen())
            artikel, pruefung, benutzt = await self._artikel(x, qs, v, b, notizen, None, messung, "Probekapitel", nur_erstes=True)
            kapitel = Buchkapitel(titel=next((c.titel for c in plan.kapitel if x in c.eintraege), plan.thema.titel), artikel=[artikel])
            kapitel, _, hinweise = await self._kapitelteile(v, b, kapitel, None, messung, "Probekapitel")
            pruefung.hinweise += hinweise
            probe = Probe(thema=b.thema, eintrag=x.id, vorlage=v.kennung, vorlage_titel=v.titel, fuer_wen=b.fuer_wen,
                          laenge=b.laenge, quelle=qs.buch.titel, zeichen_original=qs.q.zeichen,
                          original=_original(benutzt), artikel=artikel, kapitel=kapitel, pruefung=pruefung, sekunden=0,
                          seiten=1, wann=_jetzt().isoformat(timespec="seconds"))
        zeichen = sum(len(a.text or a.html) for a in probe.artikel.absaetze)
        probe = probe.model_copy(update={"sekunden": round(time.monotonic() - beginn, 1),
                                         "seiten": max(1, round(zeichen / ZEICHEN_JE_SEITE["a5"]))})
        await self._sp.probe_merken(e.konto, probe)
        return {"thema": b.thema, "eintrag": x.id, "hinweise": len(probe.pruefung.hinweise)}

    async def _neu_schreiben(self, p: Probe, qs: Quellstand, v: Vorlage, b: Bestellung, stellen: list[int],
                             messung: Messung) -> Probe:
        """Absätze des Probekapitels neu schreiben lassen, nur aus ihren Belegen, und neu prüfen. Das neue Ergebnis gilt
        auch für den Bau: der Zwischenspeicher des Stücks bekommt den neuen Absatz."""
        nach_nr = {blk.nr: blk for blk in qs.q.absaetze}
        absaetze = list(p.artikel.absaetze)
        for i in sorted(set(stellen)):
            if not (0 <= i < len(absaetze)) or absaetze[i].html:
                continue
            alt = absaetze[i]
            quellen_bl = [nach_nr[n] for n in alt.belege if n in nach_nr] or list(nach_nr.values())[:6]
            roh = await self._fragen(system(v, b.fuer_wen, b.laenge, NEU_AUFGABE), neu_eingabe(alt, quellen_bl), NEU_FORM,
                                     None, messung, "Probekapitel")
            try:
                absaetze[i] = neu_lesen(roh, alt, set(nach_nr))
            except ValueError as f:
                raise AuftragFehler(str(f)) from f
        await self._stueck_ersetzen(qs.q, v, b, absaetze)
        artikel, pruefung = pruefen(qs.q, p.artikel.model_copy(update={"absaetze": absaetze}))
        return p.model_copy(update={"artikel": artikel, "pruefung": pruefung})

    async def _stueck_ersetzen(self, q: quellen.Quelltext, v: Vorlage, b: Bestellung, absaetze: list[Absatz]) -> None:
        """Das erste Stück im Zwischenspeicher mit den neu geschriebenen Absätzen (der Bau nimmt sie dann)."""
        teile = quellen.stuecke(q)
        if not teile or not any(t.art == "umgeformt" for t in v.aufbau.innen):
            return
        schl = schluessel(self._modell(), system(v, b.fuer_wen, b.laenge, UMFORMEN_AUFGABE),
                          umformen_eingabe(q.titel, teile[0], False), json.dumps(UMFORMEN_FORM, sort_keys=True))
        roh = {"absaetze": [{"ueberschrift": a.ueberschrift, "text": a.text, "belege": a.belege} for a in absaetze]}
        await self._sp.umformung_merken(schl, roh, 0, 0.0)

    # ----- Bau eines Buchs ---------------------------------------------------------------------------------------------

    async def _bauen(self, k: Kontext) -> dict[str, Any]:
        e: Bauauftrag = k.eingabe
        b, v = e.bestellung, e.vorlage
        if v.ki and self._ls() is None:
            raise AuftragFehler("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        try:
            plan = await self._plan(e.konto, b, v)
        except LookupError as f:
            raise AuftragFehler(str(f)) from f
        if not plan.eintraege:
            raise AuftragFehler("Im Buch steht kein Artikel aus einer vorhandenen Quelle")
        stand = Baustand(auftrag=k.auftrag_id, zustand="laeuft", titel=f"{plan.thema.titel} als {v.titel}",
                         beschreibung=_beschreibung(b, plan, v, self._modell()), thema=b.thema, vorlage_titel=v.titel,
                         titelbild=b.titelbild or next((x.bild for x in plan.eintraege if x.bild), ""),
                         begonnen=_jetzt().isoformat(timespec="seconds"),
                         stufen=[Baustufe(titel=f"{i} {c.titel}" if v.aufbau.gliederung == "kapitel" else c.titel, zustand="offen",
                                          text=f"0 von {len(c.eintraege)}") for i, c in enumerate(plan.kapitel, 1)])
        kapitelteile = any(t.art in ("kapiteleinleitung", "fragen", "glossar") for t in [*v.aufbau.innen, *v.aufbau.hinten, *v.aufbau.vorn])
        if kapitelteile:
            stand.stufen.append(Baustufe(titel="Glossar und Fragen", zustand="offen"))
        stand.stufen.append(Baustufe(titel=f"Satz {' und '.join(f for f, an in (('EPUB', b.epub), ('PDF', b.pdf)) if an)}",
                                     zustand="offen"))
        await self._sp.baustand_merken(e.konto, stand)
        await k.fortschritt(0, "Liest die Artikel")

        quellen_je: dict[str, Quellstand] = {}
        for x in plan.eintraege:
            await k.pruefen()
            try:
                quellen_je[x.id] = await self._quelle(x, b.uebersetzung)
            except (BuchFehlt, EintragFehlt):
                logger.info("Buch %s: %s ließ sich nicht lesen, bleibt draußen", plan.thema.titel, x.titel)
        gesamt = sum(qs.q.zeichen for qs in quellen_je.values()) or 1
        notizen = await self._notizen_je_artikel(e.konto)
        messung, erledigt, pruefungen = Messung(), 0, []
        kapitel: list[Buchkapitel] = []
        tempo_vorher, _ = await self._tempo()

        for ki, c in enumerate(plan.kapitel):
            buchkapitel = Buchkapitel(titel=c.titel)
            stand.stufen[ki].zustand = "jetzt"
            for ai, x in enumerate(c.eintraege):
                await k.pruefen()
                qs = quellen_je.get(x.id)
                if qs is None:
                    continue
                stand.stufen[ki].text = x.titel
                stand.stufen[ki].anteil = ai / len(c.eintraege)
                await self._melden(k, e.konto, stand, erledigt / gesamt, f"{c.titel}: {x.titel}", messung, gesamt - erledigt,
                                   tempo_vorher, b, v)
                artikel, pruefung, _ = await self._artikel(x, qs, v, b, notizen.get((x.buch_name, x.pfad), Notizen()),
                                                           "hintergrund", messung, "Buch bauen")
                buchkapitel.artikel.append(artikel)
                pruefungen.append(pruefung)
                erledigt += qs.q.zeichen
                stand.hinweise = sum(len(p.hinweise) for p in pruefungen)
            stand.stufen[ki] = stand.stufen[ki].model_copy(update={
                "zustand": "fertig", "anteil": 1.0, "text": f"{len(buchkapitel.artikel)} von {len(c.eintraege)} Artikeln"})
            if buchkapitel.artikel:
                kapitel.append(buchkapitel)

        glossar: dict[str, Glossareintrag] = {}
        if kapitelteile:
            stufe = len(plan.kapitel)
            stand.stufen[stufe].zustand = "jetzt"
            for ki, c in enumerate(kapitel):
                await k.pruefen()
                stand.stufen[stufe].anteil = ki / len(kapitel)
                await self._melden(k, e.konto, stand, 0.95, f"Glossar und Fragen: {c.titel}", messung, 0, tempo_vorher, b, v)
                kapitel[ki], eintraege, hinweise = await self._kapitelteile(v, b, c, "hintergrund", messung, "Buch bauen")
                pruefungen.append(Pruefung(zahlen=0, zahlen_gefunden=0, absaetze=0, belegt=0, hinweise=hinweise))
                for g in eintraege:
                    glossar.setdefault(g.begriff.casefold(), g)
            stand.stufen[stufe] = stand.stufen[stufe].model_copy(update={"zustand": "fertig", "anteil": 1.0})

        stand.stufen[-1].zustand = "jetzt"
        await self._melden(k, e.konto, stand, 0.97, "Satz", messung, 0, tempo_vorher, b, v)
        literatur = await self._literatur(e.konto, plan.thema) if any(t.art == "literatur" for t in [*v.aufbau.vorn, *v.aufbau.hinten]) else ""
        inhalt = Buchinhalt(
            titel=plan.thema.titel, untertitel=v.untertitel, beschreibung=plan.thema.beschreibung, vorlage=v,
            titelbild=Bild(adresse=stand.titelbild) if stand.titelbild and any(t.art == "titelseite" for t in v.aufbau.vorn) else None,
            kapitel=kapitel, glossar=sorted(glossar.values(), key=lambda g: sortierschluessel(g.begriff)),
            literatur=[z for z in literatur.splitlines() if z.startswith(("## ", "- ", "  - "))], erstellt=date.today().isoformat())
        await k.pruefen()
        dateien, seiten = await self._setzen(inhalt, b, e.konto)
        alt = await self._sp.buch_zu(e.konto, b.thema, v.kennung)
        formate = []
        for fmt, (daten, art, titel_fmt) in dateien.items():
            try:
                pfad = await self.ablage.ablegen(plan.thema.titel, self.ablage.dateiname(plan.thema.titel, v.titel, fmt), daten, art)
            except AblageFehler as f:
                raise AuftragFehler(f.meldung) from f
            formate.append(Buchformat(format=fmt, titel=titel_fmt, pfad=pfad, groesse=len(daten)))
        hinweise = zusammen(pruefungen).hinweise
        satz = Buchsatz(id=alt.id if alt else str(uuid.uuid4()), konto=e.konto, thema=b.thema, vorlage=v.kennung,
                        titel=plan.thema.titel, vorlage_titel=v.titel, bestellung=b,
                        eintraege=[x.id for c in plan.kapitel for x in c.eintraege if x.id in quellen_je],
                        artikel=sum(len(c.artikel) for c in kapitel), seiten=seiten,
                        zeichen=sum(qs.q.zeichen for qs in quellen_je.values()), formate=formate, titelbild=stand.titelbild,
                        hinweise=hinweise, gebaut=_jetzt().isoformat(timespec="seconds"), inhalt=inhalt)
        await self._sp.buch_merken(satz)
        if messung.sekunden >= MESSEN_AB_S:
            await self._sp.tempo_merken(self._modell(), round(messung.tempo, 1))
        await self._sp.bau_vergessen(k.auftrag_id)
        return {"buch": satz.id, "seiten": seiten, "hinweise": len(hinweise), "formate": [f.pfad for f in formate],
                "tempo": round(messung.tempo, 1)}

    async def _melden(self, k: Kontext, konto: str, stand: Baustand, anteil: float, schritt: str, messung: Messung,
                      rest: int, tempo_vorher: float, b: Bestellung, v: Vorlage) -> None:
        tempo = messung.tempo or tempo_vorher
        faktor = {"original": 1.0, "haelfte": 0.5, "wichtigste": 0.25}[b.laenge] if v.ki else 0.0
        stand.anteil = round(anteil, 3)
        stand.tempo = round(messung.tempo, 1)
        stand.fertig_gegen = (_jetzt() + timedelta(seconds=rest * faktor / tempo + 30)).isoformat(timespec="seconds")
        await self._sp.baustand_merken(konto, stand)
        await k.fortschritt(anteil, schritt)

    async def _setzen(self, inhalt: Buchinhalt, b: Bestellung, konto: str) -> tuple[dict[str, tuple[bytes, str, str]], int]:
        """EPUB und PDF aus dem Inhalt: Bilder holen (Titel- und Leitbilder groß, wenn der Bildholer sie hat), Seiten
        darstellen, packen und setzen. Ergebnis: Format -> (Daten, Medienart, Beschriftung) und die Seitenzahl."""
        gross = {inhalt.titelbild.adresse} if inhalt.titelbild else set()
        gross |= {a.leitbild.adresse for k in inhalt.kapitel for a in k.artikel if a.leitbild}
        namen: dict[str, str] = {}
        dateien: dict[str, Bilddatei] = {}
        for i, bild in enumerate(alle_bilder(inhalt)):
            d = await self._bilder.holen(bild.adresse, gross=bild.adresse in gross)
            if d is None:
                continue
            d = await asyncio.to_thread(fuer_jedes_lesegeraet, d)
            name = f"bilder/b{i:03d}.{BILDARTEN[d.art]}"
            namen[bild.adresse], dateien[name] = name, d
        _bildangaben(inhalt, {a: (dateien[n].urheber, dateien[n].lizenz) for a, n in namen.items()})
        bildname = lambda bild: namen.get(bild.adresse)  # noqa: E731
        aus: dict[str, tuple[bytes, str, str]] = {}
        seiten = 0
        if b.epub:
            seitenliste, nav, im_buch = epub_seiten(inhalt, bildname)
            kennung = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, f'nachschlag:{konto}:{b.thema}:{inhalt.vorlage.kennung}')}"
            titelbild = namen.get(inhalt.titelbild.adresse, "") if inhalt.titelbild else ""
            epub = epub_bauen(Epubangaben(titel=inhalt.titel, untertitel=inhalt.untertitel, kennung=kennung,
                                          beschreibung=inhalt.beschreibung, titelbild=titelbild),
                              seitenliste, nav, stil(inhalt.vorlage.gestaltung, "epub"),
                              [Epubbild(n, d.art, d.daten) for n, d in dateien.items()], im_buch)
            aus["epub"] = (epub, "application/epub+zip", "EPUB")
        if b.pdf:
            html = pdf_dokument(inhalt, bildname, b.seiten)
            try:
                pdf, seiten = await asyncio.to_thread(pdf_bauen, html, {n: (d.daten, d.art) for n, d in dateien.items()},
                                                      b.seiten == "a4_zwei")
            except PdfFehler as f:
                if not b.epub:
                    raise AuftragFehler(f.meldung) from f
                logger.warning("Buch %s ohne PDF: %s", inhalt.titel, f.meldung)
            else:
                aus["pdf"] = (pdf, "application/pdf", {"a5": "PDF A5", "a4": "PDF A4", "a4_zwei": "PDF A4, zwei Seiten je Blatt"}[b.seiten])
        if not seiten:
            zeichen = sum(len(x.text or x.html) for k in inhalt.kapitel for a in k.artikel for x in a.absaetze)
            seiten = max(1, round(zeichen / ZEICHEN_JE_SEITE["a5"]) + len(inhalt.kapitel) + 3)
        return aus, seiten

    # ----- Eigene Bücher -----------------------------------------------------------------------------------------------

    async def regal(self, konto: str) -> Regal:
        saetze = await self._sp.buecher(konto)
        gebaut = {(s.thema, s.vorlage): s.gebaut for s in saetze}
        staende = await self._sp.baustaende(konto)
        seite = await self._auftraege.liste(art=ART_BAU, zustand=(*OFFEN, *UNFERTIG), grenze=100)
        laufend: list[Baustand] = []
        gesehen: set[str] = set()
        for a in seite.eintraege:
            eingabe = Bauauftrag.model_validate(a.eingabe)
            gegenstand = f"{eingabe.bestellung.thema}:{eingabe.vorlage.kennung}"
            if eingabe.konto != konto or gegenstand in gesehen or a.uebernommen_von:
                continue
            fertig_danach = (gebaut.get((eingabe.bestellung.thema, eingabe.vorlage.kennung)) or "") > a.erstellt_am.isoformat()
            if a.zustand in UNFERTIG and fertig_danach:
                continue
            gesehen.add(gegenstand)
            laufend.append(_baustand(a, eingabe, staende.get(a.id)))
        fertig = [await self._eigenbuch(s, konto) for s in saetze]
        return Regal(laufend=laufend, fertig=fertig, ablage=await self.ablage.ordner())

    async def _eigenbuch(self, s: Buchsatz, konto: str) -> Eigenbuch:
        return Eigenbuch(id=s.id, thema=s.thema, titel=s.titel, vorlage=s.vorlage, vorlage_titel=s.vorlage_titel,
                         artikel=s.artikel, seiten=s.seiten, gebaut=s.gebaut, titelbild=s.titelbild, formate=s.formate,
                         hinweise=s.hinweise, veraltet=await self._veraltet(s, konto))

    async def _veraltet(self, s: Buchsatz, konto: str) -> Veraltet | None:
        """Neue und herausgenommene Artikel seit dem Bau, mit der Dauer des Nachbaus (nur das Neue wird umgeformt)."""
        t = await self._themen.thema(konto, s.thema)
        if t is None:
            return None
        try:
            v = await self._vorlage(s.vorlage)
            plan = await self._plan(konto, s.bestellung, v)
        except (LookupError, ValueError):                 # Vorlage gelöscht oder gerade nicht lesbar: ohne Hinweis
            return None
        jetzt = {x.id: x for x in plan.eintraege}
        neu = [x for i, x in jetzt.items() if i not in set(s.eintraege)]
        weg = [i for i in s.eintraege if i not in jetzt]
        if not (neu or weg):
            return None
        tempo, gemessen = await self._tempo()
        zahlen = [k for x in neu if (k := await self._kennzahl(x, s.bestellung.uebersetzung)) is not None]
        dauer = schaetzen([k.zeichen for k in zahlen], len(plan.kapitel), 0, v, s.bestellung, tempo, gemessen, self._modell())
        teile = []
        if neu:
            teile.append(f"{len(neu)} {'neuer Artikel' if len(neu) == 1 else 'neue Artikel'}")
        if weg:
            teile.append(f"{len(weg)} Artikel herausgenommen")
        return Veraltet(neu=len(neu), weg=len(weg), text="Thema geändert: " + ", ".join(teile), sekunden=dauer.sekunden)

    async def nachbauen(self, konto: str, wer: str, kennung: str, wann: str) -> Auftrag:
        s = await self._sp.buch(konto, kennung)
        if s is None:
            raise LookupError("Dieses Buch gibt es nicht")
        return await self.bestellen(konto, wer, s.bestellung.model_copy(update={"wann": wann}))

    async def loeschen(self, konto: str, kennung: str) -> bool:
        """Das Buch aus dem Regal; seine Dateien gehen aus der Ablage (in der Kellerwolke: in den Papierkorb)."""
        s = await self._sp.buch(konto, kennung)
        if s is None:
            return False
        for f in s.formate:
            try:
                await self.ablage.loeschen(f.pfad)
            except AblageFehler as fehler:
                logger.warning("Buch %s: Datei nicht in den Papierkorb (%s)", s.titel, fehler.meldung)
        return await self._sp.buch_loeschen(konto, kennung)

    async def leseansicht(self, konto: str, kennung: str) -> Leseansicht:
        s = await self._sp.buch(konto, kennung, mit_inhalt=True)
        if s is None or s.inhalt is None:
            raise LookupError("Dieses Buch gibt es nicht")
        return Leseansicht(titel=s.inhalt.titel, untertitel=s.inhalt.untertitel, html=lesen_html(s.inhalt, lambda b: b.adresse))

    async def datei(self, konto: str, kennung: str, fmt: str) -> tuple[str, str, AsyncIterator[bytes]]:
        """Name, Medienart und Inhalt einer Datei des Buchs aus der Ablage."""
        s = await self._sp.buch(konto, kennung)
        f = next((x for x in s.formate if x.format == fmt), None) if s else None
        if s is None or f is None:
            raise LookupError("Diese Datei gibt es nicht")
        art = "application/epub+zip" if fmt == "epub" else "application/pdf"
        try:
            inhalt = await self.ablage.oeffnen(f.pfad)
        except AblageFehler as fehler:
            raise LookupError(fehler.meldung) from fehler
        return f.pfad.rsplit("/", 1)[-1], art, inhalt


# ----- Hilfen (rein) ---------------------------------------------------------------------------------------------------

def _gekuerzt(bloecke: list[quellen.Quellblock], hoechstens: int) -> list[quellen.Quellblock]:
    aus, laenge = [], 0
    for blk in bloecke:
        if laenge + len(blk.text) > hoechstens and laenge:
            break
        aus.append(blk)
        laenge += len(blk.text)
    return aus


def _original(bloecke: list[quellen.Quellblock]) -> list[Quellabsatz]:
    aus, ueberschrift = [], ""
    for blk in bloecke:
        if blk.art == "ueberschrift":
            ueberschrift = blk.text
        elif blk.nr:
            aus.append(Quellabsatz(nr=blk.nr, text=blk.text, ueberschrift=ueberschrift))
            ueberschrift = ""
    return aus


def _wie_im_buch(q: quellen.Quelltext, bis_nr: int | None, mit_bildern: bool) -> list[Absatz]:
    """Der Text wie im Buch: jeder Block ein Absatz (Überschriften an den nächsten), Bilder an ihrer Stelle."""
    aus: list[Absatz] = []
    ueberschrift, ebene = "", 2
    for blk in q.bloecke:
        if bis_nr is not None and blk.nr and blk.nr > bis_nr:
            break
        if blk.art == "ueberschrift":
            if ueberschrift:
                aus.append(Absatz(text="", ueberschrift=ueberschrift, ebene=ebene))
            ueberschrift, ebene = blk.text, max(2, min(blk.ebene, 4))
            continue
        aus.append(Absatz(text=blk.text, html=blk.html or blk.text, art=blk.art if blk.art != "ueberschrift" else "absatz",
                          liste=blk.liste, geordnet=blk.geordnet, ueberschrift=ueberschrift, ebene=ebene,
                          belege=[blk.nr] if blk.nr else [], bilder=blk.bilder[:BILDER_JE_ARTIKEL] if mit_bildern else []))
        ueberschrift = ""
    return aus


def _stelle_im_ergebnis(absaetze: list[Absatz], nr: int, umgeformt: bool) -> int:
    """Stelle des Absatzes im Buchtext, der den Absatz `nr` des Originals trägt (umgeformt: der erste, der ihn belegt,
    sonst der nächste danach); -1: keiner."""
    if nr <= 0 or not absaetze:
        return -1
    if not umgeformt:
        return next((i for i, a in enumerate(absaetze) if nr in a.belege), -1)
    genau = next((i for i, a in enumerate(absaetze) if nr in a.belege), -1)
    if genau >= 0:
        return genau
    return next((i for i, a in enumerate(absaetze) if a.belege and max(a.belege) >= nr), len(absaetze) - 1)


def _bilder_einordnen(absaetze: list[Absatz], q: quellen.Quelltext, bis_nr: int) -> None:
    """Bilder des Originals (bis zum Absatz `bis_nr`) hinter den umgeformten Absatz, der ihre Stelle belegt; höchstens
    BILDER_JE_ARTIKEL."""
    zuletzt, gesetzt = 0, 0
    for blk in q.bloecke:
        zuletzt = blk.nr or zuletzt
        if zuletzt > bis_nr:
            return
        for bild in blk.bilder:
            stelle = _stelle_im_ergebnis(absaetze, max(zuletzt, 1), True)
            if gesetzt >= BILDER_JE_ARTIKEL:
                return
            if stelle >= 0:
                absaetze[stelle].bilder.append(bild)
                gesetzt += 1


def _notizen_einordnen(absaetze: list[Absatz], notizen: list[Notiz], q: quellen.Quelltext, umgeformt: bool) -> list[Randnotiz]:
    """Notizen an einer Stelle hinter ihren Absatz; die übrigen gelten dem ganzen Artikel."""
    zum_artikel = []
    for n in sorted(notizen, key=lambda n: n.angelegt):
        notiz = Randnotiz(text=n.text.strip(), zitat=" ".join(n.zitat.split()))
        stelle = _stelle_im_ergebnis(absaetze, quellen.stelle_von(q, n.zitat), umgeformt) if n.zitat.strip() else -1
        if stelle >= 0:
            absaetze[stelle].notizen.append(notiz)
        else:
            zum_artikel.append(notiz)
    return zum_artikel


def _markierungen_einordnen(absaetze: list[Absatz], markierungen: list[Notiz], q: quellen.Quelltext, umgeformt: bool) -> None:
    """Gemerkte Stellen: im Text wie im Buch wörtlich hervorgehoben, im umgeformten der Absatz, der sie trägt."""
    for n in markierungen:
        stelle = _stelle_im_ergebnis(absaetze, quellen.stelle_von(q, n.zitat), umgeformt)
        if stelle < 0:
            continue
        if umgeformt:
            absaetze[stelle].hervorgehoben = True
        else:
            absaetze[stelle].markiert.append(" ".join(n.zitat.split()))


def _bildangaben(inhalt: Buchinhalt, angaben: dict[str, tuple[str, str]]) -> None:
    """Urheber und Lizenz der geholten Bilder an jedes Bild des Inhalts (für Quellen und Lizenzen)."""
    reihe = [inhalt.titelbild] if inhalt.titelbild else []
    for k in inhalt.kapitel:
        for a in k.artikel:
            reihe += [a.leitbild] if a.leitbild else []
            reihe += [b for x in a.absaetze for b in x.bilder]
    for b in reihe:
        if b.adresse in angaben:
            b.urheber, b.lizenz = angaben[b.adresse]


def _beschreibung(b: Bestellung, plan: Plan, v: Vorlage, modell: str) -> str:
    formate = " und ".join(x for x, an in (("EPUB", b.epub), ("PDF " + {"a5": "A5", "a4": "A4", "a4_zwei": "A4 (zwei Seiten je Blatt)"}[b.seiten], b.pdf)) if an)
    n = len(plan.eintraege)
    teil = f"{formate}, {n} Artikel in {len(plan.kapitel)} {'Kapiteln' if len(plan.kapitel) != 1 else 'Kapitel'}"
    return f"{teil}, über die Leitstelle mit {modell}." if v.ki else f"{teil}, ohne KI."


def _baustand(a: Auftrag, e: Bauauftrag, gemerkt: Baustand | None) -> Baustand:
    """Stand eines Bauauftrags für das Regal: der gemerkte Stand des Baus mit Zustand und Grund des Auftrags."""
    grund = (a.zurueckgestellt or a.fehler or "") if a.zustand != "laeuft" else ""
    if a.zustand == "abgebrochen":
        grund = "angehalten"
    if gemerkt is not None:
        return gemerkt.model_copy(update={"auftrag": a.id, "zustand": a.zustand, "grund": grund})
    b, v = e.bestellung, e.vorlage
    formate = " und ".join(x for x, an in (("EPUB", b.epub), ("PDF", b.pdf)) if an)
    return Baustand(auftrag=a.id, zustand=a.zustand, grund=grund, titel=a.titel.removesuffix(" (heute Nacht)"),
                    beschreibung=f"{formate}, Vorlage {v.titel}", thema=b.thema, titelbild=b.titelbild, vorlage_titel=v.titel)
