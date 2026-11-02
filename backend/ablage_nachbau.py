"""Nachgestellte Ablage der Kellerwolke für die Tests und den Probebetrieb, nur im Speicher: Ordner und Dateien mit
ihrem Pfad. Sie kann, was Nachschlag braucht (Bilder an Notizen, WIKI-51): Ordner anlegen, Datei schreiben, Knoten
über den Pfad finden, lesen und löschen; ein gelöschter Ordner nimmt seinen Inhalt mit (wie der Papierkorb)."""

from __future__ import annotations

import json
import re
import uuid

import httpx

ZEIT = "2026-11-02T12:00:00Z"


class Ablage:
    def __init__(self) -> None:
        #: Kennung -> (Pfad, Inhalt); Ordner haben keinen Inhalt
        self.knoten: dict[str, tuple[str, bytes | None]] = {}

    def unter(self, pfad: str) -> dict[str, str]:
        """Der Knoten unter diesem Pfad und alles darunter: Kennung -> Pfad."""
        return {k: p for k, (p, _) in self.knoten.items() if p == pfad or p.startswith(f"{pfad}/")}

    def antwort(self, request: httpx.Request) -> httpx.Response | None:
        """Antwort auf eine Anfrage an die Ablage; None, wenn sie nicht der Ablage gilt."""
        pfad = request.url.path
        if pfad == "/api/v1/ablage/ordner":
            ziel = json.loads(request.content)["pfad"]
            return self._json(self._finden(ziel) or self._anlegen(ziel, None))
        if pfad == "/api/v1/ablage/datei" and request.method == "PUT":
            return self._json(self._anlegen(request.url.params["pfad"], request.content))
        if pfad == "/api/v1/ablage/pfad":
            kennung = self._finden(request.url.params["pfad"])
            return self._json(kennung) if kennung else self._fehlt()
        if (m := re.fullmatch(r"/api/v1/ablage/knoten/([0-9a-f-]+)(/inhalt)?", pfad)):
            kennung = m.group(1)
            if kennung not in self.knoten:
                return self._fehlt()
            if request.method == "DELETE":
                for k in self.unter(self.knoten[kennung][0]):
                    del self.knoten[k]
                return httpx.Response(204)
            return httpx.Response(200, content=self.knoten[kennung][1] or b"")
        return None

    def _anlegen(self, pfad: str, inhalt: bytes | None) -> str:
        kennung = str(uuid.uuid4())
        self.knoten[kennung] = (pfad, inhalt)
        return kennung

    def _finden(self, pfad: str) -> str | None:
        return next((k for k, (p, _) in self.knoten.items() if p == pfad), None)

    def _json(self, kennung: str) -> httpx.Response:
        pfad, inhalt = self.knoten[kennung]
        return httpx.Response(200, json={"id": kennung, "name": pfad.rsplit("/", 1)[-1], "pfad": pfad, "recht": "schreiben",
                                         "typ": "ordner" if inhalt is None else "datei",
                                         "erstellt_am": ZEIT, "geaendert_am": ZEIT})

    @staticmethod
    def _fehlt() -> httpx.Response:
        return httpx.Response(404, json={"detail": "gibt es nicht"})
