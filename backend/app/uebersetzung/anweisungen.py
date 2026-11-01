"""Anweisungen für das Übersetzen von Artikeln (WIKI-8), je Art des Buchs: was fachlich ist und unverändert bleibt,
welcher Ton gilt. An der Qualität wird je Art gefeilt, hier und nur hier."""

from __future__ import annotations

from ..modell.buch import Art

#: Ausgangssprachen (ISO 639-3): im Dativ für "aus dem ..." und als Kennzeichen für HTML (lang); Unbekanntes heißt
#: "aus dem Original" und bleibt ohne Kennzeichen
SPRACHEN = {"eng": ("Englischen", "en"), "fra": ("Französischen", "fr"), "spa": ("Spanischen", "es"),
            "ita": ("Italienischen", "it"), "nld": ("Niederländischen", "nl"), "por": ("Portugiesischen", "pt"),
            "rus": ("Russischen", "ru"), "pol": ("Polnischen", "pl")}

GRUND = """Du übersetzt Stücke eines Artikels aus einem Nachschlagewerk aus dem {sprache} ins Deutsche. Jedes Stück ist ein
Absatz, ein Listenpunkt, eine Überschrift oder eine Tabellenzelle desselben Artikels ("{titel}"), in der Reihenfolge des
Artikels.

Regeln für jedes Stück:
- Marken wie <t1>...</t1> umschließen ausgezeichneten Text (Verweis, Betonung). Übersetze den Text darin und behalte jede
  Marke genau so, mit derselben Nummer und derselben Schachtelung. Die Stellung im Satz darf sich ändern, wenn der deutsche
  Satz es verlangt.
- Platzhalter wie <x2/> stehen für Code, Formeln, Bilder oder Belegnummern. Übernimm jeden genau einmal an die passende
  Stelle.
- Zahlen, Jahreszahlen, Maße, Einheiten und Versionen bleiben unverändert. Nichts weglassen, nichts hinzufügen, nichts
  erklären.
- &lt; &gt; &amp; bleiben so geschrieben.
- Ist ein Stück schon deutsch oder nur ein Name, gib es unverändert zurück.
- Nur gerade Anführungszeichen (") und einfache Bindestriche (-).

{art}

Antworte nur mit dem JSON-Objekt {{"stuecke": [...]}}: genau {anzahl} übersetzte Stücke in derselben Reihenfolge."""

JE_ART: dict[str, str] = {
    "dokumentation": """Es ist die Dokumentation einer Programmiersprache oder eines Werkzeugs. Unverändert bleiben Namen von
Funktionen, Methoden, Klassen, Parametern, Konstanten, Typen (string, int, bool, array, callable, mixed), Schlüsselwörter
(true, false, null), Dateinamen, Optionen und Befehle. Verwende die üblichen deutschen Fachbegriffe der Programmierung
(callback: Callback-Funktion, return value: Rückgabewert, deprecated: veraltet, throws: wirft). Schreibe sachlich und
unpersönlich, ohne Anrede.""",
    "frage_antwort": """Es ist eine Frage oder Antwort aus einem Frage-und-Antwort-Forum zu Technik. Unverändert bleiben Befehle,
Tastenkürzel, Namen von Programmen, Optionen, Dateien, Funktionen und Personen. Behalte den Ton des Beitrags; wo der Beitrag
den Leser anspricht, mit du.""",
    "enzyklopaedie": """Es ist ein Artikel einer Enzyklopädie. Eigennamen stehen in der im Deutschen üblichen Form (München,
Peking), sonst unverändert; wissenschaftliche Namen (Gattung, Art) und Titel von Werken bleiben unverändert. Schreibe im
sachlichen Stil eines Lexikons.""",
}
SONST = "Schreibe sachlich; Fachbegriffe, Namen und Bezeichner bleiben unverändert."


def sprache_in_worten(kuerzel: str) -> str:
    """"Englischen" für "aus dem Englischen"; mehrere oder unbekannte Sprachen: "Original"."""
    return SPRACHEN.get(kuerzel.strip(), ("Original", ""))[0]


def html_sprache(kuerzel: str) -> str:
    return SPRACHEN.get(kuerzel.strip(), ("Original", ""))[1]


def anweisung(art: Art, sprache: str, titel: str, anzahl: int) -> str:
    return GRUND.format(sprache=sprache_in_worten(sprache), titel=titel, art=JE_ART.get(art, SONST), anzahl=anzahl)
