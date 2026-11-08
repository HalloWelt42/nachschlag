"""Die Bildquelle: die Schnittstelle des Wikis (api.php) nennt zu bis zu 50 Dateien auf einmal Größe, Urheber, Lizenz und
die Adresse eines Vorschaubilds in der gewünschten Breite (aus Commons oder dem Wiki selbst); danach wird jedes Bild
einzeln geladen. Antwortet die Quelle mit 429 oder 503, ist das eine Drosselung (`Gedrosselt`, mit ihrer Wartezeit)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

#: so viele Dateien fragt eine Anfrage an die Schnittstelle höchstens ab (Grenze des Wikis)
JE_ANFRAGE = 50
#: größtes Bild, das geladen wird (ein Vorschaubild in 1920 Pixeln ist weit kleiner)
HOECHSTENS_BYTES = 40 << 20
_TAGS = re.compile(r"<[^>]+>")


class Abgelehnt(Exception):
    """Die Quelle sperrt den Absender (403, Regeln für Roboter): ohne Kontakt in der Kennung geht nichts."""


class Gedrosselt(Exception):
    def __init__(self, warten_s: float) -> None:
        super().__init__(f"Bildquelle drosselt, {warten_s:g} s warten")
        self.warten_s = warten_s


@dataclass(frozen=True)
class Datei:
    name: str
    adresse: str            # Vorschaubild in der gewünschten Breite (oder das Original, wenn es schmaler ist)
    breite: int
    hoehe: int
    original: int
    mime: str
    urheber: str
    lizenz: str
    lizenz_url: str
    seite_url: str


def _text(html: str) -> str:
    return " ".join(_TAGS.sub("", html or "").split())


def _wartezeit(antwort: httpx.Response, vorgabe: float = 60.0) -> float:
    try:
        return max(float(antwort.headers.get("retry-after", vorgabe)), 1.0)
    except ValueError:
        return vorgabe


class Bildquelle:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    def _pruefen(self, antwort: httpx.Response) -> None:
        if antwort.status_code in (429, 503):
            raise Gedrosselt(_wartezeit(antwort))
        if antwort.status_code == 403 and "robot policy" in antwort.text:
            raise Abgelehnt("Die Bildquelle lehnt den Absender ab: er braucht einen Kontakt (Webseite oder E-Mail)")
        antwort.raise_for_status()

    async def angaben(self, quelle: str, namen: list[str], breite: int, absender: str) -> dict[str, Datei | None]:
        """Je Name die Angaben; None für eine Datei, die es in der Quelle nicht (mehr) gibt."""
        aus: dict[str, Datei | None] = {n: None for n in namen}
        titel = {f"File:{n}": n for n in namen}
        antwort = await self._client.get(f"https://{quelle}/w/api.php", headers={"User-Agent": absender}, params={
            "action": "query", "format": "json", "formatversion": "2", "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(breite),
            "iiextmetadatafilter": "Artist|LicenseShortName|LicenseUrl", "titles": "|".join(titel)})
        self._pruefen(antwort)
        daten = antwort.json().get("query", {})
        # die Quelle schreibt Titel um (Leerzeichen, Namensraum in der Sprache des Wikis): zurück zum Namen der Anfrage
        umbenannt = {e["to"]: e["from"] for e in daten.get("normalized", [])}
        for seite in daten.get("pages", []):
            angefragt = umbenannt.get(seite.get("title", ""), seite.get("title", ""))
            name = titel.get(angefragt)
            info = (seite.get("imageinfo") or [None])[0]
            if name is None or not info:
                continue
            meta = info.get("extmetadata") or {}
            original = int(info.get("width") or 0)
            schmal = not info.get("thumburl") or original <= int(info.get("thumbwidth") or 0)
            aus[name] = Datei(name=name, adresse=info["url"] if schmal else info["thumburl"],
                              breite=original if schmal else int(info.get("thumbwidth") or 0),
                              hoehe=int(info.get("height") or 0) if schmal else int(info.get("thumbheight") or 0),
                              original=original, mime=info.get("thumbmime") or info.get("mime") or "image/jpeg",
                              urheber=_text(meta.get("Artist", {}).get("value", "")),
                              lizenz=_text(meta.get("LicenseShortName", {}).get("value", "")),
                              lizenz_url=meta.get("LicenseUrl", {}).get("value", ""),
                              seite_url=info.get("descriptionurl", ""))
        return aus

    async def laden(self, adresse: str, absender: str) -> bytes:
        teile, groesse = [], 0
        async with self._client.stream("GET", adresse, headers={"User-Agent": absender}) as antwort:
            if antwort.status_code == 403:
                await antwort.aread()                   # die Begründung steht im Text
            self._pruefen(antwort)
            async for stueck in antwort.aiter_bytes():
                groesse += len(stueck)
                if groesse > HOECHSTENS_BYTES:
                    raise ValueError(f"Bild größer als {HOECHSTENS_BYTES >> 20} MB")
                teile.append(stueck)
        return b"".join(teile)
