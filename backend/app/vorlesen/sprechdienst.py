"""Vorlesen über den Sprechdienst der Leitstelle (WIKI-43): der Text an Satzgrenzen geteilt (`appkern.saetze`), jeder
Satz vom Sprechdienst gesprochen (Vorgabe klangwerk-sprechen, `POST /v1/audio/speech`, WAV) und als Zeile eines Stroms
geliefert, sobald er da ist; so beginnt die Wiedergabe nach dem ersten Satz. Das Modell läuft im Klangwerk hinter der
Leitstelle; Nachschlag wählt nur Dienst, Stimme (aus dem Katalog des Dienstes) und die Sprache des Texts. Alle Sätze
einer Vorlesung sind bei der Leitstelle eine Arbeit (das Modell bleibt dafür stehen).

Der Strom ist NDJSON, wie ihn der Vorleser der Oberfläche liest: je Zeile `art` satz (mit `nr`, `text`, `dauer_ms` und
dem Ton als Base64-WAV in `ton`), zuletzt ende, oder fehler, wenn es nach dem ersten Satz scheitert."""

from __future__ import annotations

import base64
import io
import json
import time
import uuid
import wave
from collections.abc import AsyncIterator, Callable

from appkern.leitstelle import Leitstelle, LeitstellenFehler
from appkern.leitstelle.arbeit import LAUFENDE_ARBEIT
from appkern.saetze import hat_worte, saetze, stuecke

#: so lange gilt der geholte Katalog der Stimmen
KATALOG_GILT_S = 600
#: Sprache des Texts (Kennzeichen wie im HTML) in der Schreibweise des Sprechmodells; sonst die Vorgabe des Dienstes
SPRACHEN = {"de": "german", "en": "english", "fr": "french", "es": "spanish", "it": "italian", "pt": "portuguese",
            "ru": "russian", "ja": "japanese", "ko": "korean", "zh": "chinese"}


class NichtBereit(Exception):
    """Vorlesen geht gerade nicht (ohne Leitstelle, ohne Dienst, nicht freigegeben, Dienst antwortet nicht), bevor
    etwas gesprochen ist; `status` für die Antwort (nie 401, sonst meldete die Oberfläche die Person ab)."""

    def __init__(self, meldung: str, status: int = 503) -> None:
        super().__init__(meldung)
        self.meldung, self.status = meldung, status


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
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self._ls, self._dienst, self._stimme, self._uhr = leitstelle, dienst, stimme, uhr
        self._katalog: tuple[float, str, list[str]] | None = None

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

    async def katalog(self) -> list[str]:
        """Die Stimmen des Sprechdienstes (`GET /tts/voices`), eine Weile gemerkt."""
        dienst = self._dienst()
        if self._katalog and self._katalog[1] == dienst and self._uhr() - self._katalog[0] < KATALOG_GILT_S:
            return self._katalog[2]
        antwort = await self._leitstelle().dienst(dienst).json("GET", "/tts/voices", titel="Stimmen des Katalogs")
        stimmen = sorted(str(s) for s in antwort.get("speakers") or [])
        self._katalog = (self._uhr(), dienst, stimmen)
        return stimmen

    async def _sprechen(self, ls: Leitstelle, text: str, sprache: str, arbeit: str) -> bytes:
        marke = LAUFENDE_ARBEIT.set(arbeit)
        try:
            stimme = self._stimme()
            antwort = await ls.dienst(self._dienst()).anfrage(
                "POST", "/v1/audio/speech", titel="Vorlesen", prioritaet="hoch",
                json={"input": text, "response_format": "wav", **({"voice": stimme} if stimme else {}),
                      **({"language": SPRACHEN[sprache]} if sprache in SPRACHEN else {})})
        finally:
            LAUFENDE_ARBEIT.reset(marke)
        return antwort.content

    async def zeilen(self, text: str, sprache: str) -> AsyncIterator[bytes]:
        """Die Zeilen des Stroms für `text`. Scheitert es vor dem ersten Satz: `NichtBereit`; danach eine Zeile
        `fehler`. Bricht der Leser ab, wird kein weiterer Satz bestellt."""
        ls = self._leitstelle()
        arbeit = f"vorlesen-{uuid.uuid4().hex[:12]}"
        nr, gesamt = 0, 0
        try:
            for satz in saetze(text):
                for stueck in stuecke(satz.text):
                    if not hat_worte(stueck):
                        continue
                    wav = await self._sprechen(ls, stueck, sprache, arbeit)
                    ms = dauer_ms(wav)
                    yield zeile({"art": "satz", "nr": nr, "text": stueck, "dauer_ms": ms,
                                 "ton": base64.b64encode(wav).decode("ascii")})
                    nr += 1
                    gesamt += ms
        except LeitstellenFehler as f:
            if not nr:
                raise NichtBereit(f"Vorlesen gerade nicht möglich: {f}", 403 if f.status in (401, 403) else 503) from f
            yield zeile({"art": "fehler", "meldung": f"Vorlesen brach ab: {f}"})
            return
        yield zeile({"art": "ende", "saetze": nr, "dauer_ms": gesamt})
