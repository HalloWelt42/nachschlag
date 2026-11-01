"""Zitieren (WIKI-31): die Angaben einer Seite für eine Quellenangabe und die Zitierformen, an einer Stelle. Notizblatt,
Literaturliste und Schnittstelle nehmen sie von hier; keine Form wird anderswo nachgebaut.

Formen: einfach (Titel, Quelle, Adresse, Abruf; wie bisher), APA (7. Auflage, deutsche Schreibweise), DIN ISO 690 und
BibTeX (@misc). Ohne Autor (Enzyklopädie, Handbuch) steht der Titel vorn; Frage und Antwort nennt, wer fragte und wann."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Form = Literal["einfach", "apa", "din", "bibtex"]
FORMEN: tuple[Form, ...] = ("einfach", "apa", "din", "bibtex")
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November",
          "Dezember")
#: Zeichen, die BibTeX in Feldern als Befehl liest
BIBTEX_ZEICHEN = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
                  "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


class Zitierangaben(BaseModel):
    """Was eine Quellenangabe braucht. Daten als JJJJ-MM-TT."""
    titel: str
    quelle: str = Field(description="das Werk, etwa der Titel der Quelle in der Bibliothek")
    stand: str = Field("", description="Stand der Quelle (Fassung der Datei)")
    url: str = Field("", description="die Seite im Netz")
    autor: str = Field("", description="wer die Seite verfasst hat, soweit die Quelle es nennt (Frage und Antwort)")
    datum: str = Field("", description="wann sie verfasst wurde (Frage und Antwort: gefragt am)")


class Zitate(BaseModel):
    """Eine Seite in allen Formen (für das Notizblatt: die Form wählt das Gerät)."""
    angaben: Zitierangaben
    einfach: str
    apa: str
    din: str
    bibtex: str


def _tag(iso: str) -> date | None:
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", iso.strip())
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def _satz(text: str) -> str:
    """Mit Punkt am Ende, außer es endet schon mit einem Satzzeichen (How do I exit Vim?)."""
    return text if text.endswith((".", "?", "!")) else text + "."


def _kurz(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _lang(d: date) -> str:
    return f"{d.day}. {MONATE[d.month - 1]} {d.year}"


def einfach(a: Zitierangaben, heute: date) -> str:
    vorn = f"{a.autor}: " if a.autor else ""
    tag = _tag(a.datum)
    return (f"{vorn}{_satz(a.titel + (f' ({_kurz(tag)})' if tag else ''))} In: {_satz(a.quelle)}"
            + (f" {a.url} (abgerufen am {_kurz(heute)})" if a.url else ""))


def apa(a: Zitierangaben, heute: date) -> str:
    """APA 7 auf Deutsch: Autor. (Jahr, Tag. Monat). Titel [Forumsbeitrag]. In Quelle. Abgerufen am ..., von URL;
    ohne Autor rückt der Titel nach vorn, ohne Datum steht o. J. Einen Autor nennen nur Frage-und-Antwort-Seiten."""
    tag = _tag(a.datum) or _tag(a.stand)
    wann = f"({tag.year}, {tag.day}. {MONATE[tag.month - 1]})" if tag else "(o. J.)"
    kopf = f"{_satz(a.autor)} {wann}. {a.titel} [Forumsbeitrag]." if a.autor else f"{_satz(a.titel)} {wann}."
    return f"{kopf} In {_satz(a.quelle)}" + (f" Abgerufen am {_lang(heute)}, von {a.url}" if a.url else "")


def din(a: Zitierangaben, heute: date) -> str:
    """DIN ISO 690: AUTOR: Titel. In: Quelle. Datum. Stand. URL (Abruf)."""
    vorn = f"{a.autor}: " if a.autor else ""
    teile = [f"{vorn}{_satz(a.titel)} In: {_satz(a.quelle)}"]
    if tag := _tag(a.datum):
        teile.append(f"{_kurz(tag)}.")
    if stand := _tag(a.stand):
        teile.append(f"Stand: {_kurz(stand)}.")
    if a.url:
        teile.append(f"URL: {a.url} (abgerufen am {_kurz(heute)})")
    return " ".join(teile)


def _bibtex_text(text: str) -> str:
    return "".join(BIBTEX_ZEICHEN.get(z, z) for z in text)


def schluessel(a: Zitierangaben) -> str:
    """Kennung des Eintrags: erstes Wort von Autor oder Titel in ASCII, dazu das Jahr (rotfuchs2026)."""
    woerter = (a.autor or a.titel).split()
    roh = unicodedata.normalize("NFKD", woerter[0] if woerter else "").encode("ascii", "ignore").decode().lower()
    wort = re.sub(r"[^a-z0-9]", "", roh) or "quelle"
    tag = _tag(a.datum) or _tag(a.stand)
    return f"{wort}{tag.year if tag else ''}"


def bibtex(a: Zitierangaben, heute: date, *, kennung: str = "") -> str:
    tag = _tag(a.datum) or _tag(a.stand)
    felder = [("title", "{" + _bibtex_text(a.titel) + "}")]
    if a.autor:                          # Namen von Konten, keine bürgerlichen Namen: nicht in Vor- und Nachname teilen
        felder.append(("author", "{" + _bibtex_text(a.autor) + "}"))
    felder.append(("howpublished", _bibtex_text(a.quelle)))
    if tag:
        felder.append(("year", str(tag.year)))
    if a.url:
        felder.append(("url", a.url))
    stand = _tag(a.stand)
    notiz = ", ".join(x for x in (f"Stand {_kurz(stand)}" if stand else "", f"abgerufen am {_kurz(heute)}" if a.url else "") if x)
    if notiz:
        felder.append(("note", notiz))
    zeilen = ",\n".join(f"  {k} = {{{v}}}" for k, v in felder)
    return f"@misc{{{kennung or schluessel(a)},\n{zeilen}\n}}"


def zitieren(a: Zitierangaben, form: Form, heute: date | None = None) -> str:
    heute = heute or date.today()
    return {"einfach": einfach, "apa": apa, "din": din, "bibtex": bibtex}[form](a, heute)


def zitate(a: Zitierangaben, heute: date | None = None) -> Zitate:
    heute = heute or date.today()
    return Zitate(angaben=a, **{f: zitieren(a, f, heute) for f in FORMEN})
