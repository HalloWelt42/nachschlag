"""Dauer und Umfang eines Buchs vor dem Bauen (WIKI-45). Grundlage ist das Tempo des Modells in Zeichen je Sekunde:
die Hausmessung über die Leitstelle (Qwen3 80B, rund 75 Zeichen je Sekunde, gemessen 08.11.2026), bis Nachschlag nach dem
ersten Auftrag selbst gemessen hat (je Modell, nach jedem Auftrag neu). Was das Modell schreibt, ergibt sich aus der Länge
des Originals und der gewählten Länge; Kästen, Einleitungen, Fragen und Glossar mit ihrer üblichen Länge. Reine Rechnung."""

from __future__ import annotations

from ..modell.alsbuch import Bestellung, Schaetzschritt, Schaetzung, Vorlage
from .umformung import FAKTOR, LAENGE_TEXT

HAUSMESSUNG_ZEICHEN_JE_S = 75.0
#: übliche Längen dessen, was das Modell neben dem Text schreibt (Zeichen)
BLICK_ZEICHEN = 450
KASTEN_ZEICHEN = 400
EINLEITUNG_ZEICHEN = 450
FRAGE_ZEICHEN = 260
GLOSSAR_ZEICHEN = 900
#: Satz: Grundzeit, je Seite und Format, je Bild (Lesen, Bilder holen, EPUB packen, PDF setzen)
SATZ_GRUND_S = 8.0
SATZ_JE_SEITE_S = 0.35
BILD_S = 0.2
#: Zeichen Text je Seite und Seiten je Bild und je Kapitelanfang (Schätzung des Umfangs)
ZEICHEN_JE_SEITE = {"a5": 1_700, "a4": 3_600, "a4_zwei": 1_700}
SEITEN_JE_BILD = 0.3
#: Seiten vor und hinter den Kapiteln (Titelseite, Inhalt, Quellen)
RAHMEN_SEITEN = 4


def _teile(v: Vorlage) -> set[str]:
    return {t.art for t in [*v.aufbau.vorn, *v.aufbau.innen, *v.aufbau.hinten]}


def schaetzen(artikel_zeichen: list[int], kapitel: int, bilder: int, v: Vorlage, b: Bestellung, tempo: float,
              gemessen: bool, modell: str) -> Schaetzung:
    """Schritte mit Dauer, Seiten und Summe; Beginn und Ende setzt der Dienst (Nachtfenster)."""
    teile = _teile(v)
    zeichen = sum(artikel_zeichen)
    n = len(artikel_zeichen)
    kaesten = sum(1 for t in v.aufbau.innen if t.art == "kasten")
    schritte: list[Schaetzschritt] = []
    text_im_buch = zeichen if "originaltext" in teile else 0
    if "umgeformt" in teile:
        geschrieben = zeichen * FAKTOR[b.laenge]
        text_im_buch = int(geschrieben)
        schritte.append(Schaetzschritt(titel=f"Artikel umformen, {LAENGE_TEXT[b.laenge]}", sekunden=geschrieben / tempo))
    beiwerk, namen = 0.0, []
    if "blick" in teile:
        beiwerk += n * BLICK_ZEICHEN
        namen.append("Auf einen Blick")
    if kaesten:
        beiwerk += n * kaesten * KASTEN_ZEICHEN
        namen.append("eigene Kästen")
    if "kapiteleinleitung" in teile:
        beiwerk += kapitel * EINLEITUNG_ZEICHEN
        namen.append("Einleitungen")
    if "fragen" in teile and b.fragen:
        beiwerk += kapitel * b.fragen * FRAGE_ZEICHEN
        namen.append("Fragen")
    if beiwerk:
        teil = f"{kapitel} Kapitel" if {"Einleitungen", "Fragen"} & set(namen) else f"{n} Artikel"
        schritte.append(Schaetzschritt(titel=f"{' und '.join(namen)}, {teil}", sekunden=beiwerk / tempo))
    if "glossar" in teile:
        beiwerk += kapitel * GLOSSAR_ZEICHEN
        schritte.append(Schaetzschritt(titel="Glossar", sekunden=kapitel * GLOSSAR_ZEICHEN / tempo))
    bilder_im_buch = bilder if b.bilder else 0
    seiten = int(RAHMEN_SEITEN + kapitel + (text_im_buch + beiwerk) / ZEICHEN_JE_SEITE[b.seiten]
                 + bilder_im_buch * SEITEN_JE_BILD + 0.999)
    formate = int(b.epub) + int(b.pdf)
    satz = SATZ_GRUND_S + seiten * SATZ_JE_SEITE_S * formate + bilder_im_buch * BILD_S
    pruefen = "Prüfen, " if "umgeformt" in teile or beiwerk else ""
    namen_satz = " und ".join(x for x, an in (("EPUB", b.epub), ("PDF", b.pdf)) if an)
    schritte.append(Schaetzschritt(titel=f"{pruefen}Satz {namen_satz}" + (", Bilder" if bilder_im_buch else ""), sekunden=satz))
    return Schaetzung(artikel=n, kapitel=kapitel, zeichen=zeichen, seiten=seiten, schritte=schritte,
                      sekunden=sum(s.sekunden for s in schritte), tempo=tempo, gemessen=gemessen, modell=modell)


def probe_sekunden(zeichen: int, v: Vorlage, b: Bestellung, tempo: float) -> float:
    """Dauer eines Probekapitels: das erste Stück des Artikels, seine Kästen und die Teile des Kapitels."""
    teile = _teile(v)
    geschrieben = zeichen * FAKTOR[b.laenge] if "umgeformt" in teile else 0
    geschrieben += BLICK_ZEICHEN if "blick" in teile else 0
    geschrieben += KASTEN_ZEICHEN * sum(1 for t in v.aufbau.innen if t.art == "kasten")
    geschrieben += EINLEITUNG_ZEICHEN if "kapiteleinleitung" in teile else 0
    geschrieben += b.fragen * FRAGE_ZEICHEN if "fragen" in teile else 0
    return geschrieben / tempo + 2.0
