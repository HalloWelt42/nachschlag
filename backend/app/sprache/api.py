"""Spracheingabe (WIKI-42, docs/SUCHE.md Punkt 8): ein Stück Ton aus der Aufnahme des Appkerns (Feld "datei", an
Sprechpausen geschnitten) wird über den Hördienst der Leitstelle zu Text. Die Live-Mitschrift der Oberfläche schickt
die Stücke nacheinander; die Antwort {text} hängt sie an. Der Ton bleibt nicht liegen."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from appkern.app import Geruest
from appkern.leitstelle import LeitstellenFehler, hoeren

#: Größtes Stück (die Aufnahme schneidet nach höchstens 15 s, 16 kHz WAV sind rund 0,5 MB)
HOECHSTENS = 8 << 20


class Gehoert(BaseModel):
    text: str


class Sprachstand(BaseModel):
    bereit: bool
    grund: str = ""


def router(geruest: Geruest, dienst: Callable[[], str]) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["sprache"], dependencies=[geruest.pflicht])

    @r.get("/sprache", response_model=Sprachstand)
    async def stand() -> Sprachstand:
        """Ob die Spracheingabe gerade geht: Leitstelle da, Hördienst eingestellt und für Nachschlag freigegeben. Die
        Oberfläche zeigt das Mikrofon nur dann (nur zeigen, was geht)."""
        leitstelle = geruest.leitstelle
        if leitstelle is None:
            return Sprachstand(bereit=False, grund="Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        if not dienst():
            return Sprachstand(bereit=False, grund="Kein Hördienst eingestellt (Einstellungen, Suche)")
        try:
            namen = {d.kennung for d in await leitstelle.dienste()}
        except LeitstellenFehler as f:
            return Sprachstand(bereit=False, grund=f"Leitstelle antwortet nicht: {f}")
        if dienst() not in namen:
            return Sprachstand(bereit=False, grund=f"Die Leitstelle gibt den Hördienst {dienst()} für Nachschlag nicht frei")
        return Sprachstand(bereit=True)

    @r.post("/sprache", response_model=Gehoert)
    async def sprache(datei: UploadFile) -> Gehoert:
        """Ein Stück Ton zu Text (Sprache erkennt der Hördienst selbst: Fragen mischen Deutsch und Fachwörter)."""
        leitstelle = geruest.leitstelle
        if leitstelle is None:
            raise HTTPException(503, "Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        if not dienst():
            raise HTTPException(503, "Kein Hördienst eingestellt (Einstellungen, Suche)")
        inhalt = await datei.read(HOECHSTENS + 1)
        if len(inhalt) > HOECHSTENS:
            raise HTTPException(413, "Stück zu lang")
        endung = Path(datei.filename or "sprache.wav").suffix or ".wav"
        with tempfile.TemporaryDirectory() as ordner:
            pfad = Path(ordner) / f"sprache{endung}"
            pfad.write_bytes(inhalt)
            try:
                gehoert = await hoeren(leitstelle, dienst(), pfad, "auto", titel="Spracheingabe", prioritaet="hoch")
            except LeitstellenFehler as f:
                raise HTTPException(503, f"Hören gerade nicht möglich: {f}") from f
        return Gehoert(text=gehoert.text)

    return r
