"""Hördateien der Stapelarbeit (WIKI-44): die Sätze des Sprechdienstes (WAV) zu einer Datei, als Opus oder MP3 (über
libsndfile, ohne eigenes Programm im Container). Zwischen den Sätzen eine kurze Pause, wie beim Vorlesen."""

from __future__ import annotations

import io
import wave
from typing import Literal

Format = Literal["opus", "mp3"]
#: Endung, Format und Unterart je Format
FORMATE: dict[str, tuple[str, str, str]] = {"opus": ("opus", "OGG", "OPUS"), "mp3": ("mp3", "MP3", "MPEG_LAYER_III")}
PAUSE_S = 0.35


def zusammenfuegen(saetze: list[bytes], format: Format) -> bytes:
    """Die Sätze (WAV, PCM 16 Bit, mono, gleiche Abtastrate) als eine Datei im gewählten Format. Die Tonbibliothek
    wird erst hier geladen: fehlt sie im Abbild, scheitert nur das Vertonen, nie der Start der App."""
    import numpy as np
    import soundfile as sf

    teile, rate = [], 0
    for wav in saetze:
        with wave.open(io.BytesIO(wav)) as w:
            rate = rate or w.getframerate()
            daten = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
        teile += [daten, np.zeros(int(rate * PAUSE_S), dtype="float32")]
    if not teile:
        return b""
    _, fmt, unterart = FORMATE[format]
    puffer = io.BytesIO()
    sf.write(puffer, np.concatenate(teile), rate, format=fmt, subtype=unterart)
    return puffer.getvalue()
