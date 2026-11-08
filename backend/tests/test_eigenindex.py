"""Eigener Index (WIKI-17): Aufbau mit Fortsetzen, Abfrage in Stufen, die Aufträge auf dem Pi mit ihrer Schnittstelle,
der Index-Dienst auf dem Mac (holt ab, baut, lädt hoch, wartet auf Netz und Pi) und die Suche darüber."""

from __future__ import annotations

import asyncio
import sqlite3
import sys
import threading
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402
from test_app import kellerwolke  # noqa: E402

from app.artikel import wege  # noqa: E402
from app.bibliothek import Bibliothek  # noqa: E402
from app.eigenindex import abfrage, aufbau, schema  # noqa: E402
from app.eigenindex.ablage import Eigenindizes  # noqa: E402
from app.indexdienst.arbeiter import Arbeiter  # noqa: E402
from app.main import app_bauen  # noqa: E402
from app.register import Register  # noqa: E402

DOKU = "probedoku_en_php_2026-08"
SCHLUESSEL = {"Authorization": "Bearer geheim"}


@pytest.fixture(scope="module")
def buecher(tmp_path_factory) -> Path:
    ordner = tmp_path_factory.mktemp("buecher")
    probebuch.bauen_doku(ordner)
    probebuch.bauen(ordner)
    return ordner


def _bauen(ordner: Path, kennung: str, ziel: Path, **weiter) -> aufbau.Stand:
    bib = Bibliothek(lambda: str(ordner))
    archiv, buch = bib.geoeffnet(kennung)
    return aufbau.bauen(archiv, buch, wege(bib), ziel, **weiter)


# ----- Index ------------------------------------------------------------------------------------------------------------

def test_aufbau_und_abfrage_in_stufen(buecher, tmp_path):
    ziel = tmp_path / schema.dateiname(DOKU)
    stand = _bauen(buecher, DOKU, ziel)
    assert stand.fertig and stand.seiten >= 2 and schema.gueltig(ziel)
    assert ziel.with_suffix(".sha256").read_text().strip() == aufbau.pruefsumme(ziel)

    funde, _ = abfrage.suchen(ziel, "array_map")                         # genauer Name zuerst
    assert funde[0].pfad == "function.array-map" and funde[0].stufe == "name"
    funde, _ = abfrage.suchen(ziel, "ARRAY_")                            # Wortanfang, ohne Groß und Klein
    assert {"function.array-map", "function.array-filter"} <= {f.pfad for f in funde}
    funde, gesamt = abfrage.suchen(ziel, "filters elements")             # Volltext, Ausschnitt aus dem Index
    assert funde[0].pfad == "function.array-filter" and funde[0].stufe == "volltext" and gesamt >= 1
    assert "<em>" in funde[0].ausschnitt and "<p" not in funde[0].ausschnitt
    assert abfrage.suchen(ziel, '"()*') == ([], 0)                       # nur Zeichen ohne Wort: nichts, kein Fehler
    assert abfrage.suchen(ziel, 'array_map "(') [0][0].pfad == "function.array-map"   # Zeichen der Abfragesprache stören nicht


def test_aufbau_setzt_nach_abbruch_fort(buecher, tmp_path):
    ziel = tmp_path / schema.dateiname("probe_de_all_2026-01")
    halb = _bauen(buecher, "probe_de_all_2026-01", ziel, stapel=1, abbrechen=lambda: True)
    assert not halb.fertig and not schema.gueltig(ziel)
    ganz = _bauen(buecher, "probe_de_all_2026-01", ziel, stapel=1)
    assert ganz.fertig and ganz.seiten > halb.seiten
    v = sqlite3.connect(ziel)
    assert v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0] == ganz.seiten
    assert v.execute("SELECT COUNT(*) FROM seiten WHERE pfad = 'Vulpes_vulpes'").fetchone()[0] == 0   # Sprungseite
    v.execute("UPDATE angaben SET wert = '0' WHERE schluessel = 'fassung'")
    v.commit()
    v.close()
    assert not schema.gueltig(ziel)                                      # alte Fassung des Schemas gilt nicht
    assert _bauen(buecher, "probe_de_all_2026-01", ziel).fertig and schema.gueltig(ziel)   # und wird neu gebaut


def test_ablage_sieht_austausch(buecher, tmp_path):
    ablage = Eigenindizes(lambda: str(tmp_path))
    assert ablage.datei(DOKU) is None
    neu = tmp_path / "neu.sqlite"
    _bauen(buecher, DOKU, neu)
    neu.replace(tmp_path / schema.dateiname(DOKU))
    assert ablage.datei(DOKU) == tmp_path / schema.dateiname(DOKU)
    assert Eigenindizes(lambda: "").datei(DOKU) is None                   # ohne Ordner kein eigener Index


async def test_register_und_trefferzahlen_frage_antwort(tmp_path):
    """Frage und Antwort (WIKI-39): nur Fragen kommen in den Index, mit Stimmen, Schlagwörtern und Autoren; daraus die
    Register über alle Bücher oder eines, und Treffer tragen die Zahlen der Frage."""
    qa = "probeqa_en_all_2026-10"
    buecher, ablage = tmp_path / "buecher", tmp_path / "pi"
    probebuch.bauen_qa(buecher)
    ablage.mkdir()
    reg = Register(Bibliothek(lambda: str(buecher)), Eigenindizes(lambda: str(ablage)))
    assert (await reg.schlagwoerter()).ohne_index == [qa]                     # Register entsteht erst mit dem Index
    ziel = ablage / schema.dateiname(qa)
    assert _bauen(buecher, qa, ziel).seiten == 1                               # Fragenliste und Nebenseiten zählen nicht

    s = await reg.schlagwoerter()
    assert [(e.wort, e.fragen, e.stimmen, e.buecher) for e in s.eintraege] == [("os-clipboard", 1, 520, [qa])] and not s.ohne_index
    assert (await reg.schlagwoerter(anfang="xyz")).eintraege == []
    f = (await reg.fragen("OS-Clipboard")).eintraege[0]
    assert (f.titel, f.stimmen, f.antworten, f.akzeptiert, f.gefragt, f.buch) == (
        "How can I copy text to the clipboard?", 520, 2, True, "03.02.2015", qa)
    a = await reg.autoren()
    assert {x.autor for x in a.eintraege} == {"thameera", "Martin Tournoij", "Quincy Bowers"} and a.gesamt == 3
    assert [x.autor for x in (await reg.autoren(anfang="mar")).eintraege] == ["Martin Tournoij"]
    seite = await reg.autor(qa, "8")                                           # thameera hat das Konto users/8
    assert (seite.autor.autor, seite.autor.fragen, seite.autor.von) == ("thameera", 1, "2015-02-03")
    assert seite.beitraege[0].art == "frage" and seite.beitraege[0].datum == "03.02.2015"
    martin = await reg.autor(qa, "15")
    assert martin.autor.akzeptiert == 1 and martin.beitraege[0].akzeptiert

    funde, _ = abfrage.suchen(ziel, "copy block text")
    assert funde[0].frage is not None and (funde[0].frage.stimmen, funde[0].frage.schlagwoerter) == (520, ["os-clipboard"])


# ----- Pi und Mac -------------------------------------------------------------------------------------------------------

class Bruecke(httpx.BaseTransport):
    """Synchroner Weg vom Index-Dienst (eigener Faden, wie auf dem Mac) zur App in der Ereignisschleife des Tests."""

    def __init__(self, app, schleife: asyncio.AbstractEventLoop) -> None:
        self._c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://pi.test")
        self._schleife = schleife

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        async def senden() -> httpx.Response:
            a = await self._c.send(self._c.build_request(request.method, request.url, headers=request.headers,
                                                         content=request.read()))
            return httpx.Response(a.status_code, headers=a.headers, content=a.content)
        return asyncio.run_coroutine_threadsafe(senden(), self._schleife).result(timeout=30)


@pytest.fixture
async def pi(tmp_path: Path, buecher: Path):
    """Nachschlag auf dem Pi mit Ordner und Schlüssel für eigene Indizes."""
    app = app_bauen(tmp_path / "daten", transport=httpx.MockTransport(kellerwolke))
    geruest = app.state.geruest
    await geruest.starten()
    await geruest.einstellungen.aendern({"buecher_ordner": str(buecher), "eigenindex_ordner": str(tmp_path / "pi"),
                                         "indexdienst_schluessel": "geheim"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
        token = (await c.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).json()["token"]
        c.headers["X-Kellerwolke-Sitzung"] = token
        yield c, app
    await geruest.stoppen()


async def _laeuft(c: httpx.AsyncClient) -> dict:
    for _ in range(200):
        a = (await c.get("/api/v1/auftraege")).json()["eintraege"]
        if a and a[0]["zustand"] == "laeuft":
            return a[0]
        await asyncio.sleep(0.02)
    raise AssertionError("kein Auftrag läuft")


async def _beendet(c: httpx.AsyncClient) -> dict:
    for _ in range(500):
        a = (await c.get("/api/v1/auftraege")).json()["eintraege"]
        if a and a[0]["zustand"] not in ("wartet", "laeuft"):
            return a[0]
        await asyncio.sleep(0.02)
    raise AssertionError("Auftrag endet nicht")


async def _abholen(mac: httpx.AsyncClient) -> dict:
    """Wie der Index-Dienst: fragen, bis die Arbeit des Auftrags bereitsteht (sie beginnt kurz nach "läuft")."""
    for _ in range(100):
        antwort = await mac.post("/api/v1/indexdienst/abholen")
        if antwort.status_code == 200:
            return antwort.json()
        await asyncio.sleep(0.02)
    raise AssertionError("nichts abzuholen")


async def test_mac_holt_ab_baut_und_uebergibt(pi, buecher, tmp_path):
    c, app = pi
    assert await app.state.indexauftraege.fehlende_einreihen() == [DOKU]    # nur die eingestellten Arten (Handbücher)
    assert await app.state.indexauftraege.fehlende_einreihen() == []        # kein zweiter Auftrag für dasselbe Buch
    laufend = await _laeuft(c)
    assert "wartet auf den Mac" in laufend["schritt"] or laufend["schritt"] == ""

    halt = threading.Event()
    mac = httpx.Client(transport=Bruecke(app, asyncio.get_running_loop()), base_url="http://pi.test", headers=SCHLUESSEL)
    arbeiter = Arbeiter(mac, buecher, tmp_path / "mac", ruhe_s=0.05, stueck=4096)       # kleine Stücke: viele Anfragen
    faden = threading.Thread(target=arbeiter.laufen, args=(halt,), daemon=True)
    faden.start()
    try:
        fertig = await _beendet(c)
    finally:
        halt.set()
        await asyncio.to_thread(faden.join, 10)
    assert fertig["zustand"] == "fertig", fertig
    assert schema.gueltig(tmp_path / "pi" / schema.dateiname(DOKU)) and not list((tmp_path / "pi").glob("*.teil"))
    verbindung = next(v for v in (await c.get("/api/v1/verbindungen")).json() if v["name"] == "Index-Dienst")
    assert verbindung["ok"]

    s = (await c.get("/api/v1/suche", params={"frage": "filters elements", "buecher": DOKU})).json()
    assert s["treffer"][0]["pfad"] == "function.array-filter" and "<em>" in s["treffer"][0]["ausschnitt"]
    s = (await c.get("/api/v1/suche", params={"frage": "array_map", "buecher": DOKU})).json()
    assert s["treffer"][0]["pfad"] == "function.array-map"


async def test_schnittstelle_schuetzt_und_setzt_fort(pi):
    c, app = pi
    mac = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://pi.test")
    assert (await mac.post("/api/v1/indexdienst/abholen")).status_code == 401
    assert (await mac.post("/api/v1/indexdienst/abholen", headers={"Authorization": "Bearer falsch"})).status_code == 401
    mac.headers.update(SCHLUESSEL)
    assert (await mac.post("/api/v1/indexdienst/abholen")).status_code == 204          # nichts offen
    assert (await c.post("/api/v1/indexdienst/abholen")).status_code == 401            # Anmeldung der Oberfläche zählt nicht

    await app.state.indexauftraege.fehlende_einreihen()
    auftrag = (await _laeuft(c))["id"]
    abholung = await _abholen(mac)
    assert abholung == {"auftrag": auftrag, "buch": DOKU, "da": 0, "vorlage": ""}         # keine frühere Fassung
    weg = f"/api/v1/indexdienst/{auftrag}"
    assert (await mac.put(f"{weg}/datei", params={"ab": 0, "gesamt": 10}, content=b"abcd")).json() == {"da": 4}
    assert (await mac.put(f"{weg}/datei", params={"ab": 2, "gesamt": 10}, content=b"xx")).status_code == 409
    assert (await mac.get(f"{weg}/datei")).json() == {"da": 4}
    assert (await mac.post("/api/v1/indexdienst/abholen")).json()["da"] == 4               # Übertragung setzt dort fort
    await mac.put(f"{weg}/stand", json={"zustand": "laeuft", "erledigt": 3, "gesamt": 6, "seiten": 2})
    await asyncio.sleep(2.1)
    assert (await c.get(f"/api/v1/auftraege/{auftrag}")).json()["phase"] == "holen"

    await c.post(f"/api/v1/auftraege/{auftrag}/abbrechen")
    await _beendet(c)
    assert (await mac.put(f"{weg}/stand", json={"zustand": "laeuft"})).status_code == 410   # der Mac lässt ihn fallen
    await mac.aclose()


async def test_falsche_pruefsumme_tauscht_nicht(pi, tmp_path):
    c, app = pi
    mac = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://pi.test", headers=SCHLUESSEL)
    await app.state.indexauftraege.fehlende_einreihen()
    auftrag = (await _laeuft(c))["id"]
    await _abholen(mac)
    await mac.put(f"/api/v1/indexdienst/{auftrag}/datei", params={"ab": 0, "gesamt": 4}, content=b"abcd")
    await mac.post(f"/api/v1/indexdienst/{auftrag}/fertig", json={"pruefsumme": "0" * 64, "groesse": 4, "seiten": 1})
    ende = await _beendet(c)
    assert ende["zustand"] == "fehler" and "Prüfsumme" in ende["fehler"]
    assert not (tmp_path / "pi" / schema.dateiname(DOKU)).exists() and not list((tmp_path / "pi").glob("*.teil"))
    await mac.aclose()


# ----- Mac ohne Netz -----------------------------------------------------------------------------------------------------

def test_mac_wartet_auf_netz_und_haengt_neu_ein(tmp_path):
    """Fehlt die Freigabe, meldet der Dienst "wartet auf Netz", hängt neu ein und versucht es erneut."""
    gemeldet, eingehaengt, halt = [], [], threading.Event()

    def pi(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/abholen"):
            return httpx.Response(200, json={"auftrag": "a1", "buch": DOKU, "da": 0})
        gemeldet.append(request.read())
        if len(eingehaengt) >= 2:
            halt.set()
        return httpx.Response(204)

    mac = httpx.Client(transport=httpx.MockTransport(pi), base_url="http://pi.test")
    Arbeiter(mac, tmp_path / "weg", tmp_path / "mac", lambda: eingehaengt.append(1), abstaende=(0.01,)).laufen(halt)
    assert len(eingehaengt) >= 2 and all(b"wartet_auf_netz" in g for g in gemeldet)


def test_mac_wartet_auf_den_pi(tmp_path):
    versuche, halt = [], threading.Event()

    def pi(request: httpx.Request) -> httpx.Response:
        versuche.append(1)
        if len(versuche) >= 3:
            halt.set()
        raise httpx.ConnectError("Netz weg")

    mac = httpx.Client(transport=httpx.MockTransport(pi), base_url="http://pi.test")
    Arbeiter(mac, tmp_path, tmp_path / "mac", abstaende=(0.01,)).laufen(halt)        # kein Fehler, nur Warten
    assert len(versuche) >= 3


def test_korrektur_ueber_den_wortschatz(buecher, tmp_path):
    """Suchkorrektur (WIKI-41): unbekannte Wörter werden durch ähnliche, häufige des Index ersetzt; bekannte bleiben."""
    from app.korrektur.dienst import abstand, ueber_wortschatz
    ziel = tmp_path / schema.dateiname(DOKU)
    _bauen(buecher, DOKU, ziel)
    assert ueber_wortschatz([ziel], "array_map") == ""                          # bekannt: nichts zu korrigieren
    assert abstand("clipbaord", "clipboard", 2) == 1 and abstand("abc", "xyz", 1) == 2
    assert ueber_wortschatz([], "irgendwas") == ""


async def test_korrektor_fragt_das_modell_nur_wenn_erlaubt(tmp_path):
    from app.einstellungen import TEXTMODELL
    from app.korrektur import Korrektor

    class Leitstelle:
        aufrufe = 0
        modelle: list = []

        async def chat(self, nachrichten, **optionen):
            Leitstelle.aufrufe += 1
            Leitstelle.modelle.append(optionen.get("modell"))
            return type("Antwort", (), {"text": '{"text": "Rotfuchs"}'})()

    k = Korrektor(lambda buecher: [], lambda: Leitstelle(), lambda: TEXTMODELL)
    assert (await k.korrigieren("Rotfuhcs", [])).vorschlag == "" and Leitstelle.aufrufe == 0
    v = await k.korrigieren("Rotfuhcs", [], mit_modell=True)
    assert (v.vorschlag, v.quelle) == ("Rotfuchs", "modell")
    assert Leitstelle.modelle == [TEXTMODELL]                                 # das Modell wählt die App (LS-19)


# ----- Neue Fassung: Unverändertes übernehmen (WIKI-58) ------------------------------------------------------------------

def _inhalt(pfad: Path) -> dict[str, list]:
    v = sqlite3.connect(pfad)
    try:
        return {"seiten": v.execute("SELECT pfad, titel, name, rubrik, einleitung, text, abdruck FROM seiten ORDER BY pfad").fetchall(),
                "schlagwoerter": v.execute("SELECT * FROM register_schlagwoerter ORDER BY wort").fetchall(),
                "autoren": v.execute("SELECT * FROM register_autoren ORDER BY schluessel").fetchall(),
                "ohne": v.execute("SELECT * FROM ohne_seite ORDER BY pfad").fetchall(),
                "register_werkzeuge": v.execute("SELECT * FROM register_werkzeuge ORDER BY wort, sprache").fetchall(),
                # Metadaten über den Pfad ihrer Seite (die Nummern sind je Index andere)
                **{t: v.execute(f"SELECT s.pfad, {', '.join('m.' + s for s in spalten)} FROM {t} m JOIN seiten s ON s.nr = m.nr "
                                f"ORDER BY 1, 2, 3").fetchall() if len(spalten) > 1 else
                   v.execute(f"SELECT s.pfad, m.{spalten[0]} FROM {t} m JOIN seiten s ON s.nr = m.nr ORDER BY 1, 2").fetchall()
                   for t, spalten in aufbau.METADATEN.items()}}
    finally:
        v.close()


def test_neue_fassung_uebernimmt_unveraendertes(tmp_path):
    ordner = tmp_path / "b"
    probebuch.bauen_qa(ordner, "probeqa_en_all_2026-07")
    probebuch.bauen_qa(ordner, "probeqa_en_all_2026-10")             # gleicher Inhalt, neuer Stand
    alt = tmp_path / "ix" / schema.dateiname("probeqa_en_all_2026-07")
    alt.parent.mkdir()
    erst = _bauen(ordner, "probeqa_en_all_2026-07", alt)
    assert erst.fertig and erst.uebernommen == 0 and _inhalt(alt)["ohne"]   # Listen und Konten: gelesen, nicht im Index

    neu = tmp_path / "ix" / schema.dateiname("probeqa_en_all_2026-10")
    stand = _bauen(ordner, "probeqa_en_all_2026-10", neu, vorlage=alt)
    assert stand.fertig and stand.seiten == erst.seiten and stand.uebernommen == stand.seiten
    assert _inhalt(neu) == _inhalt(alt)                                 # Seiten, Metadaten und Register wie neu gebaut
    assert abfrage.suchen(neu, "vim")[1] == abfrage.suchen(alt, "vim")[1]

    # eine geänderte Seite (anderer Abdruck in der Vorlage) wird neu aufbereitet, der Rest übernommen
    v = sqlite3.connect(alt)
    geaendert = v.execute("SELECT pfad FROM seiten LIMIT 1").fetchone()[0]
    v.execute("UPDATE seiten SET abdruck = 'anders' WHERE pfad = ?", (geaendert,))
    v.commit()
    v.close()
    gemischt = tmp_path / "ix" / "gemischt.sqlite"
    stand = _bauen(ordner, "probeqa_en_all_2026-10", gemischt, vorlage=alt)
    assert stand.uebernommen == stand.seiten - 1 and _inhalt(gemischt) == _inhalt(neu)
    # keine taugliche Vorlage (sie selbst, fehlt, halb gebaut): alles neu, ohne Fehler
    assert _bauen(ordner, "probeqa_en_all_2026-10", tmp_path / "ix" / "frei.sqlite", vorlage=tmp_path / "fehlt.sqlite").uebernommen == 0


def test_vorgaenger_ist_der_juengste_geltende_fruehere(buecher, tmp_path):
    gueltig = tmp_path / "vorlage.sqlite"
    _bauen(buecher, DOKU, gueltig)
    for name in ("x_en_all_2026-01", "x_en_all_2026-12", "xy_en_all_2026-03"):
        (tmp_path / schema.dateiname(name)).write_bytes(gueltig.read_bytes())
    (tmp_path / schema.dateiname("x_en_all_2026-05")).write_text("kaputt")       # gilt nicht
    ablage = Eigenindizes(lambda: str(tmp_path))
    assert ablage.vorgaenger("x_en_all_2026-10") == "x_en_all_2026-01"
    assert ablage.vorgaenger("x_en_all_2026-01") == "" and ablage.vorgaenger("ohne_stand") == ""


async def test_mac_holt_die_vorlage_beim_pi(pi, buecher, tmp_path):
    c, app = pi
    (tmp_path / "pi").mkdir()
    vorige = tmp_path / "pi" / schema.dateiname("probedoku_en_php_2026-01")
    _bauen(buecher, DOKU, vorige)                                       # Index einer früheren Fassung liegt auf dem Pi
    assert await app.state.indexauftraege.fehlende_einreihen() == [DOKU]
    await _laeuft(c)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://pi.test", headers=SCHLUESSEL) as mac:
        abholung = await _abholen(mac)
        assert abholung["vorlage"] == "probedoku_en_php_2026-01"
        antwort = await mac.get(f"/api/v1/indexdienst/{abholung['auftrag']}/vorlage")
        assert antwort.status_code == 200 and antwort.content == vorige.read_bytes()

    halt = threading.Event()
    mac = httpx.Client(transport=Bruecke(app, asyncio.get_running_loop()), base_url="http://pi.test", headers=SCHLUESSEL)
    faden = threading.Thread(target=Arbeiter(mac, buecher, tmp_path / "mac", ruhe_s=0.05).laufen, args=(halt,), daemon=True)
    faden.start()
    try:
        fertig = await _beendet(c)
    finally:
        halt.set()
        await asyncio.to_thread(faden.join, 10)
    assert fertig["zustand"] == "fertig", fertig
    v = schema.lesen(tmp_path / "pi" / schema.dateiname(DOKU))
    try:
        assert int(schema.angabe(v, "uebernommen")) == v.execute("SELECT COUNT(*) FROM seiten").fetchone()[0] > 0
    finally:
        v.close()


def test_text_mit_steuerzeichen():
    """Seiten mit Steuerzeichen (vereinzelt in iFixit) halten den Index nicht auf: sie werden zu Leerraum."""
    assert aufbau._text("<p>Akku\x0blösen</p><p>Schritt\x01 2</p>") == "Akku lösen Schritt 2"


def test_index_entfernen(buecher, tmp_path):
    """WIKI-77: der Index eines gelöschten Buchs geht samt Prüfsumme; danach gilt keiner mehr."""
    eigen = Eigenindizes(lambda: str(tmp_path))
    ziel = tmp_path / schema.dateiname(DOKU)
    _bauen(buecher, DOKU, ziel)
    assert eigen.datei(DOKU) == ziel and ziel.with_suffix(".sha256").is_file()
    assert eigen.entfernen(DOKU) and eigen.datei(DOKU) is None
    assert not ziel.exists() and not ziel.with_suffix(".sha256").exists()
    assert not eigen.entfernen(DOKU)



def test_rueckverweise(buecher, tmp_path):
    """WIKI-20: der Index merkt sich die Verweise jeder Seite; daraus die Seiten, die auf eine Seite verweisen."""
    ziel = tmp_path / schema.dateiname("probe_de_all_2026-01")
    _bauen(buecher, "probe_de_all_2026-01", ziel)
    liste, gesamt = abfrage.rueckverweise(ziel, "Kreuzfuchs")
    assert gesamt >= 1 and "Rotfuchs" in [r.pfad for r in liste]
    assert abfrage.rueckverweise(ziel, "gibt_es_nicht") == ([], 0)
    v = sqlite3.connect(ziel)                       # ein Index von vorher kennt die Verweise nicht: keine Aussage
    v.execute("DELETE FROM angaben WHERE schluessel = 'verweise'")
    v.commit()
    v.close()
    assert abfrage.rueckverweise(ziel, "Kreuzfuchs") is None
