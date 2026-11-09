"""Originalansicht auf eigener Herkunft (WIKI-85): Scheine, Geheimnis im Datenordner, Brücke in der Seite."""

from pathlib import Path

from starlette.datastructures import URL

from app.originalansicht import GUELTIG_TAGE, Originalherkunft
from app.originalansicht.herkunft import GEHEIM_DATEI
from app.originalansicht.seite import BRUECKE_TAG, bruecke_einsetzen

TAG = 86400


class Uhr:
    def __init__(self, tag: int) -> None:
        self.jetzt = tag * TAG + 3600.0

    def __call__(self) -> float:
        return self.jetzt


def test_schein_gilt_fuer_ein_buch_und_eine_frist():
    uhr = Uhr(20000)
    h = Originalherkunft(8712, b"g" * 32, uhr)
    schein = h.schein("buch_a")
    assert h.gilt(schein, "buch_a") and not h.gilt(schein, "buch_b")
    uhr.jetzt += 5 * 3600
    assert h.schein("buch_a") == schein                    # derselbe Tag: dieselbe Adresse, der Zwischenspeicher hält
    uhr.jetzt += GUELTIG_TAGE * TAG
    assert h.gilt(schein, "buch_a")                        # bis zum Ablauftag
    uhr.jetzt += TAG
    assert not h.gilt(schein, "buch_a")
    assert not Originalherkunft(8712, b"x" * 32, uhr).gilt(h.schein("buch_a"), "buch_a")   # anderes Geheimnis
    for falsch in ("", "abc", "1.", f"{20000 + GUELTIG_TAGE * 9}.{schein.split('.')[1]}"):
        assert not h.gilt(falsch, "buch_a")


def test_geheimnis_bleibt_im_datenordner(tmp_path: Path):
    a = Originalherkunft.im_ordner(8712, tmp_path / "daten")
    b = Originalherkunft.im_ordner(8712, tmp_path / "daten")
    assert a.schein("x") == b.schein("x")
    datei = tmp_path / "daten" / GEHEIM_DATEI
    assert len(datei.read_bytes()) == 32 and datei.stat().st_mode & 0o777 == 0o600


def test_adresse_und_herkunft():
    h = Originalherkunft(8712, b"g" * 32)
    app = URL("https://nachschlag.local:8711/api/v1/artikel/b/p?x=1")
    assert h.adresse(app, "/api/v1/original/s/b/p") == "https://nachschlag.local:8712/api/v1/original/s/b/p"
    assert h.adresse(URL("http://[::1]:9711/x"), "/w") == "http://[::1]:8712/w"
    assert h.ist_original(URL("https://192.168.178.49:8712/w")) and not h.ist_original(app)
    assert not h.ist_original(URL("https://nachschlag.local/w"))


def test_bruecke_an_den_anfang_des_kopfs():
    assert bruecke_einsetzen(b'<!DOCTYPE html><html lang="de"><HEAD class="x"><title>T</title>') \
        == b'<!DOCTYPE html><html lang="de"><HEAD class="x">' + BRUECKE_TAG + b"<title>T</title>"
    assert bruecke_einsetzen(b"<html><body>B</body></html>") == b"<html>" + BRUECKE_TAG + b"<body>B</body></html>"
    assert bruecke_einsetzen(b"<p>nur Text</p>") == BRUECKE_TAG + b"<p>nur Text</p>"
    assert bruecke_einsetzen(b"<header>kein Kopf</header>") == BRUECKE_TAG + b"<header>kein Kopf</header>"
