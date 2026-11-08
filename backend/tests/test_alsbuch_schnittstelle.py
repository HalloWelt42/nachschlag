"""Als Buch über die Schnittstelle (WIKI-45), mit dem Probebuch und der nachgestellten Kellerwolke: Seite Als Buch,
Vorlagen als Dateien (kopieren, ändern, weitergeben, löschen), Schätzung, ein Nachschlagewerk bauen (ohne KI), Regal,
Herunterladen, Lesen und Löschen. Vorlagen mit KI brauchen die Leitstelle."""

import asyncio
import io
import zipfile

from test_app import buecher, nachschlag  # noqa: F401 (Fixtures)


async def test_als_buch_ueber_die_schnittstelle(nachschlag):  # noqa: F811
    c, _, _ = nachschlag
    t = (await c.post("/api/v1/meins/themen", json={"titel": "Füchse"})).json()
    for pfad in ("Rotfuchs", "Kreuzfuchs"):
        r = await c.post(f"/api/v1/meins/themen/{t['id']}/eintraege", json={"buch": "probe_de_all_2026-01", "pfad": pfad, "titel": pfad})
        assert r.status_code == 200
    wahl = (await c.get(f"/api/v1/meins/buecher/thema/{t['id']}")).json()
    assert wahl["artikel"] == 2 and [(k["titel"], k["artikel"]) for k in wahl["kapitel"]] == [("Füchse", 2)]
    assert wahl["steckbriefe"] == 1 and wahl["leitstelle"] is False and wahl["ablage"].endswith("/Bücher/Füchse")
    assert (await c.get("/api/v1/meins/buecher/thema/gibt-es-nicht")).status_code == 404

    # Vorlagen: mitgelieferte fest, eigene als Datei in der Kellerwolke
    liste = (await c.get("/api/v1/buchvorlagen")).json()
    assert [v["kennung"] for v in liste["vorlagen"]] == ["sachbuch", "lernheft", "nachschlagewerk", "vorlesebuch", "einfache-sprache"]
    assert liste["ordner"] == "Apps/Nachschlag/Vorlagen" and liste["hinweis"] == ""
    katalog = (await c.get("/api/v1/buchvorlagen/teile")).json()
    assert "Beleg je Absatz" in katalog["regeln"] and any(x["art"] == "kasten" for x in katalog["teile"])
    kopie = (await c.post("/api/v1/buchvorlagen/lernheft/kopie", json={"titel": "Beobachtungsheft"})).json()
    assert kopie["kennung"] == "beobachtungsheft" and kopie["kopiert_aus"] == "Lernheft" and not kopie["mitgeliefert"]
    kopie["aufbau"]["innen"].append({"art": "kasten", "titel": "So beobachtest du es", "anweisung": "Womit man es sieht."})
    assert (await c.put("/api/v1/buchvorlagen/beobachtungsheft", json=kopie)).status_code == 200
    kopie["aufbau"]["vorn"].append({"art": "blick"})
    assert (await c.put("/api/v1/buchvorlagen/beobachtungsheft", json=kopie)).status_code == 422     # Auf einen Blick nicht vorn
    kopie["aufbau"]["vorn"].pop()
    assert (await c.put("/api/v1/buchvorlagen/lernheft", json={**kopie, "kennung": "lernheft"})).status_code == 409
    datei = await c.get("/api/v1/buchvorlagen/beobachtungsheft/datei")
    assert 'So beobachtest du es' in datei.text and "beobachtungsheft.toml" in datei.headers["content-disposition"]
    assert [v["titel"] for v in (await c.get("/api/v1/buchvorlagen")).json()["vorlagen"]][-1] == "Beobachtungsheft"
    assert (await c.delete("/api/v1/buchvorlagen/beobachtungsheft")).status_code == 204
    assert (await c.delete("/api/v1/buchvorlagen/sachbuch")).status_code == 409

    # Ohne Leitstelle keine KI; ein Nachschlagewerk geht
    lernheft = {"thema": t["id"], "vorlage": "lernheft", "pdf": False, "wann": "jetzt"}
    assert (await c.post("/api/v1/meins/buecher", json=lernheft)).status_code == 409
    bestellung = {**lernheft, "vorlage": "nachschlagewerk"}
    s = (await c.post("/api/v1/meins/buecher/schaetzung", json=bestellung)).json()
    assert s["artikel"] == 2 and s["schritte"][-1]["titel"] == "Satz EPUB, Bilder" and s["tempo"] == 75
    assert (await c.post("/api/v1/meins/buecher/schaetzung", json={**bestellung, "epub": False, "pdf": False})).status_code == 422
    auftrag = (await c.post("/api/v1/meins/buecher", json=bestellung)).json()
    for _ in range(300):
        a = (await c.get(f"/api/v1/auftraege/{auftrag['id']}")).json()
        if a["zustand"] not in ("wartet", "laeuft"):
            break
        await asyncio.sleep(0.02)
    assert a["zustand"] == "fertig", a.get("fehler")
    regal = (await c.get("/api/v1/meins/buecher")).json()
    buch = regal["fertig"][0]
    assert (buch["titel"], buch["vorlage_titel"], buch["artikel"]) == ("Füchse", "Nachschlagewerk", 2)
    assert buch["formate"][0]["pfad"] == "Apps/Nachschlag/Bücher/Füchse/Füchse - Nachschlagewerk.epub"
    epub = await c.get(f"/api/v1/meins/buecher/{buch['id']}/datei/epub")
    assert epub.headers["content-type"] == "application/epub+zip" and "filename*=UTF-8''F%C3%BCchse" in epub.headers["content-disposition"]
    assert zipfile.ZipFile(io.BytesIO(epub.content)).read("mimetype") == b"application/epub+zip"
    assert (await c.get(f"/api/v1/meins/buecher/{buch['id']}/datei/pdf")).status_code == 404
    lesen = (await c.get(f"/api/v1/meins/buecher/{buch['id']}/lesen")).json()
    assert "Kreuzfuchs" in lesen["html"] and "Quellen und Lizenzen" in lesen["html"]
    assert (await c.get(f"/api/v1/meins/buecher/probe/{t['id']}")).json() is None
    assert (await c.delete(f"/api/v1/meins/buecher/{buch['id']}")).status_code == 204
    assert (await c.get("/api/v1/meins/buecher")).json()["fertig"] == []
