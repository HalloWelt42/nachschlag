"""Suchkorrektur (WIKI-41, docs/SUCHE.md Punkt 9): "Meintest du ...". Zuerst über den Wortschatz der eigenen Indizes
(jedes Wort der Frage, das dort nicht vorkommt, wird durch das nächste vorkommende ersetzt: kleinster Schreibabstand,
bei Gleichstand das häufigere); erst wenn das nichts hergibt und die Suche nichts fand, fragt Nachschlag das lokale
Modell über die Leitstelle. Fachbegriffe und Code, die im Wortschatz stehen, bleiben dadurch unangetastet."""

from __future__ import annotations

import asyncio
import math
import re
import sqlite3
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from appkern.leitstelle import Leitstelle, LeitstellenFehler, Nachricht, antwortform, gerade, json_lesen

from ..eigenindex import schema

WORT = re.compile(r"[\w:$\\]+", re.UNICODE)
#: So weit darf ein Wort abweichen (Einfügen, Löschen, Ersetzen, Vertauschen): kurze Wörter weniger
ABSTAND_KURZ, ABSTAND_LANG, LANG_AB = 1, 2, 8
#: Ab so vielen Seiten gilt ein Wort als bekannt (seltene Schreibfehler stehen auch im Wortschatz)
BEKANNT_AB = 3
#: Ein Wort der Frage, das im Wortschatz steht, weicht nur einem ähnlichen, das so viel häufiger ist (häufige
#: Schreibfehler wie subsitute stehen auch dort)
HAEUFIGER = 20
#: Gewicht der Häufigkeit gegen den Abstand (log10 der Seiten): ein viel häufigeres Wort darf etwas weiter weg sein
HAEUFIGKEIT_ZAEHLT = 0.5
#: Höchstens so viele Kandidaten je Wort aus dem Wortschatz (gleicher Anfang, ähnliche Länge)
KANDIDATEN = 4000

ANWEISUNG = """Du korrigierst Tippfehler in einer Suchanfrage für ein Nachschlagewerk. Gib die Anfrage mit
berichtigter Schreibweise zurück und ändere sonst nichts: keine anderen Wörter, keine Übersetzung, Code, Namen und
Fachbegriffe bleiben. Ist nichts falsch geschrieben, gib sie unverändert zurück. Antworte nur mit {"text": "..."}."""
FORM = antwortform("korrektur", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
                                 "additionalProperties": False})


class Korrektur(BaseModel):
    frage: str
    vorschlag: str = ""                 # leer: nichts zu korrigieren
    quelle: Literal["", "wortschatz", "modell"] = ""


def falten(wort: str) -> str:
    """Wie der Tokenizer des Index: klein, ohne Akzente (remove_diacritics)."""
    zerlegt = unicodedata.normalize("NFKD", wort.lower())
    return "".join(z for z in zerlegt if not unicodedata.combining(z))


def abstand(a: str, b: str, grenze: int) -> int:
    """Schreibabstand mit Vertauschung benachbarter Zeichen (Damerau, eingeschränkt); über `grenze` früh abgebrochen."""
    if abs(len(a) - len(b)) > grenze:
        return grenze + 1
    vorvorige, vorige = None, list(range(len(b) + 1))
    for i, za in enumerate(a, 1):
        aktuelle = [i] + [0] * len(b)
        for j, zb in enumerate(b, 1):
            aktuelle[j] = min(vorige[j] + 1, aktuelle[j - 1] + 1, vorige[j - 1] + (za != zb))
            if vorvorige and i > 1 and j > 1 and za == b[j - 2] and a[i - 2] == zb:
                aktuelle[j] = min(aktuelle[j], vorvorige[j - 2] + 1)
        if min(aktuelle) > grenze:
            return grenze + 1
        vorvorige, vorige = vorige, aktuelle
    return vorige[-1]


def _vokabeln(v: sqlite3.Connection) -> None:
    v.execute("CREATE VIRTUAL TABLE IF NOT EXISTS temp.vokabeln USING fts5vocab(main, volltext, 'row')")


def _bekannt(v: sqlite3.Connection, wort: str) -> int:
    z = v.execute("SELECT doc FROM temp.vokabeln WHERE term = ?", (wort,)).fetchone()
    return z[0] if z else 0


def _kandidaten(v: sqlite3.Connection, wort: str) -> list[tuple[str, int]]:
    """Wörter mit gleichem ersten Zeichen und ähnlicher Länge (Tippfehler am Anfang sind selten)."""
    return v.execute("SELECT term, doc FROM temp.vokabeln WHERE term >= ? AND term < ? AND length(term) BETWEEN ? AND ? "
                     "ORDER BY doc DESC LIMIT ?", (wort[0], wort[0] + chr(0x10FFFF), len(wort) - 2, len(wort) + 2,
                                                   KANDIDATEN)).fetchall()


def _ersatz(verbindungen: list[sqlite3.Connection], w: str) -> str | None:
    """Das Wort, das 19:53  up 1 day,  7:02, 2 users, load averages: 58.10 43.44 43.60
USER       TTY      FROM    LOGIN@  IDLE WHAT
alpha      console  -      Sat12   31:01 -
alpha      s000     -      18:13    1:32 /Users/alpha/Entwicklung/04_Experiment ersetzen soll, oder None: im Abstand erlaubt, häufig genug, die Häufigkeit mitgewogen."""
    selbst = sum(_bekannt(v, w) for v in verbindungen)
    grenze = ABSTAND_LANG if len(w) >= LANG_AB else ABSTAND_KURZ
    mindestens = max(BEKANNT_AB, selbst * HAEUFIGER)
    beste: tuple[float, str] | None = None                        # (Wert, Wort): Abstand minus Gewicht der Häufigkeit
    for v in verbindungen:
        for term, doc in _kandidaten(v, w):
            if doc < mindestens or term == w:
                continue
            d = abstand(w, term, grenze)
            wert = d - HAEUFIGKEIT_ZAEHLT * math.log10(1 + doc)
            if d <= grenze and (beste is None or wert < beste[0]):
                beste = (wert, term)
    return beste[1] if beste else None


def ueber_wortschatz(dateien: list[Path], frage: str) -> str:
    """Die Frage mit ersetzten unbekannten Wörtern; leer, wenn alle bekannt sind oder sich keins ersetzen lässt."""
    woerter = WORT.findall(frage)
    if not woerter or not dateien:
        return ""
    verbindungen = [schema.lesen(d) for d in dateien]
    try:
        for v in verbindungen:
            _vokabeln(v)
        neu, geaendert = [], False
        for roh in woerter:
            w = falten(roh)
            if len(w) < 3 or w.isdigit():
                neu.append(roh)
                continue
            ersatz = _ersatz(verbindungen, w)
            if ersatz:                                     # ein häufiger Schreibfehler führt erst zu einem anderen:
                ersatz = _ersatz(verbindungen, ersatz) or ersatz      # dann noch einen Schritt weiter
            neu.append(ersatz or roh)
            geaendert = geaendert or bool(ersatz)
        return " ".join(neu) if geaendert else ""
    finally:
        for v in verbindungen:
            v.close()


class Korrektor:
    def __init__(self, dateien: Callable[[list[str]], list[Path]], leitstelle: Callable[[], Leitstelle | None],
                 modell: Callable[[], str]) -> None:
        """`dateien`: die geltenden eigenen Indizes der genannten Quellen (alle, wenn keine genannt sind)."""
        self._dateien, self._leitstelle, self._modell = dateien, leitstelle, modell

    async def korrigieren(self, frage: str, buecher: list[str], mit_modell: bool = False) -> Korrektur:
        frage = re.sub(r"\s+", " ", frage).strip()
        vorschlag = await asyncio.to_thread(ueber_wortschatz, self._dateien(buecher), frage)
        if vorschlag and vorschlag.lower() != frage.lower():
            return Korrektur(frage=frage, vorschlag=vorschlag, quelle="wortschatz")
        leitstelle = self._leitstelle()
        if not mit_modell or leitstelle is None:
            return Korrektur(frage=frage)
        try:
            antwort = await leitstelle.chat([Nachricht.system(ANWEISUNG), Nachricht.nutzer(frage)], modell=self._modell() or None,
                                            titel="Suche korrigieren", prioritaet="hoch", response_format=FORM, temperature=0)
            text = re.sub(r"\s+", " ", gerade(str(json_lesen(antwort.text).get("text", "")))).strip()
        except (LeitstellenFehler, ValueError, AttributeError):
            return Korrektur(frage=frage)                      # ohne Korrektur bleibt die Suche, wie sie war
        if text and text.lower() != frage.lower():
            return Korrektur(frage=frage, vorschlag=text, quelle="modell")
        return Korrektur(frage=frage)
