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
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from libzim.reader import Archive
from lxml import html as lhtml

from ..bausteine import Wege, baustein_fuer
from ..bibliothek import Eintrag
from ..modell.artikel import FrageAngaben
from ..modell.buch import Buch
from . import schema

#: Seiten je Stapel (so viel geht bei einem Abbruch höchstens verloren)
STAPEL = 400
#: So viel Text je Seite kommt in den Volltext (lange Seiten tragen ihr Thema vorn)
TEXT_HOECHSTENS = 20_000
_SPRUNG = re.compile(rb"http-equiv=[\"']?refresh", re.I)


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

    def metadaten(self, nr: int) -> tuple[list, list, list]:
        return (self.v.execute("SELECT stimmen, antworten, akzeptiert, gefragt, gewicht FROM fragen WHERE nr=?", (nr,)).fetchall(),
                self.v.execute("SELECT wort FROM schlagwoerter WHERE nr=?", (nr,)).fetchall(),
                self.v.execute("SELECT schluessel, autor, art, stimmen, datum, akzeptiert FROM beitraege WHERE nr=?", (nr,)).fetchall())

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
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    for el in list(wurzel.iter()):
        if NICHT_TEXT & set((el.get("class") or "").split()) and el.getparent() is not None:
            el.drop_tree()
    for el in wurzel.iter():
        if el.tag in BLOECKE:
            el.tail = " " + (el.tail or "")
            el.text = " " + (el.text or "")
    return " ".join(wurzel.text_content().split())[:TEXT_HOECHSTENS]


METADATEN = ("fragen", "schlagwoerter", "beitraege")


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
                for tabelle in ("seiten", *METADATEN):
                    v.execute(f"DELETE FROM {tabelle} WHERE nr=?", (alt["nr"],))
            nr = v.execute("INSERT INTO seiten (pfad, titel, name, rubrik, einleitung, text, abdruck) VALUES (?,?,?,?,?,?,?)",
                           (z.pfad, *z.volltext(), z.abdruck)).lastrowid
            v.execute("INSERT INTO volltext(rowid, titel, name, rubrik, einleitung, text) VALUES (?,?,?,?,?,?)", (nr, *z.volltext()))
            if z.frage:
                _frage_schreiben(v, nr, z.frage)
            elif z.aus_vorlage is not None and vorlage is not None:
                _metadaten_uebernehmen(v, nr, vorlage.metadaten(z.aus_vorlage))
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


def _metadaten_uebernehmen(v, nr: int, metadaten: tuple[list, list, list]) -> None:
    """Fragen, Schlagwörter und Beiträge einer unveränderten Seite aus der Vorlage, unter der neuen Nummer."""
    fragen, woerter, beitraege = metadaten
    v.executemany("INSERT INTO fragen (nr, stimmen, antworten, akzeptiert, gefragt, gewicht) VALUES (?,?,?,?,?,?)",
                  [(nr, *f) for f in fragen])
    v.executemany("INSERT OR IGNORE INTO schlagwoerter (wort, nr) VALUES (?,?)", [(w[0], nr) for w in woerter])
    v.executemany("INSERT INTO beitraege (nr, schluessel, autor, art, stimmen, datum, akzeptiert) VALUES (?,?,?,?,?,?,?)",
                  [(nr, *b) for b in beitraege])


def _register_verdichten(v) -> None:
    """Register aus den Metadaten: je Schlagwort Fragen und Stimmen, je Autor Beiträge, Stimmen und Zeitraum."""
    with v:
        v.execute("DELETE FROM register_schlagwoerter")
        v.execute("INSERT INTO register_schlagwoerter (wort, fragen, stimmen) SELECT s.wort, COUNT(*), COALESCE(SUM(f.stimmen), 0) "
                  "FROM schlagwoerter s JOIN fragen f ON f.nr = s.nr GROUP BY s.wort")
        v.execute("DELETE FROM register_autoren")
        v.execute("INSERT INTO register_autoren (schluessel, autor, beitraege, fragen, antworten, akzeptiert, stimmen, von, bis) "
                  "SELECT schluessel, MAX(autor), COUNT(*), SUM(art = 'frage'), SUM(art = 'antwort'), SUM(akzeptiert), "
                  "COALESCE(SUM(stimmen), 0), COALESCE(MIN(NULLIF(datum, '')), ''), COALESCE(MAX(NULLIF(datum, '')), '') "
                  "FROM beitraege GROUP BY schluessel")


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
    name = fertig.titel if fertig.titelart == "code" else ""
    return Zeile(e.path, fertig.titel, name, fertig.rubrik, fertig.einleitung, _text(fertig.html), fertig.frage, abdruck=ab)


def bauen(archiv: Archive, buch: Buch, wege: Wege, ziel: Path, melden: Callable[[Stand], None] | None = None,
          abbrechen: Callable[[], bool] | None = None, stapel: int = STAPEL, vorlage: Path | None = None) -> Stand:
    """Baut (oder setzt fort) den Index in `ziel`. Lesefehler der Datei (etwa Netz weg) brechen ab, ohne den Stand zu
    verlieren; der Aufrufer versucht es später erneut. `abbrechen` hält nach dem nächsten Stapel an. `vorlage`: Index der
    vorigen Fassung desselben Buchs; Unverändertes kommt von dort."""
    v = schema.oeffnen(ziel)
    quelle = Vorlage.oeffnen(vorlage, ziel)
    if schema.angabe(v, "fassung") != str(schema.FASSUNG):     # Index aus einer anderen Fassung des Schemas: neu bauen
        v.close()
        ziel.unlink()
        v = schema.oeffnen(ziel)
    try:
        gesamt = archiv.entry_count
        if schema.angabe(v, "fertig") == "1":
            return Stand(gesamt, gesamt, v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0], True,
                         int(schema.angabe(v, "uebernommen", "0")))
        with v:
            schema.angabe_setzen(v, "buch", buch.kennung)
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
            if len(inhalt) < 4096 and _SPRUNG.search(inhalt):
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
