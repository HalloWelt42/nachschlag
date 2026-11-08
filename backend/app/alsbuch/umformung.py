"""Umformung durch das Sprachmodell (WIKI-45): Anweisungen, Antwortformen und das nachsichtige Lesen der Antworten. Reine
Umformung; gefragt wird über die Leitstelle im Dienst.

Feste Regeln gelten für jede Vorlage: nur was in den Artikeln steht, Beleg je Absatz, Zahlen genau wie im Original.
Danach folgen Ton, Leserschaft und Länge der Bestellung und der Zusatz der Vorlage in eigenen Worten. Je Artikel gibt es
bis zu drei Arten von Anfragen: Umformen (je Stück des Artikels), Teile je Artikel (Auf einen Blick und eigene Kästen,
eine Anfrage) und Neuschreiben eines Absatzes (Probekapitel); je Kapitel eine für Einleitung, Fragen und Glossar."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from appkern.leitstelle import antwortform, gerade

from ..modell.alsbuch import Absatz, Belegt, Frage, FuerWen, Glossareintrag, Kasten, Laenge, Teil, Ton, Vorlage
from .quelle import Quellblock, als_eingabe

FESTE_REGELN = [
    "Schreibe nur, was in den nummerierten Absätzen des Originals steht. Kein Wissen von außen, keine eigenen Beispiele, "
    "Vergleiche oder Wertungen.",
    "Jeder Absatz und jeder Punkt deines Textes nennt in \"belege\" die Nummern der Absätze des Originals, aus denen er "
    "stammt (mindestens eine).",
    "Zahlen, Maße, Jahreszahlen und Namen gibst du genau wie im Original wieder: nicht runden, nicht umrechnen, nichts "
    "dazurechnen.",
    "Schreibe auf Deutsch, in ganzen Sätzen, ohne Markdown und ohne Aufzählungszeichen im Text.",
]
#: Die festen Regeln in Worten für die Oberfläche (Seite Als Buch und Vorlagen)
REGELN_KURZ = ["nur was in den Artikeln steht", "Beleg je Absatz", "Zahlen gegen das Original geprüft"]

TON: dict[Ton, str] = {
    "sachlich": "Schreibe sachlich und klar wie ein gutes Sachbuch.",
    "erzaehlend": "Schreibe erzählend und anschaulich, aber ohne etwas auszuschmücken, das nicht im Original steht.",
    "locker": "Schreibe locker und direkt und sprich die Leser mit du an.",
}
FUER_WEN: dict[FuerWen, str] = {
    "erwachsene": "Die Leser sind Erwachsene ohne Vorwissen im Fach.",
    "jugendliche": "Die Leser sind Jugendliche ab 14 Jahren: Fachwörter beim ersten Vorkommen kurz erklären.",
    "kinder": "Die Leser sind Kinder ab 10 Jahren: kurze Sätze, einfache Wörter, jedes Fachwort erklären.",
}
LAENGE: dict[Laenge, str] = {
    "original": "Behalte alle Aussagen und Einzelheiten; dein Text ist etwa so lang wie das Original.",
    "haelfte": "Kürze auf etwa die Hälfte: lass Einzelheiten weg, nie die Hauptaussagen.",
    "wichtigste": "Nur das Wichtigste: etwa ein Viertel der Länge des Originals.",
}
#: Anteil der Länge des Originals, den die Länge ergibt (für die Schätzung)
FAKTOR: dict[Laenge, float] = {"original": 1.0, "haelfte": 0.5, "wichtigste": 0.25}
LAENGE_TEXT: dict[Laenge, str] = {"original": "wie im Original", "haelfte": "auf die Hälfte", "wichtigste": "nur das Wichtigste"}
#: so viel vom Original geht höchstens in die Anfrage der Teile je Artikel (Auf einen Blick, eigene Kästen)
TEILE_ZEICHEN = 24_000
#: so viel vom umgeformten Kapitel geht höchstens in die Anfrage je Kapitel
KAPITEL_ZEICHEN = 24_000
GLOSSAR_HOECHSTENS = 8


def schluessel(*teile: str) -> str:
    """Schlüssel eines Ergebnisses im Zwischenspeicher: gleiche Anfrage, gleiches Ergebnis (so formt ein Nachbau nur
    Neues um)."""
    return hashlib.sha256("\x1f".join(teile).encode()).hexdigest()


def system(vorlage: Vorlage, fuer_wen: FuerWen, laenge: Laenge, aufgabe: str) -> str:
    regeln = "\n".join(f"{i}. {r}" for i, r in enumerate(FESTE_REGELN, 1))
    zeilen = [f"Du formst Artikel aus Nachschlagewerken für ein Buch um (Vorlage {vorlage.titel}).",
              f"Feste Regeln, die immer gelten:\n{regeln}",
              " ".join([TON[vorlage.anweisung.ton], FUER_WEN[fuer_wen], LAENGE[laenge]])]
    if vorlage.anweisung.zusatz.strip():
        zeilen.append(f"Zusatz der Vorlage: {vorlage.anweisung.zusatz.strip()}")
    zeilen.append(aufgabe)
    return "\n\n".join(zeilen)


def _zahlen(werte: Any, erlaubt: set[int]) -> list[int]:
    aus: list[int] = []
    for w in werte if isinstance(werte, list) else []:
        try:
            n = int(w)
        except (TypeError, ValueError):
            continue
        if n in erlaubt and n not in aus:
            aus.append(n)
    return aus


def _text(wert: Any, laenge: int = 4000) -> str:
    return " ".join(gerade(str(wert or "")).split())[:laenge]


_BELEGT = {"type": "object", "additionalProperties": False, "required": ["text", "belege"],
           "properties": {"text": {"type": "string"}, "belege": {"type": "array", "items": {"type": "integer"}}}}


# ----- Umformen eines Stücks --------------------------------------------------------------------------------------------

UMFORMEN_AUFGABE = ("Forme den Artikel nach diesen Vorgaben um. Antworte nur mit JSON: {\"absaetze\": [{\"ueberschrift\": "
                    "\"\", \"text\": \"...\", \"belege\": [1, 2]}]}. \"ueberschrift\" ist leer oder eine kurze "
                    "Zwischenüberschrift (höchstens fünf Wörter), die vor dem Absatz steht.")
UMFORMEN_FORM = antwortform("umformung", {
    "type": "object", "additionalProperties": False, "required": ["absaetze"],
    "properties": {"absaetze": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["ueberschrift", "text", "belege"],
        "properties": {"ueberschrift": {"type": "string"}, "text": {"type": "string"},
                       "belege": {"type": "array", "items": {"type": "integer"}}}}}}})


def umformen_eingabe(titel: str, bloecke: list[Quellblock], fortsetzung: bool) -> str:
    kopf = f"Artikel: {titel}" + (" (Fortsetzung; ohne neue Einleitung weiterschreiben)" if fortsetzung else "")
    return f"{kopf}\n\n{als_eingabe(bloecke)}"


def umformung_lesen(roh: dict[str, Any], erlaubt: set[int]) -> list[Absatz]:
    """Absätze aus der Antwort: ohne Text fallen sie weg, Belege nur auf Nummern dieses Stücks."""
    aus = []
    for a in roh.get("absaetze") or []:
        if not isinstance(a, dict) or not (text := _text(a.get("text"))):
            continue
        aus.append(Absatz(text=text, ueberschrift=_text(a.get("ueberschrift"), 80), ebene=2,
                          belege=_zahlen(a.get("belege"), erlaubt)))
    return aus


# ----- Teile je Artikel (Auf einen Blick, eigene Kästen) -----------------------------------------------------------------

def artikelteile_aufgabe(blick: bool, kaesten: list[Teil]) -> str:
    teile = []
    if blick:
        teile.append("- \"blick\" (Auf einen Blick): drei bis sechs kurze Punkte mit den Kernaussagen des Artikels.")
    for i, k in enumerate(kaesten, 1):
        teile.append(f"- Kasten {i} \"{k.titel}\": {k.anweisung.strip()} Steht dazu nichts im Artikel, bleibt der Kasten leer.")
    return ("Schreibe diese Teile zum Artikel, je Punkt mit Belegen:\n" + "\n".join(teile)
            + "\nAntworte nur mit JSON: {\"blick\": [{\"text\": \"...\", \"belege\": [1]}], \"kaesten\": [[{\"text\": \"...\", "
              "\"belege\": [2]}]]}; \"kaesten\" enthält je Kasten in dieser Reihenfolge eine Liste von Punkten.")


def artikelteile_form(blick: bool, kaesten: int) -> dict[str, Any]:
    punkte = {"type": "array", "items": _BELEGT}
    eigenschaften: dict[str, Any] = {}
    if blick:
        eigenschaften["blick"] = punkte
    if kaesten:
        eigenschaften["kaesten"] = {"type": "array", "items": punkte, "minItems": kaesten, "maxItems": kaesten}
    return antwortform("artikelteile", {"type": "object", "additionalProperties": False, "required": list(eigenschaften),
                                        "properties": eigenschaften})


def _punkte(werte: Any, erlaubt: set[int], hoechstens: int = 12) -> list[Belegt]:
    aus = []
    for p in werte if isinstance(werte, list) else []:
        if isinstance(p, dict) and (text := _text(p.get("text"), 600)):
            aus.append(Belegt(text=text, belege=_zahlen(p.get("belege"), erlaubt)))
        elif isinstance(p, str) and (text := _text(p, 600)):
            aus.append(Belegt(text=text))
    return aus[:hoechstens]


def artikelteile_lesen(roh: dict[str, Any], blick: bool, kaesten: list[Teil], erlaubt: set[int]) -> tuple[Kasten | None, list[Kasten]]:
    b = Kasten(titel="Auf einen Blick", punkte=_punkte(roh.get("blick"), erlaubt)) if blick else None
    roh_kaesten = roh.get("kaesten") if isinstance(roh.get("kaesten"), list) else []
    eigene = [Kasten(titel=k.titel, punkte=_punkte(roh_kaesten[i] if i < len(roh_kaesten) else [], erlaubt))
              for i, k in enumerate(kaesten)]
    return b, eigene


# ----- Teile je Kapitel (Einleitung, Fragen, Glossar) --------------------------------------------------------------------

def kapitelteile_aufgabe(titel: str, einleitung: bool, fragen: int, glossar: bool) -> str:
    teile = []
    if einleitung:
        teile.append("- \"einleitung\": zwei bis vier Sätze, die ins Kapitel führen.")
    if fragen:
        teile.append(f"- \"fragen\": genau {fragen} Fragen zum Wiederholen, je mit kurzer Antwort.")
    if glossar:
        teile.append(f"- \"glossar\": bis zu {GLOSSAR_HOECHSTENS} Fachbegriffe, die im Kapitel vorkommen, je mit einer "
                     "Erklärung in einem Satz.")
    return (f"Schreibe zum Kapitel \"{titel}\" diese Teile; die Belege sind hier die Nummern der Artikel (A1, A2 ...) als "
            "Zahl:\n" + "\n".join(teile) + "\nAntworte nur mit JSON mit genau diesen Feldern: einleitung (Liste von "
            "{text, belege}), fragen (Liste von {frage, antwort, belege}), glossar (Liste von {begriff, erklaerung}).")


def kapitelteile_form(einleitung: bool, fragen: int, glossar: bool) -> dict[str, Any]:
    eigenschaften: dict[str, Any] = {}
    if einleitung:
        eigenschaften["einleitung"] = {"type": "array", "items": _BELEGT}
    if fragen:
        eigenschaften["fragen"] = {"type": "array", "minItems": 1, "maxItems": fragen, "items": {
            "type": "object", "additionalProperties": False, "required": ["frage", "antwort", "belege"],
            "properties": {"frage": {"type": "string"}, "antwort": {"type": "string"},
                           "belege": {"type": "array", "items": {"type": "integer"}}}}}
    if glossar:
        eigenschaften["glossar"] = {"type": "array", "maxItems": GLOSSAR_HOECHSTENS, "items": {
            "type": "object", "additionalProperties": False, "required": ["begriff", "erklaerung"],
            "properties": {"begriff": {"type": "string"}, "erklaerung": {"type": "string"}}}}
    return antwortform("kapitelteile", {"type": "object", "additionalProperties": False, "required": list(eigenschaften),
                                        "properties": eigenschaften})


def kapitel_eingabe(titel: str, artikel: list[tuple[str, list[Absatz]]], hoechstens: int = KAPITEL_ZEICHEN) -> str:
    """Das umgeformte Kapitel: je Artikel A1, A2 ... mit seinen Absätzen, gekürzt auf `hoechstens` Zeichen."""
    zeilen, laenge = [f"Kapitel: {titel}"], 0
    for i, (name, absaetze) in enumerate(artikel, 1):
        zeilen.append(f"\nA{i}: {name}")
        for a in absaetze:
            text = a.text or a.html
            if laenge + len(text) > hoechstens:
                break
            zeilen.append(text)
            laenge += len(text)
    return "\n".join(zeilen)


def kapitelteile_lesen(roh: dict[str, Any], artikel: int, fragen: int) -> tuple[list[Belegt], list[Frage], list[Glossareintrag]]:
    erlaubt = set(range(1, artikel + 1))
    einleitung = _punkte(roh.get("einleitung"), erlaubt, 6)
    fr = []
    for f in roh.get("fragen") or []:
        if isinstance(f, dict) and (frage := _text(f.get("frage"), 400)) and (antwort := _text(f.get("antwort"), 800)):
            fr.append(Frage(frage=frage, antwort=antwort, belege=_zahlen(f.get("belege"), erlaubt)))
    glossar = []
    for g in roh.get("glossar") or []:
        if isinstance(g, dict) and (begriff := _text(g.get("begriff"), 80)) and (erklaerung := _text(g.get("erklaerung"), 400)):
            glossar.append(Glossareintrag(begriff=begriff, erklaerung=erklaerung))
    return einleitung, fr[:fragen], glossar[:GLOSSAR_HOECHSTENS]


# ----- Neuschreiben eines Absatzes (Probekapitel) ------------------------------------------------------------------------

NEU_AUFGABE = ("Schreibe den Absatz neu, nur aus den angegebenen Absätzen des Originals. Die markierten Sätze stehen so nicht "
               "im Original: lass sie weg oder schreibe sie so, dass jede Aussage im Original steht. Antworte nur mit JSON: "
               "{\"text\": \"...\", \"belege\": [1]}.")
NEU_FORM = antwortform("absatz", _BELEGT)


def neu_eingabe(absatz: Absatz, quellen: list[Quellblock]) -> str:
    markiert = "\n".join(f"- {s}" for s in absatz.ohne_beleg) or "- (keine)"
    return (f"Absatz:\n{absatz.text}\n\nMarkierte Sätze:\n{markiert}\n\nOriginal:\n{als_eingabe(quellen)}")


def neu_lesen(roh: dict[str, Any], alt: Absatz, erlaubt: set[int]) -> Absatz:
    text = _text(roh.get("text"))
    if not text:
        raise ValueError("Die Antwort enthält keinen Text")
    return alt.model_copy(update={"text": text, "belege": _zahlen(roh.get("belege"), erlaubt) or alt.belege, "ohne_beleg": []})


def als_json(daten: Any) -> str:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True)
