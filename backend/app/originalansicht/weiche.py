"""Weiche zwischen den beiden Herkünften im selben Backend (WIKI-85)."""

from __future__ import annotations

from starlette.datastructures import URL
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .herkunft import PRAEFIX, Originalherkunft


class Herkunftsweiche:
    """Auf dem Port der Originalansicht gibt es nur die Originalseiten, auf jedem anderen Port nie: kein Skript eines
    Buchs läuft mit der Herkunft der App, und die App nie mit der Herkunft der Bücher (dort käme ein Buch an ihren
    Speicher und damit an die Anmeldung)."""

    def __init__(self, app: ASGIApp, herkunft: Originalherkunft) -> None:
        self._app = app
        self._herkunft = herkunft

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            original = self._herkunft.ist_original(URL(scope=scope))
            weg: str = scope["path"]
            if original != (weg == PRAEFIX or weg.startswith(PRAEFIX + "/")):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                hier = "nur Originalseiten der Bücher" if original else "keine Originalseiten (die haben einen eigenen Port)"
                await JSONResponse({"detail": f"Nicht gefunden: auf diesem Port gibt es {hier}"}, status_code=404)(scope, receive, send)
                return
        await self._app(scope, receive, send)
