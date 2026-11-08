"""Katalog der Teile einer Vorlage (WIKI-45): je Teil Beschriftung, Herkunft und Ebene, an genau einer Stelle. Die
Oberfläche liest ihn über die Schnittstelle; der Aufbau einer Vorlage wird hier geprüft (welcher Teil wohin darf)."""

from __future__ import annotations

from ..modell.alsbuch import EINMALIG, KAESTEN_HOECHSTENS, Aufbau, Teilangabe

KATALOG: list[Teilangabe] = [
    Teilangabe(art="titelseite", titel="Titelseite mit Titelbild", herkunft="thema", ebene="buch",
               beschreibung="Titel des Themas, Untertitel der Vorlage und das Titelbild"),
    Teilangabe(art="inhalt", titel="Inhaltsverzeichnis", herkunft="selbst", ebene="buch",
               beschreibung="Kapitel und Artikel, im PDF mit Seitenzahlen"),
    Teilangabe(art="kapitel", titel="Je Bereich ein Kapitel", herkunft="thema", ebene="gliederung", wechsel="abc",
               beschreibung="Jeder Bereich des Themas wird ein Kapitel, in der Reihenfolge der Seite Als Buch"),
    Teilangabe(art="abc", titel="Von A bis Z, je Buchstabe ein Kapitel", herkunft="thema", ebene="gliederung", wechsel="kapitel",
               beschreibung="Alle Artikel nach dem Alphabet wie in einem Nachschlagewerk"),
    Teilangabe(art="kapiteleinleitung", titel="Einleitung des Kapitels", herkunft="ki", ebene="kapitel",
               beschreibung="Zwei bis vier Sätze, die ins Kapitel führen"),
    Teilangabe(art="blick", titel="Je Artikel: Auf einen Blick", herkunft="ki", ebene="artikel",
               beschreibung="Die Kernaussagen in wenigen Punkten, je Punkt belegt"),
    Teilangabe(art="umgeformt", titel="Je Artikel: Text, umgeformt", herkunft="ki", ebene="artikel", wechsel="originaltext",
               beschreibung="Der Artikel nach Ton, Leserschaft und Länge der Vorlage, Beleg je Absatz"),
    Teilangabe(art="originaltext", titel="Je Artikel: Text wie im Buch", herkunft="buch", ebene="artikel", wechsel="umgeformt",
               beschreibung="Der Artikel unverändert, mit Listen und Tabellen"),
    Teilangabe(art="kasten", titel="Je Artikel: eigener Kasten", herkunft="ki", ebene="artikel",
               beschreibung="Ein Kasten mit eigener Überschrift; was hinein kommt, sagt die Anweisung des Kastens"),
    Teilangabe(art="notizen", titel="Meine Notizen als Randnotiz", herkunft="meins", ebene="artikel",
               beschreibung="Notizen zum Artikel; Notizen zu einer Stelle stehen an ihrer Stelle"),
    Teilangabe(art="fragen", titel="Fragen zum Kapitel", herkunft="ki", ebene="kapitel",
               beschreibung="Fragen zum Wiederholen mit Antwort (EPUB zum Aufklappen, PDF hinten im Kapitel)"),
    Teilangabe(art="glossar", titel="Glossar", herkunft="ki", ebene="buch",
               beschreibung="Fachbegriffe der Kapitel mit Erklärung, alphabetisch"),
    Teilangabe(art="literatur", titel="Literaturliste", herkunft="thema", ebene="buch",
               beschreibung="Je Artikel die Quellenangabe und die Belege aus den Notizen"),
]
JE_ART: dict[str, Teilangabe] = {t.art: t for t in KATALOG}


def braucht_ki(aufbau: Aufbau) -> bool:
    """Kommt mindestens ein Teil von der KI?"""
    return any(JE_ART[t.art].herkunft == "ki" for t in [*aufbau.vorn, *aufbau.innen, *aufbau.hinten])


def aufbau_pruefen(aufbau: Aufbau) -> None:
    """Jeder Teil an einem erlaubten Platz, Einmaliges nur einmal, eigene Kästen mit Überschrift und Anweisung;
    ValueError mit dem Grund in Worten."""
    plaetze = (("vorn", aufbau.vorn, {"buch"}), ("innen", aufbau.innen, {"kapitel", "artikel"}), ("hinten", aufbau.hinten, {"buch"}))
    gesehen: set[str] = set()
    kaesten = 0
    for platz, teile, ebenen in plaetze:
        for t in teile:
            angabe = JE_ART[t.art]
            if angabe.ebene not in ebenen:
                ort = {"vorn": "vor den Kapiteln", "innen": "im Kapitel", "hinten": "nach den Kapiteln"}[platz]
                raise ValueError(f"{angabe.titel} steht nicht {ort}")
            if t.art in EINMALIG:
                if t.art in gesehen or (t.art in ("umgeformt", "originaltext") and {"umgeformt", "originaltext"} & gesehen):
                    raise ValueError(f"{angabe.titel} steht nur einmal im Aufbau")
                gesehen.add(t.art)
            if t.art == "kasten":
                kaesten += 1
                if not (t.titel.strip() and t.anweisung.strip()):
                    raise ValueError("Ein eigener Kasten braucht Überschrift und Anweisung")
    if kaesten > KAESTEN_HOECHSTENS:
        raise ValueError(f"Höchstens {KAESTEN_HOECHSTENS} eigene Kästen")
