"""Die Kategorien eines Buchs bauen (auf dem Mac, im Index-Dienst): die Seiten des Buchs aus der ZIM-Datei mit dem
aufbereiteten Datenabzug seines Wikis zusammenführen (schema.py beschreibt die Datei).

1. Alle Artikel des Buchs lesen (Pfad und Titel; Weiterleitungen nicht) und über den Titel im Abzug finden.
2. Ihre Kategorien nehmen und von dort aufwärts alle Kategorien darüber, bis zur obersten (der Baum hat Kreise; jede
   Kategorie zählt einmal). Kategorien ohne Seite des Buchs darunter fehlen so von selbst.
3. Nummern nach der Ordnung der Titel vergeben und schreiben."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from libzim.reader import Archive

from . import schema
from ..eigenindex.aufbau import pruefsumme

#: so viele Einträge der ZIM-Datei, dann eine Meldung und die Frage nach dem Abbruch
STAPEL = 20_000


@dataclass
class Stand:
    erledigt: int
    gesamt: int
    seiten: int
    fertig: bool


def _artikel(archiv: Archive, melden: Callable[[Stand], None], abbrechen: Callable[[], bool]) -> dict[str, str] | None:
    """Pfad und Titel aller Artikel (HTML, keine Weiterleitung, keine inneren Dateien); abgebrochen: None."""
    gesamt, aus = archiv.entry_count, {}
    for nr in range(gesamt):
        e = archiv.get_entry_by_id(nr)
        if not (e.is_redirect or e.path.startswith("_")) and e.get_item().mimetype.startswith("text/html"):
            aus[e.path] = e.title or e.path
        if nr % STAPEL == 0:
            melden(Stand(nr, gesamt, 0, False))
            if abbrechen():
                return None
    return aus


def _aufwaerts(start: set[int], ober: dict[int, list[int]]) -> set[int]:
    """Alle Kategorien ab `start` und darüber; Kreise im Baum halten nicht auf."""
    gesehen, offen = set(start), list(start)
    while offen:
        for o in ober.get(offen.pop(), ()):
            if o not in gesehen:
                gesehen.add(o)
                offen.append(o)
    return gesehen


def bauen(archiv: Archive, kennung: str, abzug: Path, ziel: Path, melden: Callable[[Stand], None] = lambda _s: None,
          abbrechen: Callable[[], bool] = lambda: False) -> Stand | None:
    """Baut die Kategorien des Buchs in `ziel` (neu, nie fortgesetzt: der teure Teil ist der Abzug, und der bleibt).
    Abgebrochen: None."""
    artikel = _artikel(archiv, melden, abbrechen)
    if artikel is None:
        return None
    a = sqlite3.connect(f"file:{abzug}?mode=ro", uri=True)
    try:
        angaben = dict(a.execute("SELECT schluessel, wert FROM angaben").fetchall())
        ids: dict[int, str] = {}
        for pfad in artikel:                                    # der Pfad einer Wikipedia-Seite ist ihr Titel im Wiki
            z = a.execute("SELECT id FROM seite WHERE titel=?", (pfad,)).fetchone()
            if z:
                ids[z[0]] = pfad
        direkt: dict[int, list[int]] = defaultdict(list)       # Seite -> Kategorien
        for seite, kat in a.execute("SELECT seite, kat FROM kseite"):
            if seite in ids:
                direkt[seite].append(kat)
        ober: dict[int, list[int]] = defaultdict(list)
        for unter, o in a.execute("SELECT unter, ober FROM kante"):
            ober[unter].append(o)
        bewohnt = _aufwaerts({k for ks in direkt.values() for k in ks}, ober)
        titel = {i: t for i, t in a.execute("SELECT id, titel FROM kat") if i in bewohnt}
    finally:
        a.close()

    kat_nr = {i: n for n, i in enumerate(sorted(titel, key=lambda i: schema.ordnung(titel[i])), start=1)}
    seiten = sorted(direkt, key=lambda s: schema.ordnung(artikel[ids[s]]))
    seite_nr = {s: n for n, s in enumerate(seiten, start=1)}
    zaehler: dict[int, int] = defaultdict(int)
    for ks in direkt.values():
        for k in ks:
            zaehler[k] += 1

    v = schema.oeffnen(ziel)
    try:
        with v:
            v.executemany("INSERT INTO kategorie VALUES (?, ?, ?)", ((kat_nr[i], t, zaehler[i]) for i, t in titel.items()))
            v.executemany("INSERT INTO seite VALUES (?, ?, ?)", ((seite_nr[s], ids[s], artikel[ids[s]]) for s in seiten))
            v.executemany("INSERT INTO seite_kategorie VALUES (?, ?)",
                          ((kat_nr[k], seite_nr[s]) for s, ks in direkt.items() for k in ks))
            v.executemany("INSERT OR IGNORE INTO unterkategorie VALUES (?, ?)",
                          ((kat_nr[o], kat_nr[u]) for u, os_ in ober.items() if u in kat_nr for o in os_ if o in kat_nr))
            for schluessel in ("wiki", "stand", "namensraum", "wurzel"):
                schema.angabe_setzen(v, schluessel, angaben.get(schluessel, ""))
            schema.angabe_setzen(v, "buch", kennung)
            schema.angabe_setzen(v, "fassung", str(schema.FASSUNG))
        v.executescript(schema.INDIZES)
        with v:
            schema.angabe_setzen(v, "fertig", "1")
        v.execute("VACUUM")
    finally:
        v.close()
    ziel.with_suffix(".sha256").write_text(pruefsumme(ziel) + "\n")
    stand = Stand(archiv.entry_count, archiv.entry_count, len(seiten), True)
    melden(stand)
    return stand
