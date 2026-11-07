"""Bücher aus einem Ordner: jede Datei `*.zim` ist ein Buch, Kennung ist der Dateiname ohne Endung. Neue oder entfernte
Dateien erscheinen beim nächsten Blick in den Ordner (ein Lesen des Ordners, kein Wächter). Geöffnete Bücher bleiben
offen, solange die Datei dieselbe ist (Größe und Änderungszeit).

Was ein Buch kann und welcher Art es ist, steht in seinen Angaben (Erzeuger, Schlagworte), nie im Dateinamen. Gelesen
wird nur; libzim liest gleichzeitig aus mehreren Fäden, darum laufen alle Zugriffe in Fäden (`asyncio.to_thread`)."""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from libzim.reader import Archive

from ..modell.buch import Art, Bibliotheksstand, Buch, Faehigkeiten

logger = logging.getLogger("nachschlag.bibliothek")
#: Erzeuger und die Grundstruktur ihrer Bücher; erkannt am Anfang der Angabe Scraper
ERZEUGER: tuple[tuple[str, Art], ...] = (("mwoffliner", "enzyklopaedie"), ("devdocs", "dokumentation"),
                                        ("sotoki", "frage_antwort"), ("warc2zim", "webseite"), ("zimit", "webseite"))
#: Spiegel von Seiten (warc2zim, zimit), deren Inhalt eine bekannte Art ist: die Quelle (Metadatum Source) entscheidet
QUELLEN: tuple[tuple[str, Art], ...] = (("php.net/manual", "dokumentation"),)
#: Arten mit eigenem Lesedesign (wächst mit den Bausteinen)
MIT_LESEDESIGN: set[Art] = {"enzyklopaedie", "dokumentation", "frage_antwort"}
#: Stand am Ende eines Dateinamens (`_2026-10`); davor steht das Buch in seiner Ausgabe
STAND = re.compile(r"_\d{4}-\d{2}$")
UMLEITUNG_HTML = re.compile(rb"""<meta[^>]+http-equiv=["']refresh["'][^>]+URL=['"]?\.?/?([^'">]+)""", re.I)


class BuchFehlt(LookupError):
    pass


class EintragFehlt(LookupError):
    pass


@dataclass(frozen=True)
class Eintrag:
    pfad: str            # nach dem Auflösen von Weiterleitungen
    titel: str
    mime: str
    inhalt: bytes
    anker: str = ""      # Abschnitt, auf den eine Weiterleitung zeigt


@dataclass
class _Offen:
    archiv: Archive
    buch: Buch
    kennzeichen: tuple[int, int]     # Größe und Änderungszeit der Datei


def _angabe(a: Archive, schluessel: str) -> str:
    try:
        return bytes(a.get_metadata(schluessel)).decode("utf-8", "replace").strip()
    except (KeyError, RuntimeError):
        return ""


def art_aus(erzeuger: str, quelle: str = "") -> Art:
    """Art eines Buchs nach seinem Erzeuger; bei Spiegeln von Seiten nach der Quelle, wenn sie bekannt ist."""
    q = quelle.lower()
    gespiegelt = next((art for name, art in QUELLEN if name in q), None)
    if gespiegelt:
        return gespiegelt
    e = erzeuger.lower()
    return next((art for name, art in ERZEUGER if name in e), "sonstiges")


def seiten_aus(a: Archive) -> int:
    """Zahl der Artikel: die Hauptseiten der Datei zählen Weiterleitungen mit (deutsche Enzyklopädie 5,04 Mio.), die
    HTML-Seiten laut Zähler (`Counter`: "text/html=3205144;...") auch Nebenseiten wie Nutzer- und Schlagwortseiten
    einer Frage-Antwort-Seite; der kleinere Wert kommt dem Buch am nächsten (Enzyklopädie 3,2 Mio., vi 25.378)."""
    zaehler = _angabe(a, "Counter")
    seiten = sum(int(n) for art, _, n in (t.rpartition("=") for t in zaehler.split(";"))
                 if art.startswith("text/html") and n.isdigit())
    return min(seiten, a.article_count) if seiten else a.article_count


def buch_aus(kennung: str, a: Archive, groesse: int) -> Buch:
    erzeuger = _angabe(a, "Scraper")
    art = art_aus(erzeuger, _angabe(a, "Source"))
    start = ""
    if a.has_main_entry:
        try:
            start = a.main_entry.get_item().path
        except RuntimeError:
            start = a.main_entry.path
    return Buch(kennung=kennung, name=_angabe(a, "Name") or kennung, titel=_angabe(a, "Title") or kennung,
                beschreibung=_angabe(a, "Description"), sprache=_angabe(a, "Language").split(",")[0],
                stand=_angabe(a, "Date"), erzeuger=erzeuger, art=art, eintraege=a.entry_count,
                artikel=seiten_aus(a), medien=a.media_count, groesse=groesse, startseite=start,
                faehigkeiten=Faehigkeiten(titelindex=a.has_title_index, volltext=a.has_fulltext_index,
                                          bilder=a.media_count > 0, lesedesign=art in MIT_LESEDESIGN))


class Bibliothek:
    def __init__(self, ordner: Callable[[], str]) -> None:
        """`ordner`: liefert den Ordner der Bücher (aus den Einstellungen, darum bei jedem Blick neu gefragt)."""
        self._ordner = ordner
        self._offen: dict[str, _Offen] = {}
        self._fehler: dict[str, str] = {}
        self._sperre = threading.Lock()

    def _dateien(self) -> dict[str, Path]:
        wurzel = Path(self._ordner())
        if not wurzel.is_dir():
            return {}
        return {p.stem: p for p in sorted(wurzel.glob("*.zim")) if p.is_file()}

    def _abgleichen(self) -> None:
        dateien = self._dateien()
        with self._sperre:
            for weg in set(self._offen) - set(dateien):
                del self._offen[weg]
            self._fehler = {k: v for k, v in self._fehler.items() if k in dateien}
            for kennung, pfad in dateien.items():
                st = pfad.stat()
                kennzeichen = (st.st_size, int(st.st_mtime))
                offen = self._offen.get(kennung)
                if offen and offen.kennzeichen == kennzeichen:
                    continue
                try:
                    a = Archive(str(pfad))
                    self._offen[kennung] = _Offen(a, buch_aus(kennung, a, st.st_size), kennzeichen)
                    self._fehler.pop(kennung, None)
                except RuntimeError as f:
                    self._offen.pop(kennung, None)
                    self._fehler[kennung] = f"{pfad.name}: {f}"
                    logger.warning("Quelle lässt sich nicht öffnen: %s", self._fehler[kennung])

    async def stand(self) -> Bibliotheksstand:
        await asyncio.to_thread(self._abgleichen)
        with self._sperre:
            buecher = sorted((o.buch for o in self._offen.values()), key=lambda b: (b.sprache != "deu", b.titel.lower(), b.kennung))
            return Bibliotheksstand(ordner=str(self._ordner()), buecher=buecher, fehler=sorted(self._fehler.values()))

    async def buch(self, kennung: str) -> Buch:
        return (await asyncio.to_thread(self._oeffnen, kennung)).buch

    def archiv(self, kennung: str) -> Archive:
        return self._oeffnen(kennung).archiv

    def geoeffnet(self, kennung: str) -> tuple[Archive, Buch]:
        """Datei und Angaben eines Buchs ohne Warten (für Arbeit in einem eigenen Faden, etwa den Index-Dienst)."""
        offen = self._oeffnen(kennung)
        return offen.archiv, offen.buch

    def _oeffnen(self, kennung: str) -> _Offen:
        with self._sperre:
            offen = self._offen.get(kennung)
        if offen is None:
            self._abgleichen()
            with self._sperre:
                offen = self._offen.get(kennung)
        if offen is None:
            raise BuchFehlt(f"Eine Quelle {kennung} gibt es in der Bibliothek nicht")
        return offen

    def _eintrag(self, kennung: str, pfad: str, tiefe: int = 0, anker: str = "") -> Eintrag:
        """`pfad` ist der echte Pfad im Buch (schon entschlüsselt, wie ihn die Wege der Schnittstelle liefern); ein Name
        darf selbst `%` enthalten (Bilder heißen etwa `..._J%C3%BCchen%2C_...`) und wird nie ein zweites Mal entschlüsselt."""
        a = self.archiv(kennung)
        try:
            e = a.get_entry_by_path(pfad)
        except KeyError:
            raise EintragFehlt(f"{pfad} steht nicht in der Quelle {kennung}") from None
        if e.is_redirect:
            e = e.get_redirect_entry()
        item = e.get_item()
        inhalt = bytes(item.content)
        # Weiterleitung als HTML-Seite mit Sprung (so legt mwoffliner Weiterleitungen auf Abschnitte an)
        if tiefe < 3 and item.mimetype.startswith("text/html") and len(inhalt) < 4096 and (m := UMLEITUNG_HTML.search(inhalt)):
            # der Sprung steht als Adresse im HTML (verschlüsselt): einmal entschlüsseln, Anker abtrennen
            ziel, _, ziel_anker = m.group(1).decode("utf-8", "replace").partition("#")
            basis = e.path.rsplit("/", 1)[0] + "/" if "/" in e.path else ""
            weiter = self._eintrag(kennung, basis + unquote(ziel), tiefe + 1, unquote(ziel_anker))
            return weiter
        return Eintrag(e.path, e.title, item.mimetype, inhalt, anker)

    async def eintrag(self, kennung: str, pfad: str) -> Eintrag:
        return await asyncio.to_thread(self._eintrag, kennung, pfad)

    def weiterleitung(self, kennung: str, pfad: str) -> str:
        """Wohin ein Pfad weiterleitet (Pfad, mit `#anker` bei Abschnitten), leer, wenn er selbst ein Artikel ist.
        Blockiert (aus einem Thread rufen); liest Inhalt nur bei kleinen Seiten, die eine Sprungseite sein können."""
        e = self.archiv(kennung).get_entry_by_path(pfad)
        if not e.is_redirect and e.get_item().size >= 4096:
            return ""
        ziel = self._eintrag(kennung, pfad)
        if ziel.pfad == pfad and not ziel.anker:
            return ""
        return ziel.pfad + (f"#{ziel.anker}" if ziel.anker else "")

    def datei(self, kennung: str, pfad: str) -> bytes | None:
        """Inhalt einer Datei im Buch (etwa die Gliederung einer Dokumentation), ohne Weiterleitungen aufzulösen; fehlt
        sie, nichts. Blockiert (aus einem Thread rufen)."""
        try:
            e = self.archiv(kennung).get_entry_by_path(pfad)
            return bytes((e.get_redirect_entry() if e.is_redirect else e).get_item().content)
        except (KeyError, BuchFehlt):
            return None

    async def name_von(self, kennung: str) -> str:
        """Name eines Buchs ohne Datum (stabil über neue Fassungen); fehlt das Buch, die Kennung ohne Datum."""
        try:
            return (await self.buch(kennung)).name
        except BuchFehlt:
            return kennung.rsplit("_", 1)[0]

    async def juengste_fassung(self, kennung: str) -> str:
        """Die jüngste Datei desselben Buchs in derselben Ausgabe (gleicher Dateiname bis auf den Stand, WIKI-58): nach
        dem Umschalten auf eine neue Fassung gilt eine Einstellung mit der alten Kennung so für die neue. Gibt es keine,
        bleibt es die Kennung."""
        stamm = STAND.sub("", kennung)
        passende = [b.kennung for b in (await self.stand()).buecher if STAND.sub("", b.kennung) == stamm]
        return max(passende, default=kennung) if stamm != kennung else kennung

    async def kennung_von(self, name: str) -> str:
        """Kennung der jüngsten Datei zu einem Namen (nach einer neuen Fassung die neue); keine: leer."""
        passende = [b for b in (await self.stand()).buecher if b.name == name]
        return max(passende, key=lambda b: (b.stand, b.kennung)).kennung if passende else ""

    def gibt_es(self, kennung: str, pfad: str) -> bool:
        """Steht ein Pfad (echter Pfad im Buch, ohne Anker) darin, auch als Weiterleitung? Für das Prüfen von Verweisen,
        ohne Inhalt zu lesen."""
        try:
            return self.archiv(kennung).has_entry_by_path(pfad)
        except BuchFehlt:
            return False
