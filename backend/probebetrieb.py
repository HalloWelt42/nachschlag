"""Probebetrieb beim Entwickeln: Nachschlag mit nachgestellter Kellerwolke (wie in den Tests), damit sich die
Oberfläche ohne echte Konten entwickeln und prüfen lässt. Bücher aus `NACHSCHLAG_BUECHER_ORDNER`, Daten in
`NACHSCHLAG_DATEN` (Vorgabe: daten-probe/ im Repo, nie im Git).

Mit Anmeldung (wie ein Betrieb mit Kellerwolke): `NACHSCHLAG_ANMELDUNG=kellerwolke`, einmal einrichten (Adresse und
Schlüssel sind nur Platzhalter), anmelden mit Kennung `probe` und Passwort `probe`. Ohne diese Angabe beginnt ein frischer
Datenordner wie Nachschlag aus dem öffentlichen Repo ohne Anmeldung (WIKI-11); ein Datenordner, in dem schon eine
Kellerwolke eingetragen ist, bleibt mit Anmeldung. Die Originalseiten der Bücher kommen über einen zweiten Port
(`NACHSCHLAG_ORIGINAL_PORT`, Vorgabe 8712), auf dem derselbe Prozess mitlauscht (WIKI-85).

    NACHSCHLAG_ANMELDUNG=kellerwolke NACHSCHLAG_BUECHER_ORDNER=/pfad/zu/zims .venv/bin/uvicorn probebetrieb:app --port 8711
    curl -X POST localhost:8711/api/v1/einrichtung -H 'Content-Type: application/json' \
         -d '{"kellerwolke_adresse": "http://kellerwolke.probe", "kellerwolke_schluessel": "kw_app_probe"}'
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn

from ablage_nachbau import Ablage
from app.fassung import WURZEL
from app.main import app_bauen, original_port

KONTO = {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True}
SITZUNG = "probe-sitzung"
#: Ablage der nachgestellten Kellerwolke (nur im Speicher, weg nach dem Neustart)
ABLAGE = Ablage()


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
    # Ablage für Dateien der App (etwa Bilder an Notizen)
    if (antwort := ABLAGE.antwort(request)) is not None:
        return antwort
    return httpx.Response(404, json={"detail": "im Probebetrieb nicht nachgestellt"})


daten = Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten-probe")
ORIGINAL_PORT = original_port()
# der Bücherlader liest das echte Verzeichnis der Bücher (laden nur, was man im Probebetrieb abonniert)
app = app_bauen(daten, transport=httpx.MockTransport(kellerwolke), lader_transport=httpx.AsyncHTTPTransport(),
                original_port=ORIGINAL_PORT)

# Originalseiten auf eigener Herkunft (WIKI-85): im Betrieb reicht der Vorschaltdienst einen zweiten Port an die App,
# hier lauscht dieselbe App im selben Prozess zusätzlich auf diesem Port (nur 127.0.0.1)
_lebenslauf = app.router.lifespan_context


@asynccontextmanager
async def _mit_originalport(a):
    zweiter = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=ORIGINAL_PORT, lifespan="off", log_level="warning"))
    lauf = asyncio.create_task(zweiter.serve())
    try:
        async with _lebenslauf(a) as zustand:
            yield zustand
    finally:
        zweiter.should_exit = True
        await lauf

app.router.lifespan_context = _mit_originalport
