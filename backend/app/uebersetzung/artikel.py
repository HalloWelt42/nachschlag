"""Artikel übersetzen (WIKI-8): Artikel aus Büchern in anderer Sprache auf Deutsch, über die Leitstelle (gerechnet wird
auf dem Mac), immer als Übersetzung gekennzeichnet. Ein Auftrag je Artikel: er zerlegt den Artikel in Textläufe
(zerlegen.py), schickt sie in Teilen ans Modell, setzt nur geprüfte Übersetzungen ein und legt das Ergebnis ab, für alle
Konten gleich. Was die Prüfung nicht besteht, bleibt im Original und trägt seine Sprache. Ein Auftrag läuft für sich
(höchstens einer zugleich), damit er nicht hinter den langen Aufträgen der eigenen Indizes wartet."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Literal

from lxml import html as lhtml
from pydantic import BaseModel, Field

from appkern.app.begleiter import Begleiter
from appkern.auftraege import Art, AuftragFehler, Auftraege, Kontext
from appkern.auftraege.modelle import Phase
from appkern.datenbank import Datenbank
from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, antwortform, gerade, json_lesen

from ..artikel import Artikelleser
from ..bausteine.html import als_html, ueberschriften
from ..bibliothek import Bibliothek
from ..modell.artikel import Abschnitt, Artikel, Steckbrief
from ..modell.buch import Buch
from .anweisungen import anweisung, html_sprache, sprache_in_worten
from .zerlegen import Abgelehnt, Lauf, einsetzen, laeufe, pruefen

logger = logging.getLogger("nachschlag.uebersetzung")

ART = "artikeluebersetzung"
#: Fassung der Übersetzung: steigt sie (bessere Anweisungen, andere Prüfung), gelten ältere Übersetzungen als fehlend
FASSUNG = 1
ZIEL = "deu"
#: so viel Text geht je Anfrage ans Modell (Zeichen der Vorlagen), höchstens so viele Stücke
TEIL_ZEICHEN = 2500
TEIL_STUECKE = 30
PHASEN = (Phase(schluessel="lesen", titel="Artikel lesen", symbol="book-open"),
          Phase(schluessel="uebersetzen", titel="Übersetzen", symbol="language"),
          Phase(schluessel="ablegen", titel="Prüfen und ablegen", symbol="check"))

STUFEN = ["""
CREATE TABLE artikeluebersetzungen (
    buch      TEXT NOT NULL,
    pfad      TEXT NOT NULL,
    fassung   INTEGER NOT NULL,
    daten     TEXT NOT NULL,
    wann      TEXT NOT NULL,
    PRIMARY KEY (buch, pfad)
)
"""]


class ArtikelEingabe(BaseModel):
    buch: str = Field(min_length=1, max_length=300)
    pfad: str = Field(min_length=1, max_length=2000)


class ArtikelUebersetzung(BaseModel):
    """Was die Oberfläche statt des Originals zeigt; Anker, Bilder und Verweise sind die des Originals."""
    titel: str
    html: str
    abschnitte: list[Abschnitt] = Field(default_factory=list)
    steckbrief: Steckbrief | None = None
    aus: str = Field(description="Sprache des Originals in Worten, für 'aus dem ...' (Englischen)")
    modell: str = ""
    wann: str = Field(description="Zeitpunkt der Übersetzung (ISO)")
    stuecke: int = Field(0, description="so viele Textstücke hat der Artikel")
    im_original: int = Field(0, description="so viele bestanden die Prüfung nicht und stehen im Original")


class Artikelstand(BaseModel):
    """Stand der Übersetzung eines Artikels. Ohne Leitstelle ist das ein Zustand mit Grund, kein Fehler."""
    zustand: Literal["fertig", "laeuft", "fehlt", "fehler", "nicht_moeglich", "nicht_noetig"]
    auftrag: str = Field("", description="Kennung des Auftrags (Seite Aufträge)")
    anteil: float | None = None
    schritt: str = ""
    grund: str = ""
    uebersetzung: ArtikelUebersetzung | None = None


def braucht_uebersetzung(buch: Buch) -> bool:
    """Bücher in genau einer anderen Sprache als Deutsch (mehrsprachige und unbekannte bleiben im Original)."""
    return bool(buch.sprache) and "," not in buch.sprache and buch.sprache not in (ZIEL, "mul")


def _teile(stuecke: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    teile, teil, zeichen = [], [], 0
    for nr, vorlage in stuecke:
        if teil and (zeichen + len(vorlage) > TEIL_ZEICHEN or len(teil) >= TEIL_STUECKE):
            teile.append(teil)
            teil, zeichen = [], 0
        teil.append((nr, vorlage))
        zeichen += len(vorlage)
    return teile + ([teil] if teil else [])


def _form(anzahl: int) -> dict[str, Any]:
    return antwortform("artikeluebersetzung", {
        "type": "object", "additionalProperties": False, "required": ["stuecke"],
        "properties": {"stuecke": {"type": "array", "items": {"type": "string"}, "minItems": anzahl, "maxItems": anzahl}}})


class Artikeluebersetzer(Begleiter):
    def __init__(self, db: Datenbank, auftraege: Auftraege, bibliothek: Bibliothek, leser: Artikelleser,
                 leitstelle: Callable[[], Leitstelle | None], modell: Callable[[], str]) -> None:
        self._db, self._auftraege, self._bib, self._leser = db, auftraege, bibliothek, leser
        self._leitstelle, self._modell = leitstelle, modell
        auftraege.anmelden(Art(name=ART, titel="Artikel übersetzen", arbeit=self._arbeit, eingabe=ArtikelEingabe, phasen=PHASEN,
                               fortsetzbar=True, nach_neustart="fortsetzen", hoechstens=1))

    async def starten(self) -> None:
        await self._db.einrichten("nachschlag_artikeluebersetzung", STUFEN)

    # ----- Stand und Anstoßen ----------------------------------------------------------------------------------------

    async def abgelegt(self, buch: str, pfad: str) -> ArtikelUebersetzung | None:
        z = await self._db.zeile("SELECT daten FROM artikeluebersetzungen WHERE buch = ? AND pfad = ? AND fassung >= ?",
                                 (buch, pfad, FASSUNG))
        return ArtikelUebersetzung.model_validate_json(z["daten"]) if z else None

    async def stand(self, buch: str, pfad: str) -> Artikelstand:
        """Abgelegt, in Arbeit, gescheitert oder fehlend; Bücher auf Deutsch (oder mehrsprachig) brauchen keine."""
        if not braucht_uebersetzung(await self._bib.buch(buch)):
            return Artikelstand(zustand="nicht_noetig")
        if fertig := await self.abgelegt(buch, pfad):
            return Artikelstand(zustand="fertig", uebersetzung=fertig)
        offen = await self._offener_auftrag(buch, pfad)
        if offen is not None:
            if offen.zustand in ("wartet", "laeuft"):
                return Artikelstand(zustand="laeuft", auftrag=offen.id, anteil=offen.fortschritt, schritt=offen.schritt or
                                    ("Wartet auf die Übersetzung eines anderen Artikels" if offen.zustand == "wartet" else ""))
            if offen.zustand in ("fehler", "unterbrochen"):
                return Artikelstand(zustand="fehler", auftrag=offen.id, grund=offen.fehler or "Übersetzung abgebrochen")
        if self._leitstelle() is None:
            return Artikelstand(zustand="nicht_moeglich", grund="Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        return Artikelstand(zustand="fehlt")

    async def anstossen(self, buch: str, pfad: str, von: str) -> Artikelstand:
        """Einen Auftrag einreihen, wenn weder eine Übersetzung noch ein offener Auftrag da ist; ein gescheiterter wird
        wiederholt (mit dem, was schon übersetzt war)."""
        stand = await self.stand(buch, pfad)
        if stand.zustand == "fehler":
            await self._auftraege.wiederholen(stand.auftrag, von=von)
            return await self.stand(buch, pfad)
        if stand.zustand != "fehlt":
            return stand
        b = await self._bib.buch(buch)
        artikel = await self._leser.lesen(buch, pfad)
        await self._auftraege.einreihen(ART, ArtikelEingabe(buch=buch, pfad=artikel.pfad),
                                        titel=f"Übersetzen: {artikel.titel} ({b.titel})", stapel=self._stapel(buch, artikel.pfad),
                                        von=von)
        return await self.stand(buch, artikel.pfad)

    @staticmethod
    def _stapel(buch: str, pfad: str) -> str:
        return f"{buch}/{pfad}"

    async def _offener_auftrag(self, buch: str, pfad: str):
        """Der jüngste Auftrag des Artikels, wenn er nicht fertig ist (fertig heißt: abgelegt)."""
        seite = await self._auftraege.liste(art=ART, stapel=self._stapel(buch, pfad), grenze=1)
        if seite.eintraege and seite.eintraege[0].zustand not in ("fertig", "abgebrochen"):
            return seite.eintraege[0]
        return None

    # ----- Der Auftrag -----------------------------------------------------------------------------------------------

    async def _arbeit(self, k: Kontext) -> dict[str, Any]:
        leitstelle = self._leitstelle()
        if leitstelle is None:
            raise AuftragFehler("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        await k.fortschritt(0.0, "Artikel lesen", phase="lesen")
        buch = await self._bib.buch(k.eingabe.buch)
        artikel = await self._leser.lesen(k.eingabe.buch, k.eingabe.pfad)
        teile = _Zerlegt(artikel)
        fertig: dict[str, str] = dict(k.zwischenstand.get("stuecke") or {})
        modell = str(k.zwischenstand.get("modell") or "")
        offen = [(nr, l.vorlage) for nr, l in enumerate(teile.laeufe) if str(nr) not in fertig]
        portionen = _teile(offen)
        for i, portion in enumerate(portionen):
            await k.pruefen()
            await k.fortschritt(len(fertig) / max(1, len(teile.laeufe)), f"Teil {i + 1} von {len(portionen)}", phase="uebersetzen")
            uebersetzt, modell = await self._uebersetzen(leitstelle, buch, artikel, teile, portion, modell)
            fertig.update({str(nr): text for nr, text in uebersetzt.items()})
            await k.merken(stuecke=fertig, modell=modell)
        await k.fortschritt(1.0, "Prüfen und ablegen", phase="ablegen")
        ergebnis = teile.zusammensetzen(fertig, buch.sprache, modell)
        await self._db.ausfuehren(
            "INSERT INTO artikeluebersetzungen (buch, pfad, fassung, daten, wann) VALUES (?,?,?,?,?) "
            "ON CONFLICT(buch, pfad) DO UPDATE SET fassung = excluded.fassung, daten = excluded.daten, wann = excluded.wann",
            (buch.kennung, artikel.pfad, FASSUNG, ergebnis.model_dump_json(), ergebnis.wann))
        return {"stuecke": ergebnis.stuecke, "im_original": ergebnis.im_original}

    async def _uebersetzen(self, leitstelle: Leitstelle, buch: Buch, artikel: Artikel, teile: _Zerlegt,
                           portion: list[tuple[int, str]], modell: str) -> tuple[dict[int, str], str]:
        """Eine Portion übersetzen. Passt die Antwort nicht (Anzahl, unlesbar), wird halbiert, bis einzelne Stücke
        übrig sind; ein einzelnes Stück, das nicht durchgeht, bleibt im Original (fehlt im Ergebnis)."""
        try:
            antwort = await leitstelle.chat(
                [Nachricht.system(anweisung(buch.art, buch.sprache, artikel.titel, len(portion))),
                 Nachricht.nutzer(json.dumps({"stuecke": [v for _, v in portion]}, ensure_ascii=False))],
                modell=self._modell() or None, titel="Artikel übersetzen", prioritaet="normal",
                response_format=_form(len(portion)), temperature=0)
            stuecke = json_lesen(antwort.text).get("stuecke")
            if not isinstance(stuecke, list) or len(stuecke) != len(portion):
                raise ValueError("Anzahl der Stücke passt nicht")
            modell = antwort.modell or modell
        except LeitstellenFehler as f:
            raise AuftragFehler(f"Übersetzung gerade nicht möglich: {f}") from f
        except (ValueError, AttributeError) as f:
            if len(portion) == 1:
                logger.info("Stück %s von %s bleibt im Original: %s", portion[0][0], artikel.pfad, f)
                return {}, modell
            mitte = len(portion) // 2
            vorn, modell = await self._uebersetzen(leitstelle, buch, artikel, teile, portion[:mitte], modell)
            hinten, modell = await self._uebersetzen(leitstelle, buch, artikel, teile, portion[mitte:], modell)
            return vorn | hinten, modell
        ergebnis, nochmal = {}, []
        for (nr, vorlage), text in zip(portion, stuecke):
            text = gerade(str(text))
            try:
                pruefen(teile.laeufe[nr], text)
            except Abgelehnt as f:
                logger.info("Stück %s von %s abgelehnt: %s", nr, artikel.pfad, f)
                nochmal.append((nr, vorlage))
                continue
            ergebnis[nr] = text
        if len(portion) > 1:                 # Abgelehntes einzeln noch einmal: allein gelingt es dem Modell eher
            for stueck in nochmal:
                einzeln, modell = await self._uebersetzen(leitstelle, buch, artikel, teile, [stueck], modell)
                ergebnis |= einzeln
        return ergebnis, modell


class _Zerlegt:
    """Ein Artikel als Bäume (Titel, Text, Steckbrief) und seine Textläufe in fester Reihenfolge. Dieselbe Fassung
    des Artikels ergibt dieselben Läufe; darauf baut das Fortsetzen (Nummern im Zwischenstand)."""

    def __init__(self, artikel: Artikel) -> None:
        self.artikel = artikel
        self.titel = lhtml.fragment_fromstring("<h1></h1>")
        self.titel.text = artikel.titel
        self.text = lhtml.fragment_fromstring(artikel.html or "<div></div>", create_parent="div")
        self.steckbrief_titel = lhtml.fragment_fromstring("<h1></h1>")
        self.steckbrief = None
        if artikel.steckbrief:
            self.steckbrief_titel.text = artikel.steckbrief.titel
            self.steckbrief = lhtml.fragment_fromstring(artikel.steckbrief.html or "<div></div>", create_parent="div")
        code_titel = artikel.titelart == "code"
        self.laeufe: list[Lauf] = [
            *([] if code_titel else laeufe(self.titel)),
            *laeufe(self.text),
            *([] if self.steckbrief is None or (artikel.steckbrief and artikel.steckbrief.code) else laeufe(self.steckbrief_titel)),
            *([] if self.steckbrief is None else laeufe(self.steckbrief)),
        ]

    def zusammensetzen(self, stuecke: dict[str, str], sprache: str, modell: str) -> ArtikelUebersetzung:
        """Geprüfte Übersetzungen einsetzen; was fehlt oder nicht durchgeht, bleibt im Original und trägt dessen
        Sprache (lang), damit Vorlesen und Silbentrennung sie kennen und die Oberfläche es zeigen kann."""
        aus, lang = sprache_in_worten(sprache), html_sprache(sprache)
        im_original = 0
        for nr, lauf in enumerate(self.laeufe):
            text = stuecke.get(str(nr))
            try:
                if text is None:
                    raise Abgelehnt("nicht übersetzt")
                einsetzen(lauf, text)
            except Abgelehnt:
                im_original += 1
                if lang:
                    lauf.eltern.set("lang", lang)
        a = self.artikel
        html = "".join(als_html(k) for k in self.text) if a.html else ""
        html = (self.text.text or "") + html
        steckbrief = None
        if a.steckbrief and self.steckbrief is not None:
            steckbrief = Steckbrief(titel=self.steckbrief_titel.text_content() or a.steckbrief.titel,
                                    html=(self.steckbrief.text or "") + "".join(als_html(k) for k in self.steckbrief),
                                    code=a.steckbrief.code)
        return ArtikelUebersetzung(titel=self.titel.text_content() or a.titel, html=html,
                                   abschnitte=ueberschriften(self.text), steckbrief=steckbrief, aus=aus, modell=modell,
                                   wann=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                   stuecke=len(self.laeufe), im_original=im_original)

