"""Vorlesen über den Sprechdienst der Leitstelle (WIKI-43): der Text an Satzgrenzen geteilt (`appkern.saetze`), jeder
Satz vom Sprechdienst gesprochen (Vorgabe klangwerk-sprechen, `POST /v1/audio/speech`, WAV) und als Zeile eines Stroms
geliefert, sobald er da ist; so beginnt die Wiedergabe nach dem ersten Satz. Das Modell läuft im Klangwerk hinter der
Leitstelle; Nachschlag wählt nur Dienst, Stimme und die Sprache des Texts. Eine eigene Stimme (etwa die Hausstimme)
spricht der Klondienst der Leitstelle (Vorgabe klangwerk-klonen, `POST /tts/clone`) mit ihrer Probe aus der Vertonung
(stimmen.py); eine Stimme aus dem Katalog der Sprechdienst. Alle Sätze einer Vorlesung sind bei der Leitstelle eine
Arbeit (das Modell bleibt dafür stehen).

Der Strom ist NDJSON, wie ihn der Vorleser der Oberfläche liest: je Zeile `art` satz (mit `nr`, `text`, `dauer_ms` und
dem Ton als Base64-WAV in `ton`), zuletzt ende, oder fehler, wenn es nach dem ersten Satz scheitert."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import uuid
import wave
from collections.abc import AsyncIterator, Callable

from appkern.leitstelle import Leitstelle, LeitstellenFehler, Prioritaet
from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from appkern.saetze import hat_worte, saetze, stuecke
from appkern.verbund import VerbundFehler

from .stimmen import PRIVAT, NichtFreigegeben, Referenz, Stimmenquelle

#: so lange gilt der geholte Katalog der Stimmen
KATALOG_GILT_S = 600
#: so viele Sätze sind zugleich beim Sprechdienst in Arbeit (WIKI-104): der nächste ist schon unterwegs, während der
#: vorige noch klingt; die Reihenfolge bleibt die des Texts
VORAUS = 3
#: Sprache des Texts (Kennzeichen wie im HTML) in der Schreibweise des Sprechmodells; sonst die Vorgabe des Dienstes
SPRACHEN = {"de": "german", "en": "english", "fr": "french", "es": "spanish", "it": "italian", "pt": "portuguese",
            "ru": "russian", "ja": "japanese", "ko": "korean", "zh": "chinese"}


class NichtBereit(Exception):
    """Vorlesen geht gerade nicht (ohne Leitstelle, ohne Dienst, nicht freigegeben, Dienst antwortet nicht), bevor
    etwas gesprochen ist; `status` für die Antwort (nie 401, sonst meldete die Oberfläche die Person ab)."""

    def __init__(self, meldung: str, status: int = 503) -> None:
        super().__init__(meldung)
        self.meldung, self.status = meldung, status


def modus(referenz: Referenz, sprache: str) -> str:
    """Wie eine eigene Stimme spricht: mit Referenztext (icl) übernimmt das Modell Klang und Sprechweise der Probe;
    spricht sie eine andere Sprache als ihre Probe, brächte das deren Akzent mit, dann nur der Stimmabdruck (wie die
    App Vorlesen)."""
    return "icl" if referenz.text.strip() and sprache == referenz.sprache else "abdruck"


def dauer_ms(wav: bytes) -> int:
    """Länge einer WAV in Millisekunden; 0, wenn der Kopf nicht lesbar ist."""
    try:
        with wave.open(io.BytesIO(wav)) as w:
            return round(w.getnframes() * 1000 / w.getframerate())
    except (wave.Error, EOFError, ZeroDivisionError):
        return 0


def zeile(daten: dict) -> bytes:
    return json.dumps(daten, ensure_ascii=False).encode() + b"\n"


class Sprechdienst:
    def __init__(self, leitstelle: Callable[[], Leitstelle | None], dienst: Callable[[], str], stimme: Callable[[], str],
                 klondienst: Callable[[], str] = lambda: "klangwerk-klonen", stimmen: Stimmenquelle | None = None,
                 uhr: Callable[[], float] = time.monotonic, prioritaet: Prioritaet | None = None) -> None:
        """`prioritaet`: nur für Arbeit, die selbst einen Vorrang hat (Vertonen über Nacht: Hintergrund); sonst gilt der
        Vorrang für Vorlesen aus den Einstellungen (Vorgabe des Dienstes, WIKI-100)."""
        self._ls, self._dienst, self._stimme, self._uhr = leitstelle, dienst, stimme, uhr
        self._prioritaet = prioritaet
        self._klondienst, self.stimmen = klondienst, stimmen
        self._katalog: tuple[float, str, list[str]] | None = None

    def _eigene_id(self) -> str:
        """Kennung der gewählten eigenen Stimme, leer bei einer Stimme aus dem Katalog."""
        stimme = self._stimme()
        return stimme.removeprefix(PRIVAT) if stimme.startswith(PRIVAT) else ""

    def _leitstelle(self) -> Leitstelle:
        ls = self._ls()
        if ls is None:
            raise NichtBereit("Leitstelle nicht eingerichtet (Einstellungen, Verbindungen)")
        if not self._dienst():
            raise NichtBereit("Kein Sprechdienst eingestellt (Einstellungen, Vorlesen)")
        return ls

    async def pruefen(self) -> None:
        """`NichtBereit` mit Grund, wenn Vorlesen gerade nicht geht: Leitstelle und Dienst eingestellt, und die Leitstelle
        gibt den Dienst für Nachschlag frei."""
        ls = self._leitstelle()
        try:
            namen = {d.kennung for d in await ls.dienste()}
        except LeitstellenFehler as f:
            raise NichtBereit(f"Leitstelle antwortet nicht: {f}") from f
        if self._dienst() not in namen:
            raise NichtBereit(f"Die Leitstelle gibt den Sprechdienst {self._dienst()} für Nachschlag nicht frei", 403)
        if self._eigene_id() and self._klondienst() not in namen:
            raise NichtBereit(f"Die Leitstelle gibt den Klondienst {self._klondienst()} für Nachschlag nicht frei", 403)

    async def katalog(self) -> list[str]:
        """Die Stimmen des Sprechdienstes (`GET /tts/voices`), eine Weile gemerkt."""
        dienst = self._dienst()
        if self._katalog and self._katalog[1] == dienst and self._uhr() - self._katalog[0] < KATALOG_GILT_S:
            return self._katalog[2]
        antwort = await self._leitstelle().dienst(dienst).json("GET", "/tts/voices", titel="Stimmen des Katalogs")
        stimmen = sorted(str(s) for s in antwort.get("speakers") or [])
        self._katalog = (self._uhr(), dienst, stimmen)
        return stimmen

    async def _sprechen(self, ls: Leitstelle, text: str, sprache: str, arbeit: str, referenz: Referenz | None) -> bytes:
        if referenz is not None:
            return await self._klonen(ls, text, sprache, arbeit, referenz)
        marke = LAUFENDE_ARBEIT.set(arbeit)
        try:
            stimme = self._stimme()
            antwort = await ls.dienst(self._dienst()).anfrage(
                "POST", "/v1/audio/speech", titel="Vorlesen", prioritaet=self._prioritaet,
                json={"input": text, "response_format": "wav", **({"voice": stimme} if stimme else {}),
                      **({"language": SPRACHEN[sprache]} if sprache in SPRACHEN else {})})
        finally:
            LAUFENDE_ARBEIT.reset(marke)
        return antwort.content

    async def _klonen(self, ls: Leitstelle, text: str, sprache: str, arbeit: str, referenz: Referenz) -> bytes:
        """Ein Stück Text mit einer eigenen Stimme als WAV; die Probe geht mit, die Datei liegt bei der Instanz, die
        gesprochen hat."""
        marke = LAUFENDE_ARBEIT.set(arbeit)
        try:
            dienst = ls.dienst(self._klondienst())
            async with dienst.gebunden():
                antwort = await dienst.json(
                    "POST", "/tts/clone", titel="Vorlesen", prioritaet=self._prioritaet,
                    data={"text": text, "ref_text": referenz.text, "language": SPRACHEN.get(sprache, "german"),
                          "modus": modus(referenz, sprache)},
                    files={"ref_audio": ("referenz.wav", referenz.ton, "audio/wav")})
                return (await dienst.anfrage("GET", f"/tts/audio/{antwort['filename']}", titel="Vorlesen")).content
        finally:
            LAUFENDE_ARBEIT.reset(marke)

    async def zeilen(self, text: str, sprache: str) -> AsyncIterator[bytes]:
        """Die Zeilen des Stroms für `text`. Scheitert es vor dem ersten Satz: `NichtBereit`; danach eine Zeile
        `fehler`. Mit dem ersten Satz kommt vorab der Plan (Zahl der Sätze und Zeichen), damit der Vorleser seinen
        Puffer nach der Länge des Rests bemisst (WIKI-104). Bis zu VORAUS Sätze sind zugleich in Arbeit; bricht der
        Leser ab, werden die bestellten zurückgenommen und keine weiteren bestellt."""
        ls = self._leitstelle()
        referenz = None
        if eigene := self._eigene_id():
            if self.stimmen is None:
                raise NichtBereit("Eigene Stimmen gibt es erst mit der Adresse der Vertonung (Einstellungen, Vorlesen)")
            try:
                referenz = await self.stimmen.referenz(eigene)
            except NichtFreigegeben as f:
                raise NichtBereit(f.meldung, 403) from f
            except VerbundFehler as f:
                raise NichtBereit(f"Die Vertonung mit den eigenen Stimmen antwortet nicht: {f.meldung}") from f
        arbeit = f"vorlesen-{uuid.uuid4().hex[:12]}"
        teile = [s for satz in saetze(text) for s in stuecke(satz.text) if hat_worte(s)]
        bestellt: dict[int, asyncio.Task[bytes]] = {}

        def bestellen(i: int) -> None:
            if i < len(teile) and i not in bestellt:
                aufgabe = asyncio.create_task(self._sprechen(ls, teile[i], sprache, arbeit, referenz))
                aufgabe.add_done_callback(lambda a: a.cancelled() or a.exception())   # abgeholt, auch zurückgenommen
                bestellt[i] = aufgabe

        nr, gesamt = 0, 0
        try:
            for i in range(VORAUS):
                bestellen(i)
            for i, stueck in enumerate(teile):
                try:
                    wav = await bestellt.pop(i)
                except LeitstellenFehler as f:
                    if not nr:
                        raise NichtBereit(f"Vorlesen gerade nicht möglich: {f}", 403 if f.status in (401, 403) else 503) from f
                    yield zeile({"art": "fehler", "meldung": f"Vorlesen brach ab: {f}"})
                    return
                bestellen(i + VORAUS)
                if i == 0:
                    yield zeile({"art": "plan", "saetze": len(teile), "zeichen": sum(len(t) for t in teile)})
                ms = dauer_ms(wav)
                yield zeile({"art": "satz", "nr": nr, "text": stueck, "dauer_ms": ms,
                             "ton": base64.b64encode(wav).decode("ascii")})
                nr += 1
                gesamt += ms
        finally:
            for aufgabe in bestellt.values():
                aufgabe.cancel()
        yield zeile({"art": "ende", "saetze": nr, "dauer_ms": gesamt})
