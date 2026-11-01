"""Aufbau eines eigenen Index: liest jede Seite eines Buchs über denselben Baustein wie das Lesen (eine Wahrheit für
Titel, Rubrik, Einleitung und Text) und schreibt sie stapelweise in die Indexdatei. Fortsetzbar: nach jedem Stapel
steht in der Datei, bei welchem Eintrag es weitergeht; ein Abbruch (Netz weg, Ruhezustand) verliert höchstens einen
Stapel. Fertig ist ein Index erst, wenn alle Einträge gelesen sind; dann steht seine Prüfsumme in einer Nachbardatei."""

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
    """Eine Seite für den Index: Felder des Volltexts und die Metadaten ihrer Inhaltsart."""
    pfad: str
    titel: str
    name: str
    rubrik: str
    einleitung: str
    text: str
    frage: FrageAngaben | None = None

    def volltext(self) -> tuple[str, str, str, str, str]:
        return self.titel, self.name, self.rubrik, self.einleitung, self.text


@dataclass
class Stand:
    erledigt: int        # Einträge der Datei gelesen
    gesamt: int
    seiten: int          # Seiten im Index
    fertig: bool


#: Nach diesen Elementen beginnt ein neues Wort (sonst klebten "Änderungen" und "Version" aus Überschrift und Tabelle)
BLOECKE = {"p", "div", "section", "li", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "tr", "pre", "br",
           "table", "ul", "ol", "dl", "figure", "figcaption", "blockquote"}


def _text(html: str) -> str:
    if not html:
        return ""
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    for el in wurzel.iter():
        if el.tag in BLOECKE:
            el.tail = " " + (el.tail or "")
            el.text = " " + (el.text or "")
    return " ".join(wurzel.text_content().split())[:TEXT_HOECHSTENS]


METADATEN = ("fragen", "schlagwoerter", "beitraege")


def _schreiben(v, zeilen: list[Zeile], naechste: int) -> None:
    """Ein Stapel in einem Zug: Seiten, Volltext, Metadaten und der Stand, bei dem es weitergeht."""
    with v:
        for z in zeilen:
            alt = v.execute("SELECT nr, titel, name, rubrik, einleitung, text FROM seiten WHERE pfad=?", (z.pfad,)).fetchone()
            if alt:   # nach einem Abbruch schon geschrieben: nicht doppelt in Volltext und Metadaten
                v.execute("INSERT INTO volltext(volltext, rowid, titel, name, rubrik, einleitung, text) VALUES('delete',?,?,?,?,?,?)",
                          (alt["nr"], alt["titel"], alt["name"], alt["rubrik"], alt["einleitung"], alt["text"]))
                for tabelle in ("seiten", *METADATEN):
                    v.execute(f"DELETE FROM {tabelle} WHERE nr=?", (alt["nr"],))
            nr = v.execute("INSERT INTO seiten (pfad, titel, name, rubrik, einleitung, text) VALUES (?,?,?,?,?,?)",
                           (z.pfad, *z.volltext())).lastrowid
            v.execute("INSERT INTO volltext(rowid, titel, name, rubrik, einleitung, text) VALUES (?,?,?,?,?,?)", (nr, *z.volltext()))
            if z.frage:
                _frage_schreiben(v, nr, z.frage)
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


def bauen(archiv: Archive, buch: Buch, wege: Wege, ziel: Path, melden: Callable[[Stand], None] | None = None,
          abbrechen: Callable[[], bool] | None = None, stapel: int = STAPEL) -> Stand:
    """Baut (oder setzt fort) den Index in `ziel`. Lesefehler der Datei (etwa Netz weg) brechen ab, ohne den Stand zu
    verlieren; der Aufrufer versucht es später erneut. `abbrechen` hält nach dem nächsten Stapel an."""
    v = schema.oeffnen(ziel)
    if schema.angabe(v, "fassung") != str(schema.FASSUNG):     # Index aus einer anderen Fassung des Schemas: neu bauen
        v.close()
        ziel.unlink()
        v = schema.oeffnen(ziel)
    try:
        gesamt = archiv.entry_count
        if schema.angabe(v, "fertig") == "1":
            return Stand(gesamt, gesamt, v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0], True)
        schema.angabe_setzen(v, "buch", buch.kennung)
        nr = int(schema.angabe(v, "naechste", "0"))
        zeilen: list[Zeile] = []
        seiten = v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0]
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
            eintrag = Eintrag(pfad=e.path, titel=e.title, mime=item.mimetype, inhalt=inhalt)
            try:
                fertig = baustein_fuer(buch, eintrag).aufbereiten(buch, eintrag, wege)
            except Exception:   # noqa: BLE001 - eine kaputte Seite hält den Index nicht auf, ein Lesefehler schon
                if not _buch_lesbar(archiv):
                    raise
                continue
            if buch.art == "frage_antwort" and fertig.frage is None:
                continue                                    # Fragenlisten, Konten, Schlagwortseiten: nur die Fragen zählen
            name = fertig.titel if fertig.titelart == "code" else ""
            zeilen.append(Zeile(e.path, fertig.titel, name, fertig.rubrik, fertig.einleitung, _text(fertig.html), fertig.frage))
            if len(zeilen) >= stapel:
                _schreiben(v, zeilen, nr)
                seiten += len(zeilen)
                zeilen = []
                if melden:
                    melden(Stand(nr, gesamt, seiten, False))
                if abbrechen and abbrechen():
                    return Stand(nr, gesamt, seiten, False)
        _schreiben(v, zeilen, gesamt)
        seiten += len(zeilen)
        _register_verdichten(v)
        with v:
            v.execute("INSERT INTO volltext(volltext) VALUES('optimize')")
            schema.angabe_setzen(v, "fertig", "1")
        v.execute("PRAGMA journal_mode = DELETE")          # eine einzige Datei, bereit zur Übertragung
    finally:
        v.close()
    ziel.with_suffix(".sha256").write_text(pruefsumme(ziel) + "\n")
    stand = Stand(gesamt, gesamt, seiten, True)
    if melden:
        melden(stand)
    return stand
