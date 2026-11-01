"""Probebetrieb am Mac: Nachschlag mit nachgestellter Kellerwolke (wie in den Tests), damit sich die Oberfläche ohne
echte Konten entwickeln und prüfen lässt. Einrichten einmal vom Mac aus (Adresse und
Schlüssel sind nur Platzhalter), anmelden mit Kennung `probe` und Passwort `probe`. Bücher aus `NACHSCHLAG_BUECHER_ORDNER`, Daten in `NACHSCHLAG_DATEN` (Vorgabe: daten-probe/ im Repo, nie im Git).

    NACHSCHLAG_BUECHER_ORDNER=/pfad/zu/zims .venv/bin/uvicorn probebetrieb:app --port 8711
    curl -X POST localhost:8711/api/v1/einrichtung -H 'Content-Type: application/json' \
         -d '{"kellerwolke_adresse": "http://kellerwolke.probe", "kellerwolke_schluessel": "kw_app_probe"}'
"""

import json
import os
from pathlib import Path

import httpx

from app.fassung import WURZEL
from app.main import app_bauen

KONTO = {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True}
SITZUNG = "probe-sitzung"


def kellerwolke(request: httpx.Request) -> httpx.Response:
    pfad = request.url.path
    if pfad == "/api/v1/ablage/ich":
        return httpx.Response(200, json={"app": "Nachschlag", "konto": "probe", "rechte": []})
    if pfad == "/api/v1/auth/login":
        eingabe = json.loads(request.content)
        if (eingabe.get("kennung"), eingabe.get("passwort")) != ("probe", "probe"):
            return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
        return httpx.Response(200, json={"token": SITZUNG, "benutzer": KONTO})
    if pfad == "/api/v1/auth/status":
        ok = request.headers.get("x-kellerwolke-sitzung") == SITZUNG
        return httpx.Response(200, json={"angemeldet": ok, "benutzer": KONTO if ok else None})
    if pfad == "/api/v1/auth/logout":
        return httpx.Response(204)
    return httpx.Response(404, json={"detail": "im Probebetrieb nicht nachgestellt"})


daten = Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten-probe")
app = app_bauen(daten, transport=httpx.MockTransport(kellerwolke))
