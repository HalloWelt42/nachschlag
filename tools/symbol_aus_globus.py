#!/usr/bin/env python3
"""Stellt das runde Motiv des Symbols frei (WIKI-3) und schreibt daraus frontend/public/symbol.svg, die einzige Quelle
für tools/symbole.py. Das Motiv ist eine Kugel: ausgeschnitten wird genau ihr Kreis mit weicher Kante (Leuchtrand
bleibt, Hintergrund, Lichtfäden außerhalb und die Spiegelfläche darunter fallen weg). Gesucht wird der Kreis, auf dem
der Leuchtrand innen hell gegen den dunkleren Hintergrund steht. Das Symbol bleibt freigestellt, ohne Grund (Nutzer
01.11.2026: "es sollte freigestellt bleiben", auch am Startbildschirm des iPhones).
    python3 tools/symbol_aus_globus.py gestaltung/globus-quelle.png
Braucht Pillow und numpy, nur auf dem Rechner, der die Bilder erzeugt.
"""

from __future__ import annotations

import base64
import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

WURZEL = Path(__file__).resolve().parent.parent
ZIEL = WURZEL / "frontend" / "public" / "symbol.svg"
EINGEBETTET = 512          # Kantenlänge des eingebetteten Motivs in Pixeln
ANTEIL = 0.96              # Durchmesser der Kugel am Symbol (ohne Grund füllt sie es fast ganz)
UEBERABTASTUNG = 4         # glatte Kante


def kreis_finden(grau: np.ndarray) -> tuple[int, int, int]:
    h, w = grau.shape
    winkel = np.linspace(0, 2 * np.pi, 720, endpoint=False)
    # unten (Spiegelfläche, Lichtfäden) nicht werten: 60 bis 120 Grad zeigen nach unten
    winkel = winkel[(winkel < np.radians(60)) | (winkel > np.radians(120))]
    bester = (-1.0, w // 2, h // 2, min(w, h) // 3)
    for cx in range(int(w * 0.45), int(w * 0.55), 2):
        for cy in range(int(h * 0.42), int(h * 0.55), 2):
            for r in range(int(min(w, h) * 0.36), int(min(w, h) * 0.45), 2):
                def ring(d: int) -> float:
                    xs = np.clip((cx + (r + d) * np.cos(winkel)).astype(int), 0, w - 1)
                    ys = np.clip((cy + (r + d) * np.sin(winkel)).astype(int), 0, h - 1)
                    return float(grau[ys, xs].mean())
                wert = ring(-6) - ring(8)
                if wert > bester[0]:
                    bester = (wert, cx, cy, r)
    return bester[1], bester[2], bester[3]


def freistellen(quelle: Path) -> Image.Image:
    bild = Image.open(quelle).convert("RGBA")
    cx, cy, r = kreis_finden(np.asarray(bild.convert("L")).astype(float))
    r += 2                                              # der Leuchtrand gehört zur Kugel
    seite = 2 * r
    ausschnitt = bild.crop((cx - r, cy - r, cx + r, cy + r))
    maske = Image.new("L", (seite * UEBERABTASTUNG,) * 2, 0)
    ImageDraw.Draw(maske).ellipse((0, 0, seite * UEBERABTASTUNG - 1, seite * UEBERABTASTUNG - 1), fill=255)
    ausschnitt.putalpha(maske.resize((seite, seite), Image.LANCZOS))
    print(f"Kugel bei ({cx}, {cy}), Halbmesser {r - 2}")
    return ausschnitt.resize((EINGEBETTET, EINGEBETTET), Image.LANCZOS)


def svg_schreiben(motiv: Image.Image) -> None:
    puffer = io.BytesIO()
    # Palette mit Durchsichtigkeit: ein Bruchteil der Größe, für ein Symbol nicht zu unterscheiden (favicon.svg ist dieselbe
    # Datei und wird mit jeder Seite geladen)
    motiv.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG).save(puffer, "PNG", optimize=True)
    daten = base64.b64encode(puffer.getvalue()).decode()
    groesse = 512 * ANTEIL
    rand = (512 - groesse) / 2
    ZIEL.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
        f'<image x="{rand:.1f}" y="{rand:.1f}" width="{groesse:.1f}" height="{groesse:.1f}" href="data:image/png;base64,{daten}"/></svg>\n',
        encoding="utf-8")
    print(f"{ZIEL.relative_to(WURZEL)} geschrieben ({ZIEL.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    svg_schreiben(freistellen(Path(sys.argv[1])))
