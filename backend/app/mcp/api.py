"""MCP über HTTP (Streamable HTTP, zustandslos): `POST /api/v1/mcp` nimmt eine JSON-RPC-Nachricht und antwortet mit
JSON. Unterstützt `initialize`, `ping`, `tools/list` und `tools/call`; Benachrichtigungen (ohne `id`) bekommen 202.
Eine falsche Eingabe eines Werkzeugs ist ein Ergebnis mit `isError` (die KI kann es verbessern), ein unbekanntes
Werkzeug oder eine unbekannte Methode ein JSON-RPC-Fehler. Angemeldet wie jeder Weg: Sitzung oder App-Schlüssel."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from appkern.app import Geruest

from .werkzeuge import Werkzeug

#: die Fassung des Protokolls, die dieser Weg spricht; fragt ein Client nach einer anderen, antwortet er mit dieser
PROTOKOLL = "2025-06-18"


def _fehler(nr: Any, code: int, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": nr, "error": {"code": code, "message": text}}


def router(geruest: Geruest, werkzeuge: list[Werkzeug]) -> APIRouter:
    r = APIRouter(prefix="/api/v1", tags=["mcp"], dependencies=[geruest.pflicht])
    nach_name = {w.name: w for w in werkzeuge}

    @r.post("/mcp", summary="MCP-Werkzeuge für KI (Suchen, Lesen, Bücher)")
    async def mcp(request: Request) -> Response:
        """Model Context Protocol über HTTP: eine KI fragt, welche Werkzeuge es gibt (`tools/list`), und ruft sie
        (`tools/call`): nachschlag_buecher, nachschlag_suchen, nachschlag_lesen. Eine JSON-RPC-Nachricht je Anfrage."""
        try:
            n = await request.json()
        except ValueError:
            return _antwort(_fehler(None, -32700, "Kein gültiges JSON"))
        if not isinstance(n, dict) or n.get("jsonrpc") != "2.0" or "method" not in n:
            return _antwort(_fehler(n.get("id") if isinstance(n, dict) else None, -32600, "Keine JSON-RPC-Nachricht"))
        if "id" not in n:
            return Response(status_code=202)                     # Benachrichtigung (etwa notifications/initialized)
        nr, methode, p = n["id"], n["method"], n.get("params") or {}
        if methode == "initialize":
            return _antwort({"jsonrpc": "2.0", "id": nr, "result": {
                "protocolVersion": PROTOKOLL, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": geruest.kennung, "title": geruest.name, "version": geruest.fassung},
                "instructions": "Erst nachschlag_buecher, dann nachschlag_suchen, dann nachschlag_lesen mit Buch und Pfad."}})
        if methode == "ping":
            return _antwort({"jsonrpc": "2.0", "id": nr, "result": {}})
        if methode == "tools/list":
            return _antwort({"jsonrpc": "2.0", "id": nr, "result": {"tools": [
                {"name": w.name, "description": w.beschreibung, "inputSchema": w.eingabe.model_json_schema()} for w in werkzeuge]}})
        if methode == "tools/call":
            w = nach_name.get(p.get("name", ""))
            if w is None:
                return _antwort(_fehler(nr, -32602, f"Unbekanntes Werkzeug: {p.get('name', '')}"))
            try:
                eingabe = w.eingabe.model_validate(p.get("arguments") or {})
            except ValidationError as f:
                return _antwort(_ergebnis(nr, "Eingabe ungültig: " + "; ".join(
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in f.errors()), fehler=True))
            return _antwort(_ergebnis(nr, await w.arbeit(eingabe)))
        return _antwort(_fehler(nr, -32601, f"Unbekannte Methode: {methode}"))

    return r


def _ergebnis(nr: Any, text: str, fehler: bool = False) -> dict:
    return {"jsonrpc": "2.0", "id": nr, "result": {"content": [{"type": "text", "text": text}], "isError": fehler}}


def _antwort(inhalt: dict) -> Response:
    return JSONResponse(inhalt)
