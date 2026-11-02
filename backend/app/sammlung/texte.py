"""Was die Stapelarbeit aus einem Artikel braucht (WIKI-44): der Lesetext als Absätze (wie beim Vorlesen: Überschriften
und Absätze, ohne Steckbrief, Code und Tabellen) und die Anweisungen fürs Zusammenfassen und die Lernfragen."""

from __future__ import annotations

import re

from lxml import html as lhtml

from appkern.leitstelle import antwortform

BLOECKE = ("h2", "h3", "h4", "p", "li", "dd", "blockquote")
OHNE = {"steckbrief", "beispiel", "beitrag-fuss", "schlagwoerter", "qa-stimmen", "signatur"}
#: so viel Text eines Artikels geht höchstens ans Modell (Zusammenfassung, Lernfragen)
HOECHSTENS_ZEICHEN = 16_000


def lesetext(html: str) -> str:
    """Überschriften und Absätze als Text, je Block eine Zeile; Code, Tabellen und Steckbrief bleiben weg."""
    if not html.strip():
        return ""
    wurzel = lhtml.fragment_fromstring(html, create_parent="div")
    zeilen = []
    for el in wurzel.iter(*BLOECKE):
        if any(a.tag in ("pre", "table") or OHNE & set((a.get("class") or "").split()) for a in el.iterancestors()):
            continue
        text = re.sub(r"\s+", " ", el.text_content()).strip()
        if text:
            zeilen.append(text)
    return "\n".join(zeilen)


ZUSAMMENFASSUNG = """Fasse den Artikel "{titel}" auf Deutsch in fünf bis acht Sätzen zusammen: sachlich, die Fachbegriffe korrekt,
Namen, Zahlen und Bezeichner unverändert, nur aus dem Text, ohne Wertung und ohne Einleitung wie "Der Artikel ...".
Antworte nur mit dem JSON-Objekt {{"text": "..."}}."""

UEBERBLICK = """Hier sind Zusammenfassungen der Artikel einer Sammlung zum Thema "{thema}". Schreibe auf Deutsch einen Überblick
in sechs bis zehn Sätzen: was die Artikel zusammen zeigen, wie sie zusammenhängen, was offen bleibt. Sachlich, nur aus den
Zusammenfassungen. Antworte nur mit dem JSON-Objekt {{"text": "..."}}."""

LERNFRAGEN = """Erstelle aus dem Artikel "{titel}" drei bis fünf Lernfragen auf Deutsch mit kurzen, richtigen Antworten zum
Wiederholen (Karteikarten). Frage nach dem Wesentlichen, nicht nach Nebensachen; Antworten nur aus dem Text, Fachbegriffe
korrekt, Namen, Zahlen und Bezeichner unverändert.
Antworte nur mit dem JSON-Objekt {{"karten": [{{"frage": "...", "antwort": "..."}}]}}."""

TEXTFORM = antwortform("text", {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"],
                                "additionalProperties": False})
KARTENFORM = antwortform("karten", {
    "type": "object", "additionalProperties": False, "required": ["karten"],
    "properties": {"karten": {"type": "array", "minItems": 1, "maxItems": 8, "items": {
        "type": "object", "additionalProperties": False, "required": ["frage", "antwort"],
        "properties": {"frage": {"type": "string"}, "antwort": {"type": "string"}}}}}})
