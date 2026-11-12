"""WIKI-100: Vorgabe je Dienst für die Leitstelle: Rechnerwunsch und Vorrang aus den Einstellungen, als Köpfe jeder
Anfrage des Dienstes; ohne Wunsch entscheidet die Leitstelle; Hintergrundarbeit bleibt Hintergrund."""

import httpx

from appkern.leitstelle import Leitstelle

from app.einstellungen import AppEinstellungen
from app.vorgaben import Vorgaben, vorgabe


def test_vorgabe_aus_den_einstellungen():
    e = AppEinstellungen()
    assert vorgabe(e, "vorlesen") == ([], "hoch") and vorgabe(e, "buch") == ([], "normal")
    e = AppEinstellungen(vorlesen_rechner="mac-128", uebersetzung_vorrang="normal")
    assert vorgabe(e, "vorlesen") == (["mac-128"], "hoch") and vorgabe(e, "uebersetzung") == ([], "normal")


async def test_jeder_dienst_schickt_seine_vorgabe():
    gesehen: list[dict[str, str]] = []

    def antwort(r: httpx.Request) -> httpx.Response:
        gesehen.append({k: v for k, v in r.headers.items() if k in ("x-leitstelle-rechner", "x-leitstelle-prioritaet")})
        return httpx.Response(200, json={"ok": True})

    e = AppEinstellungen(vorlesen_rechner="mac-128", spracheingabe_vorrang="normal")
    async with httpx.AsyncClient(transport=httpx.MockTransport(antwort)) as client:
        ls = Leitstelle("http://ls.test", "ls_x", "Nachschlag", client=client)
        v = Vorgaben(lambda: ls, lambda: e)
        await v.leitstelle("vorlesen")().dienst("klangwerk-sprechen").json("POST", "/v1/audio/speech", json={})
        await v.leitstelle("vorlesen")().dienst("klangwerk-sprechen").json("POST", "/v1/audio/speech", json={},
                                                                          prioritaet="hintergrund")
        await v.leitstelle("spracheingabe")().dienst("klangwerk-hoeren").json("POST", "/x", json={})
    assert gesehen == [{"x-leitstelle-rechner": "mac-128", "x-leitstelle-prioritaet": "hoch"},
                       {"x-leitstelle-rechner": "mac-128", "x-leitstelle-prioritaet": "hintergrund"},
                       {"x-leitstelle-prioritaet": "normal"}]
    assert Vorgaben(lambda: None, lambda: e).leitstelle("vorlesen")() is None
