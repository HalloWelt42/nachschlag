"""Aufbau eines eigenen Index: liest jede Seite eines Buchs über denselben Baustein wie das Lesen (eine Wahrheit für
Titel, Rubrik, Einleitung und Text) und schreibt sie stapelweise in die Indexdatei. Fortsetzbar: nach jedem Stapel
steht in der Datei, bei welchem Eintrag es weitergeht; ein Abbruch (Netz weg, Ruhezustand) verliert höchstens einen
Stapel. Fertig ist ein Index erst, wenn alle Einträge gelesen sind; dann steht seine Prüfsumme in einer Nachbardatei.

Neue Fassung eines Buchs (WIKI-58): mit einer Vorlage (dem Index der vorigen Fassung) wird jede Seite, deren Rohinhalt
gleich geblieben ist (gleicher Pfad, gleicher Abdruck), samt ihren Metadaten aus der Vorlage übernommen; aufbereitet wird
nur, was neu oder geändert ist. Seiten, die es nicht mehr gibt, kommen gar nicht erst hinein."""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from html import unescape
from urllib.parse import unquote
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from libzim.reader import Archive
from lxml import html as lhtml

from ..bausteine import Wege, baustein_fuer
from ..bibliothek import Eintrag
from ..bibliothek.ordner import sprungziel
from ..modell.anleitung import Anleitungsangaben, Geraeteangaben
from ..modell.artikel import FrageAngaben
from ..modell.buch import Buch
from . import schema

#: Seiten je Stapel (so viel geht bei einem Abbruch höchstens verloren)
STAPEL = 400
#: So viel Text je Seite kommt in den Volltext (lange Seiten tragen ihr Thema vorn)
TEXT_HOECHSTENS = 20_000
#: Steuerzeichen, die XML nicht erlaubt (in Seiten der Quellen vereinzelt vorhanden; lxml weist sie beim Setzen ab)
_STEUERZEICHEN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Zeile:
    """Eine Seite für den Index: Felder des Volltexts und die Metadaten ihrer Inhaltsart. `aus_vorlage`: Nummer der
    gleichen Seite im Index der vorigen Fassung, deren Metadaten mitkommen."""
    pfad: str
    titel: str
    name: str
    rubrik: str
    einleitung: str
    text: str
    frage: FrageAngaben | None = None
    anleitung: Anleitungsangaben | None = None
    geraet: Geraeteangaben | None = None
    verweise: tuple[str, ...] = ()
    abdruck: str = ""
    aus_vorlage: int | None = None

    def volltext(self) -> tuple[str, str, str, str, str]:
        return self.titel, self.name, self.rubrik, self.einleitung, self.text


@dataclass
class Stand:
    erledigt: int        # Einträge der Datei gelesen
    gesamt: int
    seiten: int          # Seiten im Index
    fertig: bool
    uebernommen: int = 0  # davon unverändert aus dem Index der vorigen Fassung


class Vorlage:
    """Der Index der vorigen Fassung, nur lesend: was dort mit gleichem Abdruck steht, muss nicht neu aufbereitet werden."""

    def __init__(self, pfad: Path) -> None:
        self.pfad = pfad
        self.v = schema.lesen(pfad)
        vorhanden = {z[0] for z in self.v.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.tabellen = [t for t in METADATEN if t in vorhanden]   # ein älterer Index kennt nicht alle Metadaten

    @classmethod
    def oeffnen(cls, pfad: Path | None, ziel: Path) -> Vorlage | None:
        """Nur ein fertiger Index dieses Schemas mit Abdrücken taugt; sonst (oder für sich selbst) keine Vorlage."""
        if pfad is None or pfad.resolve() == ziel.resolve() or not schema.gueltig(pfad):
            return None
        vorlage = cls(pfad)
        if schema.mit_abdruck(vorlage.v):
            return vorlage
        vorlage.schliessen()
        return None

    def seite(self, pfad: str, abdruck: str) -> Zeile | None:
        z = self.v.execute("SELECT nr, titel, name, rubrik, einleitung, text FROM seiten WHERE pfad=? AND abdruck=?",
                           (pfad, abdruck)).fetchone()
        if z is None:
            return None
        return Zeile(pfad, z["titel"], z["name"], z["rubrik"], z["einleitung"], z["text"], abdruck=abdruck, aus_vorlage=z["nr"])

    def ohne(self, pfad: str, abdruck: str) -> bool:
        """War die Seite schon in der vorigen Fassung gelesen und nicht im Index (etwa keine Frage)?"""
        return self.v.execute("SELECT 1 FROM ohne_seite WHERE pfad=? AND abdruck=?", (pfad, abdruck)).fetchone() is not None

    def metadaten(self, nr: int) -> dict[str, list]:
        """Je Tabelle der Metadaten die Zeilen der Seite (ohne ihre Nummer)."""
        return {t: self.v.execute(f"SELECT {', '.join(METADATEN[t])} FROM {t} WHERE nr=?", (nr,)).fetchall() for t in self.tabellen}

    def schliessen(self) -> None:
        self.v.close()


#: Nach diesen Elementen beginnt ein neues Wort (sonst klebten "Änderungen" und "Version" aus Überschrift und Tabelle)
BLOECKE = {"p", "div", "section", "li", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "tr", "pre", "br",
           "table", "ul", "ol", "dl", "figure", "figcaption", "blockquote"}


#: Bedienung des Lesedesigns, kein Inhalt: Stimmenspalte, Haken, Wer und Wann, Überschrift der Antworten
NICHT_TEXT = {"qa-stimmen", "akz-marke", "beitrag-fuss", "antworten-kopf"}


def _text(html: str) -> str:
    if not html:
        return ""
    wurzel = lhtml.fragment_fromstring(_STEUERZEICHEN.sub(" ", html), create_parent="div")
    for el in list(wurzel.iter()):
        if NICHT_TEXT & set((el.get("class") or "").split()) and el.getparent() is not None:
            el.drop_tree()
    for el in wurzel.iter():
        if el.tag in BLOECKE:
            el.tail = " " + (el.tail or "")
            el.text = " " + (el.text or "")
    return " ".join(wurzel.text_content().split())[:TEXT_HOECHSTENS]


#: Metadaten je Seite: Tabelle und ihre Spalten neben `nr`. Eine Liste für Schreiben, Ersetzen und Übernehmen.
METADATEN: dict[str, tuple[str, ...]] = {
    "fragen": ("stimmen", "antworten", "akzeptiert", "gefragt", "gewicht"),
    "schlagwoerter": ("wort",),
    "beitraege": ("schluessel", "autor", "art", "stimmen", "datum", "akzeptiert"),
    "anleitungen": ("art", "sprache", "schwierigkeit", "schwierigkeit_text", "zeit", "zeit_von", "zeit_bis", "schritte", "bild"),
    "werkzeuge": ("wort",),
    "geraete": ("bild", "kurz"),
    "geraet_kind": ("kind",),
    "geraet_anleitung": ("anleitung", "bauteil", "empfohlen"),
    "verweise": ("ziel",),
}


def _zeilen_schreiben(v, tabelle: str, nr: int, zeilen: list) -> None:
    spalten = ("nr", *METADATEN[tabelle])
    v.executemany(f"INSERT OR IGNORE INTO {tabelle} ({', '.join(spalten)}) VALUES ({', '.join('?' * len(spalten))})",
                  [(nr, *z) for z in zeilen])


def _schreiben(v, zeilen: list[Zeile], naechste: int, ohne: list[tuple[str, str]] = (),
               vorlage: Vorlage | None = None) -> None:
    """Ein Stapel in einem Zug: Seiten, Volltext, Metadaten, die übergangenen Seiten mit Abdruck und der Stand, bei dem
    es weitergeht."""
    with v:
        v.executemany("INSERT OR REPLACE INTO ohne_seite (pfad, abdruck) VALUES (?,?)", ohne)
        for z in zeilen:
            alt = v.execute("SELECT nr, titel, name, rubrik, einleitung, text FROM seiten WHERE pfad=?", (z.pfad,)).fetchone()
            if alt:   # nach einem Abbruch schon geschrieben: nicht doppelt in Volltext und Metadaten
                v.execute("INSERT INTO volltext(volltext, rowid, titel, name, rubrik, einleitung, text) VALUES('delete',?,?,?,?,?,?)",
                          (alt["nr"], alt["titel"], alt["name"], alt["rubrik"], alt["einleitung"], alt["text"]))
                for tabelle in ("seiten", *METADATEN):   # seiten zuerst, Metadaten über dieselbe Nummer
                    v.execute(f"DELETE FROM {tabelle} WHERE nr=?", (alt["nr"],))
            nr = v.execute("INSERT INTO seiten (pfad, titel, name, rubrik, einleitung, text, abdruck) VALUES (?,?,?,?,?,?,?)",
                           (z.pfad, *z.volltext(), z.abdruck)).lastrowid
            v.execute("INSERT INTO volltext(rowid, titel, name, rubrik, einleitung, text) VALUES (?,?,?,?,?,?)", (nr, *z.volltext()))
            if z.aus_vorlage is not None and vorlage is not None:
                for tabelle, metadaten in vorlage.metadaten(z.aus_vorlage).items():
                    _zeilen_schreiben(v, tabelle, nr, metadaten)
            if z.frage:
                _frage_schreiben(v, nr, z.frage)
            if z.anleitung:
                _anleitung_schreiben(v, nr, z.anleitung)
            if z.geraet:
                _geraet_schreiben(v, nr, z.geraet)
            if z.verweise:
                _zeilen_schreiben(v, "verweise", nr, [(ziel,) for ziel in z.verweise if ziel != z.pfad])
        schema.angabe_setzen(v, "naechste", str(naechste))


def _frage_schreiben(v, nr: int, f: FrageAngaben) -> None:
    # Gewicht für die Rangfolge: Stimmen logarithmisch (10 Stimmen 1, 1000 Stimmen 3), mit Haken etwas mehr
    gewicht = math.log10(1 + max(f.stimmen, 0)) + (0.5 if f.akzeptiert else 0)
    v.execute("INSERT INTO fragen (nr, stimmen, antworten, akzeptiert, gefragt, gewicht) VALUES (?,?,?,?,?,?)",
              (nr, f.stimmen, f.antworten, int(f.akzeptiert), f.gefragt, gewicht))
    v.executemany("INSERT OR IGNORE INTO schlagwoerter (wort, nr) VALUES (?,?)", [(w.lower(), nr) for w in f.schlagwoerter])
    v.executemany("INSERT INTO beitraege (nr, schluessel, autor, art, stimmen, datum, akzeptiert) VALUES (?,?,?,?,?,?,?)",
                  [(nr, schema.autor_schluessel(b.autor_nr, b.autor), b.autor, b.art, b.stimmen, b.datum, int(b.akzeptiert))
                   for b in f.beitraege if b.autor])


_HREF = re.compile(r'href="([^"]+)"')


def _verweise(html: str, praefix: str) -> tuple[str, ...]:
    """Die Seiten desselben Buchs, auf die eine aufbereitete Seite verweist (Pfade, ohne Anker, jede einmal). Die
    Bausteine schreiben solche Verweise auf `wege.artikel`, also auf `praefix` + Pfad."""
    aus: dict[str, None] = {}
    for href in _HREF.findall(html):
        href = unescape(href)
        if href.startswith(praefix):
            ziel = unquote(href[len(praefix):].split("#", 1)[0].split("?", 1)[0])
            if ziel:
                aus[ziel] = None
    return tuple(aus)


def _anleitung_schreiben(v, nr: int, a: Anleitungsangaben) -> None:
    bild = a.hauptbild or next((s.bilder[0] for s in a.schritte if s.bilder), "")
    _zeilen_schreiben(v, "anleitungen", nr, [(a.art, a.sprache, a.schwierigkeit, a.schwierigkeit_text, a.zeit, a.zeit_von,
                                              a.zeit_bis, len(a.schritte), bild)])
    _zeilen_schreiben(v, "werkzeuge", nr, [(w.name,) for w in a.werkzeuge])


def _geraet_schreiben(v, nr: int, g: Geraeteangaben) -> None:
    """Geräteseite, Kategorie oder Startseite: Bild, Kurztext, Unterkategorien und Anleitungen (Bauteil = Titel dort)."""
    _zeilen_schreiben(v, "geraete", nr, [(g.bild, g.kurz)])
    _zeilen_schreiben(v, "geraet_kind", nr, [(e.pfad,) for e in g.unterkategorien])
    _zeilen_schreiben(v, "geraet_anleitung", nr, [(e.pfad, e.bauteil or e.titel, int(e.empfohlen)) for e in g.anleitungen])


def _register_verdichten(v) -> None:
    """Register aus den Metadaten: je Schlagwort Fragen und Stimmen, je Autor Beiträge, Stimmen und Zeitraum, je Werkzeug
    und Sprache die Anleitungen, die es brauchen."""
    with v:
        v.execute("DELETE FROM register_schlagwoerter")
        v.execute("INSERT INTO register_schlagwoerter (wort, fragen, stimmen) SELECT s.wort, COUNT(*), COALESCE(SUM(f.stimmen), 0) "
                  "FROM schlagwoerter s JOIN fragen f ON f.nr = s.nr GROUP BY s.wort")
        v.execute("DELETE FROM register_autoren")
        v.execute("INSERT INTO register_autoren (schluessel, autor, beitraege, fragen, antworten, akzeptiert, stimmen, von, bis) "
                  "SELECT schluessel, MAX(autor), COUNT(*), SUM(art = 'frage'), SUM(art = 'antwort'), SUM(akzeptiert), "
                  "COALESCE(SUM(stimmen), 0), COALESCE(MIN(NULLIF(datum, '')), ''), COALESCE(MAX(NULLIF(datum, '')), '') "
                  "FROM beitraege GROUP BY schluessel")
        v.execute("DELETE FROM register_werkzeuge")
        v.execute("INSERT INTO register_werkzeuge (wort, sprache, anleitungen) SELECT w.wort, a.sprache, COUNT(*) "
                  "FROM werkzeuge w JOIN anleitungen a ON a.nr = w.nr GROUP BY w.wort, a.sprache")
        v.execute("DELETE FROM register_einordnung")
        v.executemany("INSERT OR IGNORE INTO register_einordnung (oben, nr) VALUES (?,?)", _einordnung(v))


def _einordnung(v):
    """Je Anleitung jede Geräteseite darüber: die Geräte, die sie aufführen, und deren Kategorien bis zur Startseite.
    Der Baum der Quelle ist kein reiner Baum (eine Kategorie kann mehrere Eltern haben, selten auch einen Kreis)."""
    eltern: dict[str, list[str]] = defaultdict(list)
    for kind, pfad in v.execute("SELECT k.kind, s.pfad FROM geraet_kind k JOIN seiten s ON s.nr = k.nr"):
        eltern[kind].append(pfad)
    ahnen: dict[str, set[str]] = {}

    def darueber(pfad: str) -> set[str]:
        if pfad not in ahnen:
            gesehen, offen = {pfad}, [pfad]
            while offen:
                for e in eltern.get(offen.pop(), ()):
                    if e not in gesehen:
                        gesehen.add(e)
                        offen.append(e)
            ahnen[pfad] = gesehen
        return ahnen[pfad]

    for nr, geraet in v.execute("SELECT a.nr, s.pfad FROM geraet_anleitung g JOIN seiten s ON s.nr = g.nr "
                                "JOIN seiten a ON a.pfad = g.anleitung").fetchall():
        for oben in darueber(geraet):
            yield oben, nr


def titelfolge_bauen(v) -> None:
    """Sortierschlüssel nach deutscher Ordnung je Seite (WIKI-21); liest nur den Index, nicht das Buch."""
    with v:
        v.execute("DELETE FROM titelfolge")
        v.executemany("INSERT OR IGNORE INTO titelfolge (schluessel, nr) VALUES (?, ?)",
                      ((schema.sortierschluessel(titel), nr) for nr, titel in v.execute("SELECT nr, titel FROM seiten").fetchall()))
        schema.angabe_setzen(v, "ergaenzung", str(schema.ERGAENZUNG))


def _buch_lesbar(archiv: Archive) -> bool:
    """Ob die Datei des Buchs noch zu lesen ist (über die Freigabe: Netz da). Entscheidet, ob ein Fehler beim Aufbereiten
    an der Seite liegt (überspringen) oder am Lesen (anhalten, später weiter)."""
    try:
        with open(archiv.filename, "rb") as f:
            f.seek(max(0, archiv.filesize - 4096))
            f.read(4096)
        return True
    except OSError:
        return False


def _startseite(archiv: Archive) -> str:
    """Pfad der Startseite (Wurzel des Gerätebaums eines Anleitungsbuchs); leer, wenn das Buch keine nennt."""
    try:
        return archiv.main_entry.get_item().path if archiv.has_main_entry else ""
    except (KeyError, RuntimeError):
        return ""


def pruefsumme(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for stueck in iter(lambda: f.read(1 << 20), b""):
            h.update(stueck)
    return h.hexdigest()


def _aufbereiten(archiv: Archive, buch: Buch, wege: Wege, e, mime: str, inhalt: bytes, ab: str) -> Zeile | None:
    """Eine neue oder geänderte Seite für den Index aufbereiten; keine Zeile, wenn sie nicht hineingehört (kaputt,
    bei Frage und Antwort keine Frage)."""
    eintrag = Eintrag(pfad=e.path, titel=e.title, mime=mime, inhalt=inhalt)
    try:
        fertig = baustein_fuer(buch, eintrag).aufbereiten(buch, eintrag, wege)
    except Exception:   # noqa: BLE001 - eine kaputte Seite hält den Index nicht auf, ein Lesefehler schon
        if not _buch_lesbar(archiv):
            raise
        return None
    if buch.art == "frage_antwort" and fertig.frage is None:
        return None                                     # Fragenlisten, Konten, Schlagwortseiten: nur die Fragen zählen
    if buch.art == "anleitung" and fertig.anleitung is None and fertig.geraet is None:
        return None                                     # Benutzerseiten, Infoseiten: nur Anleitungen und Geräte zählen
    name = fertig.titel if fertig.titelart == "code" else ""
    return Zeile(e.path, fertig.titel, name, fertig.rubrik, fertig.einleitung, _text(fertig.html), fertig.frage,
                 fertig.anleitung, fertig.geraet, verweise=_verweise(fertig.html, wege.artikel(buch.kennung, "")), abdruck=ab)


def bauen(archiv: Archive, buch: Buch, wege: Wege, ziel: Path, melden: Callable[[Stand], None] | None = None,
          abbrechen: Callable[[], bool] | None = None, stapel: int = STAPEL, vorlage: Path | None = None) -> Stand:
    """Baut (oder setzt fort) den Index in `ziel`. Lesefehler der Datei (etwa Netz weg) brechen ab, ohne den Stand zu
    verlieren; der Aufrufer versucht es später erneut. `abbrechen` hält nach dem nächsten Stapel an. `vorlage`: Index der
    vorigen Fassung desselben Buchs; Unverändertes kommt von dort."""
    wege = replace(wege, medien=lambda _buch, pfad: pfad)      # Bilder im Index als Pfad im Buch, gültig über Fassungen
    v = schema.oeffnen(ziel)
    quelle = Vorlage.oeffnen(vorlage, ziel)
    if schema.angabe(v, "fassung") != str(schema.FASSUNG):     # Index aus einer anderen Fassung des Schemas: neu bauen
        v.close()
        ziel.unlink()
        v = schema.oeffnen(ziel)
    try:
        gesamt = archiv.entry_count
        if schema.angabe(v, "fertig") == "1":
            seiten, uebernommen = v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0], int(schema.angabe(v, "uebernommen", "0"))
            if int(schema.angabe(v, "ergaenzung", "0") or 0) < schema.ERGAENZUNG:
                titelfolge_bauen(v)                         # fertig, aber ohne die Ergänzungen dieses Stands: nachziehen
                v.execute("PRAGMA journal_mode = DELETE")
                v.close()
                ziel.with_suffix(".sha256").write_text(pruefsumme(ziel) + "\n")
            return Stand(gesamt, gesamt, seiten, True, uebernommen)
        with v:
            schema.angabe_setzen(v, "buch", buch.kennung)
            if schema.angabe(v, "naechste", "0") == "0":   # neu angefangen: dieser Index kennt die Verweise (WIKI-20)
                schema.angabe_setzen(v, "verweise", "1")
            schema.angabe_setzen(v, "startseite", _startseite(archiv))
            if quelle:
                schema.angabe_setzen(v, "vorlage", quelle.pfad.name)
        nr = int(schema.angabe(v, "naechste", "0"))
        uebernommen = int(schema.angabe(v, "uebernommen", "0"))
        zeilen: list[Zeile] = []
        ohne: list[tuple[str, str]] = []
        seiten = v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0]

        def stapel_schreiben(bis: int) -> None:
            nonlocal zeilen, ohne, seiten, uebernommen
            uebernommen += sum(1 for z in zeilen if z.aus_vorlage is not None)
            _schreiben(v, zeilen, bis, ohne, quelle)
            with v:
                schema.angabe_setzen(v, "uebernommen", str(uebernommen))
            seiten += len(zeilen)
            zeilen, ohne = [], []

        while nr < gesamt:
            e = archiv.get_entry_by_id(nr)
            nr += 1
            if e.is_redirect or e.path.startswith("_"):
                continue
            item = e.get_item()
            if not item.mimetype.startswith("text/html"):
                continue
            inhalt = bytes(item.content)
            if sprungziel(item.mimetype, inhalt):
                continue                                    # Sprungseite: zeigt auf eine andere Seite
            ab = schema.abdruck(inhalt)
            gleich = quelle.seite(e.path, ab) if quelle else None
            if gleich:
                zeilen.append(gleich)
            elif quelle and quelle.ohne(e.path, ab):
                ohne.append((e.path, ab))
            else:
                zeile = _aufbereiten(archiv, buch, wege, e, item.mimetype, inhalt, ab)
                if zeile:
                    zeilen.append(zeile)
                else:
                    ohne.append((e.path, ab))
            if len(zeilen) >= stapel:
                stapel_schreiben(nr)
                if melden:
                    melden(Stand(nr, gesamt, seiten, False, uebernommen))
                if abbrechen and abbrechen():
                    return Stand(nr, gesamt, seiten, False, uebernommen)
        stapel_schreiben(gesamt)
        _register_verdichten(v)
        titelfolge_bauen(v)
        with v:
            v.execute("INSERT INTO volltext(volltext) VALUES('optimize')")
            schema.angabe_setzen(v, "fertig", "1")
        v.execute("PRAGMA journal_mode = DELETE")          # eine einzige Datei, bereit zur Übertragung
    finally:
        v.close()
        if quelle:
            quelle.schliessen()
    ziel.with_suffix(".sha256").write_text(pruefsumme(ziel) + "\n")
    stand = Stand(gesamt, gesamt, seiten, True, uebernommen)
    if melden:
        melden(stand)
    return stand
