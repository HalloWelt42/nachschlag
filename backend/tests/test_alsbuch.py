"""Als Buch (WIKI-45): Vorlagen (Dateien, Aufbau), Quelle eines Artikels, Prüfung gegen das Original, Schätzung,
EPUB-Aufbau, Satz als PDF (wenn Pango da ist) und der ganze Weg mit nachgestelltem Sprachmodell: Probekapitel mit
Neuschreiben, Bau, Zwischenspeicher (ein Nachbau formt nur Neues um) und Regal."""

from __future__ import annotations

import asyncio
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest
from lxml import etree

from appkern.auftraege import Auftraege
from appkern.datenbank import Datenbank

from app.alsbuch import quelle as quellen
from app.alsbuch.ablage import Buchablage
from app.alsbuch.bilder import Bilddatei
from app.alsbuch.darstellung import epub_seiten, lesen_html, pdf_dokument, stil
from app.alsbuch.dauer import HAUSMESSUNG_ZEICHEN_JE_S, schaetzen
from app.alsbuch.dienst import Buecher
from app.alsbuch.epub import Epubangaben, Epubbild, epub_bauen
from app.alsbuch.pdf import pdf_bauen, verfuegbar
from app.alsbuch.pruefung import pruefen, zahlwerte
from app.alsbuch.teile import KATALOG
from app.alsbuch.vorlagen import Vorlagen, als_toml, aus_toml, kennung_fuer, mitgelieferte
from app.einstellungen import TEXTMODELL
from app.modell.alsbuch import (
    Absatz, Aufbau, Belegt, Bestellung, Bild, Buchartikel, Buchinhalt, Buchkapitel, Frage, Glossareintrag, Kasten,
    Probewunsch, Quellangabe, Randnotiz, Teil, Vorlage,
)
from app.modell.artikel import Artikel, Steckbrief
from app.modell.buch import Buch, Faehigkeiten
from app.modell.meins import Notiz
from app.modell.themen import Bereich, Thema, Themeneintrag
from app.zeitfenster import ZONE, Nachtfenster

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00"
       b"\x00\rIDATx\x9cc\xf8\xff\xff?\x03\x00\x08\xfc\x02\xfe\xa7\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")
SATURN = """<div><figure><img src="/api/v1/inhalt/medien/wp_de_2026-01/_assets_/saturn.png"/><figcaption>Saturn im
Fernrohr</figcaption></figure>
<aside class="steckbrief"><p>Steckbrief</p></aside>
<p>Der Saturn ist der sechste Planet und mit einem Durchmesser von etwa 120.500 Kilometern nach Jupiter der zweitgrößte.<span class="beleg" data-beleg="1"></span></p>
<p>Als Gasplanet hat Saturn keine feste Oberfläche. Seine mittlere Dichte von etwa 0,69 g/cm³ ist die geringste aller Planeten.</p>
<h2 id="u">Umlaufbahn</h2>
<p>Für einen Umlauf um die Sonne benötigt der Saturn ungefähr 29 Jahre und 163 Tage.</p>
<ul><li>Perihel bei 9,04 AE</li><li>Aphel bei 10,12 AE</li></ul>
<table><tr><th>Masse</th><td>95 Erdmassen</td></tr></table>
</div>"""
ERFUNDEN = "In einer großen Badewanne würde er deshalb schwimmen."


# ----- Vorlagen ---------------------------------------------------------------------------------------------------------

def test_mitgelieferte_vorlagen_und_datei_hin_und_zurueck():
    vorlagen = mitgelieferte()
    assert [v.titel for v in vorlagen] == ["Sachbuch", "Lernheft", "Nachschlagewerk", "Vorlesebuch", "Einfache Sprache"]
    assert [v.ki for v in vorlagen] == [True, True, False, True, True]
    assert all(v.mitgeliefert for v in vorlagen)
    lernheft = vorlagen[1]
    eigene = lernheft.model_copy(update={"kennung": "beobachtungsheft", "titel": "Beobachtungsheft", "mitgeliefert": False,
                                         "aufbau": lernheft.aufbau.model_copy(update={"innen": [*lernheft.aufbau.innen, Teil(
                                             art="kasten", titel="So beobachtest du es", anweisung="Womit man es sieht.")]})})
    text = als_toml(eigene)
    assert "kennung" not in text and "mitgeliefert" not in text and 'titel = "So beobachtest du es"' in text
    wieder = aus_toml("beobachtungsheft", text)
    assert wieder == eigene and wieder.ki
    with pytest.raises(ValueError, match="aufbau"):
        aus_toml("kaputt", 'titel = "X"\n[aufbau]\nvorn = [{ art = "blick" }]\n')
    assert kennung_fuer("Größe & Maß", {"groesse-mass"}) == "groesse-mass-2"
    assert {t.art for t in KATALOG} >= {"blick", "umgeformt", "originaltext", "kasten", "abc"}


def test_aufbau_prueft_plaetze_und_einmaliges():
    with pytest.raises(ValueError, match="nicht im Kapitel"):
        Aufbau(innen=[Teil(art="glossar")])
    with pytest.raises(ValueError, match="nur einmal"):
        Aufbau(innen=[Teil(art="umgeformt"), Teil(art="originaltext")])
    with pytest.raises(ValueError, match="Überschrift und Anweisung"):
        Aufbau(innen=[Teil(art="kasten", titel="Ohne Anweisung")])
    assert Aufbau(vorn=[Teil(art="titelseite")], gliederung="abc", innen=[Teil(art="originaltext")]).gliederung == "abc"


# ----- Quelle und Prüfung -----------------------------------------------------------------------------------------------

def test_quelle_nummeriert_absaetze_mit_bildern_und_teilt_in_stuecke():
    q = quellen.lesen("Saturn", SATURN)
    assert [(b.art, b.nr) for b in q.bloecke] == [("absatz", 1), ("absatz", 2), ("ueberschrift", 0), ("absatz", 3),
                                                  ("punkt", 4), ("punkt", 5), ("tabelle", 0)]
    assert q.bloecke[0].bilder == [Bild(adresse="/api/v1/inhalt/medien/wp_de_2026-01/_assets_/saturn.png",
                                        unterschrift="Saturn im Fernrohr")]
    assert "Steckbrief" not in " ".join(b.text for b in q.bloecke)              # Steckbrief und Belegmarken bleiben draußen
    assert "<td>95 Erdmassen</td>" in q.bloecke[-1].html
    assert quellen.stelle_von(q, "ungefähr 29 Jahre\nund 163 Tage") == 3
    stuecke = quellen.stuecke(q, hoechstens=300)
    assert [[b.nr for b in s] for s in stuecke] == [[1, 2], [0, 3, 4, 5]]            # an der Überschrift geteilt
    assert quellen.als_eingabe(stuecke[1]).startswith("## Umlaufbahn\n[3] Für einen Umlauf")
    assert "[4] - Perihel" in quellen.als_eingabe(stuecke[1])


def test_zahlen_in_beiden_schreibweisen():
    assert zahlwerte("120.500 km") >= {"120500"} and "0.69" in zahlwerte("etwa 0,69 g")
    assert zahlwerte("1,430 miles") & zahlwerte("1.430 Meilen") and "1.43" in zahlwerte("1,43 Milliarden")


def test_pruefung_markiert_saetze_zahlen_und_fehlende_belege():
    q = quellen.lesen("Saturn", SATURN)
    a = Buchartikel(eintrag="e", titel="Saturn", buch="b", pfad="p", quelle=Quellangabe(buch="B", urheber="u", lizenz="l"),
                    blick=Kasten(titel="Auf einen Blick", punkte=[Belegt(text="Ein Tag dauert 10,5 Stunden.", belege=[3])]),
                    absaetze=[Absatz(text=f"Saturn ist ein Gasplanet ohne feste Oberfläche; seine mittlere Dichte von 0,69 g/cm³ ist "
                                          f"die geringste. {ERFUNDEN}", belege=[2]),
                              Absatz(text="Ein Umlauf dauert 29 Jahre und 163 Tage.", belege=[3]),
                              Absatz(text="Ohne Beleg.", belege=[99])])
    geprueft, p = pruefen(q, a)
    assert geprueft.absaetze[0].ohne_beleg == [ERFUNDEN] and geprueft.absaetze[1].ohne_beleg == []
    assert (p.zahlen, p.zahlen_gefunden, p.absaetze, p.belegt) == (4, 3, 4, 3)
    assert {(h.art, h.text) for h in p.hinweise} == {("satz", ERFUNDEN), ("zahl", "10,5"), ("beleg", "Ohne Beleg.")}


# ----- Schätzung und Nachtfenster ---------------------------------------------------------------------------------------

def test_schaetzung_aus_der_hausmessung():
    lernheft = mitgelieferte()[1]
    b = Bestellung(thema="t", vorlage="lernheft", laenge="haelfte", fragen=5, epub=True, pdf=True, seiten="a5")
    s = schaetzen([40_000, 20_000], 2, 10, lernheft, b, HAUSMESSUNG_ZEICHEN_JE_S, False, TEXTMODELL)
    titel = [x.titel for x in s.schritte]
    assert titel[0] == "Artikel umformen, auf die Hälfte" and s.schritte[0].sekunden == pytest.approx(400)
    assert titel[1] == "Auf einen Blick und Einleitungen und Fragen, 2 Kapitel" and titel[2] == "Glossar"
    assert titel[-1] == "Prüfen, Satz EPUB und PDF, Bilder" and s.sekunden == pytest.approx(sum(x.sekunden for x in s.schritte))
    assert s.seiten > 20 and not s.gemessen
    ohne_ki = schaetzen([40_000], 1, 0, mitgelieferte()[2], b.model_copy(update={"pdf": False}), 75, False, TEXTMODELL)
    assert [x.titel for x in ohne_ki.schritte] == ["Satz EPUB"]


def test_nachtfenster_naechste_nacht():
    uhr = {"jetzt": datetime(2026, 11, 8, 15, 30, tzinfo=ZONE)}
    n = Nachtfenster(lambda: (1, 6), lambda: uhr["jetzt"])
    beginn, ende = n.naechste()
    assert (beginn.day, beginn.hour, ende.day, ende.hour) == (9, 1, 9, 6) and n.warten() == "wartet auf die Nacht (1 bis 6 Uhr)"
    uhr["jetzt"] = datetime(2026, 11, 9, 2, 10, tzinfo=ZONE)
    assert n.ist_nacht() and n.naechste()[0].hour == 2 and n.warten() == ""


# ----- Darstellung, EPUB und PDF ----------------------------------------------------------------------------------------

def inhalt(vorlage: Vorlage) -> Buchinhalt:
    bild = Bild(adresse="/api/v1/inhalt/medien/wp/saturn.png", unterschrift="Saturn & Ringe")
    artikel = Buchartikel(
        eintrag="e1", titel="Saturn <Planet>", buch="wp", pfad="Saturn", leitbild=bild,
        quelle=Quellangabe(buch="Wikipedia", fassung="2026-01", adresse="https://de.wikipedia.org/wiki/Saturn",
                           urheber="die Autorinnen und Autoren", lizenz="CC BY-SA 4.0"),
        blick=Kasten(titel="Auf einen Blick", punkte=[Belegt(text="sechster Planet", belege=[1])]),
        absaetze=[Absatz(text="Saturn ist der sechste Planet.", belege=[1], notizen=[Randnotiz(text="Mit dem Fernrohr", zitat="Planet")],
                         bilder=[bild], hervorgehoben=True),
                  Absatz(text="", html="Ein <b>Punkt</b>", art="punkt", liste=1, belege=[2], ueberschrift="Bahn"),
                  Absatz(text="", html="<table><tr><td>95</td></tr></table>", art="tabelle")],
        notizen=[Randnotiz(text="Ganz allgemein")])
    kapitel = Buchkapitel(titel="Planeten", einleitung=[Belegt(text="Ein Kapitel über Planeten.", belege=[1])], artikel=[artikel],
                          fragen=[Frage(frage="Welcher Planet?", antwort="Der sechste.", belege=[1])])
    return Buchinhalt(titel="Sternenhimmel", untertitel="Ein Lernheft", vorlage=vorlage, titelbild=bild, kapitel=[kapitel],
                      glossar=[Glossareintrag(begriff="Gasplanet", erklaerung="Ein Planet aus Gas.")],
                      literatur=["## Planeten", "- Saturn. In: Wikipedia", "  - Beleg 1: NASA"], erstellt="2026-11-08")


def epub_pruefen(daten: bytes) -> dict[str, bytes]:
    """Prüft den Aufbau eines EPUB 3 und gibt seine Dateien zurück."""
    z = zipfile.ZipFile(io.BytesIO(daten))
    erste = z.infolist()[0]
    assert erste.filename == "mimetype" and erste.compress_type == zipfile.ZIP_STORED and z.read("mimetype") == b"application/epub+zip"
    container = etree.fromstring(z.read("META-INF/container.xml"))
    opf_pfad = container.find(".//{*}rootfile").get("full-path")
    opf = etree.fromstring(z.read(opf_pfad))
    ns = {"o": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    assert opf.get("version") == "3.0" and opf.find(".//dc:identifier", ns).text.startswith("urn:uuid:")
    assert opf.find(".//dc:title", ns).text and opf.find(".//dc:language", ns).text == "de"
    assert opf.find(".//o:meta[@property='dcterms:modified']", ns) is not None
    basis = opf_pfad.rsplit("/", 1)[0]
    items = {i.get("id"): i for i in opf.findall(".//o:manifest/o:item", ns)}
    namen = set(z.namelist())
    for i in items.values():
        assert f"{basis}/{i.get('href')}" in namen, i.get("href")
    assert all(r.get("idref") in items for r in opf.findall(".//o:spine/o:itemref", ns))
    navs = [i for i in items.values() if "nav" in (i.get("properties") or "").split()]
    assert len(navs) == 1
    nav = etree.fromstring(z.read(f"{basis}/{navs[0].get('href')}"))
    assert nav.find(".//{http://www.w3.org/1999/xhtml}nav").get("{http://www.idpf.org/2007/ops}type") == "toc"
    for name in namen:
        if name.endswith(".xhtml"):
            doc = etree.fromstring(z.read(name))                                 # wohlgeformtes XHTML
            for img in doc.iter("{http://www.w3.org/1999/xhtml}img"):
                assert f"{basis}/{img.get('src')}" in namen
    return {n: z.read(n) for n in namen}


def test_epub_aufbau_mit_allen_teilen():
    lernheft = mitgelieferte()[1]
    i = inhalt(lernheft.model_copy(update={"aufbau": lernheft.aufbau.model_copy(update={"hinten": [Teil(art="glossar"), Teil(art="literatur")]})}))
    namen = {i.titelbild.adresse: "bilder/b000.png"}
    seiten, nav, im_buch = epub_seiten(i, lambda b: namen.get(b.adresse))
    assert [s.datei for s in seiten] == ["titel.xhtml", "kapitel-01.xhtml", "glossar.xhtml", "literatur.xhtml", "quellen.xhtml"] and im_buch
    assert [p.titel for p in nav] == ["1 Planeten", "Glossar", "Literaturliste", "Quellen und Lizenzen"]
    assert nav[0].unter[0].ziel == "kapitel-01.xhtml#k1-a1"
    daten = epub_bauen(Epubangaben(titel="Sternenhimmel", untertitel="Ein Lernheft", kennung="urn:uuid:1", titelbild="bilder/b000.png"),
                       seiten, nav, stil(i.vorlage.gestaltung, "epub"), [Epubbild("bilder/b000.png", "image/png", PNG)], im_buch,
                       geaendert=datetime(2026, 11, 8, 12, 0))
    dateien = epub_pruefen(daten)
    kapitel = dateien["OEBPS/kapitel-01.xhtml"].decode()
    assert "Saturn &lt;Planet&gt;" in kapitel and "Auf einen Blick" in kapitel and "<details><summary>Antwort</summary>" in kapitel
    assert '<p class="hervorgehoben">' in kapitel and "Meine Notiz:" in kapitel and "Ganz allgemein" in kapitel
    assert '<ul><li>Ein <b>Punkt</b></li></ul>' in kapitel and "Ein Kapitel über Planeten." in kapitel
    assert kapitel.index("Ein Kapitel über Planeten.") < kapitel.index("Auf einen Blick") < kapitel.index("Fragen zum Kapitel")
    opf = dateien["OEBPS/paket.opf"].decode()
    assert 'properties="cover-image"' in opf and opf.index('idref="s0"') < opf.index('idref="nav"') < opf.index('idref="s1"')
    assert "CC BY-SA 4.0" in dateien["OEBPS/quellen.xhtml"].decode()
    assert "Saturn &amp; Ringe" in kapitel


def test_pdf_dokument_und_leseansicht():
    i = inhalt(mitgelieferte()[1])
    html = pdf_dokument(i, lambda b: "bilder/b000.png", "a5")
    assert "size: A5" in html and 'href="#antworten-1"' in html and "target-counter" in html
    assert "<details>" not in html and '<section class="antworten"' in html
    etree.fromstring(html.encode())                                                     # wohlgeformt
    lesen = lesen_html(i, lambda b: b.adresse)
    assert "<details>" in lesen and 'src="/api/v1/inhalt/medien/wp/saturn.png"' in lesen and "@page" not in lesen


@pytest.mark.skipif(bool(verfuegbar()), reason="Satz als PDF braucht Pango (am Mac DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib)")
def test_pdf_satz_a5_und_zwei_je_a4(caplog):
    i = inhalt(mitgelieferte()[1])
    html = pdf_dokument(i, lambda b: "bilder/b000.png", "a5")
    pdf, seiten = pdf_bauen(html, {"bilder/b000.png": (PNG, "image/png")})
    assert pdf.startswith(b"%PDF") and seiten >= 4
    zwei, _ = pdf_bauen(html, {"bilder/b000.png": (PNG, "image/png")}, zwei_je_a4=True)
    from pypdf import PdfReader
    blaetter = PdfReader(io.BytesIO(zwei)).pages
    assert len(blaetter) == (seiten + 1) // 2 and float(blaetter[0].mediabox.width) > float(blaetter[0].mediabox.height)
    pdf_bauen(html.replace("bilder/b000.png", "file:///etc/passwd"), {})               # nur Bilder aus dem Buch
    assert "nicht im Buch: file:///etc/passwd" in caplog.text


# ----- Der ganze Weg mit nachgestelltem Sprachmodell --------------------------------------------------------------------

BUCH = Buch(kennung="wp_de_2026-01", name="wp_de", titel="Probe-Wiki", sprache="deu", art="enzyklopaedie", eintraege=3,
            artikel=3, medien=1, groesse=1, stand="2026-01-01",
            faehigkeiten=Faehigkeiten(titelindex=True, volltext=True, bilder=True, lesedesign=True))
TEXTE = {"Saturn": SATURN, "Mars": "<p>Der Mars ist der vierte Planet. Er ist rot.</p><p>Ein Tag dauert 24 Stunden und 37 Minuten.</p>",
         "Mond": "<p>Der Mond umkreist die Erde in 27 Tagen.</p>"}


def eintrag(i: str, pfad: str, bereich: str, platz: int) -> Themeneintrag:
    return Themeneintrag(id=i, bereich=bereich, buch_name="wp_de", buch=BUCH.kennung, pfad=pfad, titel=pfad, platz=platz,
                         bild="/api/v1/inhalt/medien/wp_de_2026-01/_assets_/saturn.png" if pfad == "Saturn" else "")


class Themen:
    def __init__(self) -> None:
        self.t = Thema(id="t1", titel="Sternenhimmel", angelegt="2026-11-08",
                       bereiche=[Bereich(id="b1", titel="Planeten", platz=0), Bereich(id="b2", titel="Monde", platz=1)],
                       eintraege=[eintrag("e1", "Saturn", "b1", 0), eintrag("e3", "Mond", "b2", 0)])

    async def thema(self, konto, kennung):
        return self.t if kennung == "t1" else None


class Bib:
    async def buch(self, kennung):
        return BUCH

    async def eintrag(self, buch, pfad):
        return type("Eintrag", (), {"inhalt": PNG, "mime": "image/png"})()


class Leser:
    async def lesen(self, buch, pfad):
        return Artikel(buch=buch, pfad=pfad, angefragt=pfad, titel=pfad, darstellung="lesedesign", baustein="enzyklopaedie",
                       original="/o", html=TEXTE[pfad], steckbrief=Steckbrief(titel=pfad, html="<dl><dt>Art</dt><dd>Planet</dd></dl>"))


class Uebersetzer:
    async def abgelegt(self, buch, pfad):
        return None


@dataclass
class Antwort:
    text: str


class Leitstelle:
    """Formt um, indem es jeden Absatz übernimmt; im ersten Absatz von Saturn erfindet es einen Satz."""

    def __init__(self) -> None:
        self.aufrufe: list[tuple[str, dict]] = []

    async def chat(self, nachrichten, **optionen):
        name = optionen["response_format"]["json_schema"]["name"]
        nutzer = nachrichten[1].inhalt
        self.aufrufe.append((name, optionen))
        zeilen = re.findall(r"^\[(\d+)\] (?:- )?(.+)$", nutzer, re.M)
        if name == "umformung":
            absaetze = [{"ueberschrift": "", "text": text + (f" {ERFUNDEN}" if nr == "1" and "Saturn" in nutzer else ""),
                         "belege": [int(nr)]} for nr, text in zeilen]
            return Antwort(json.dumps({"absaetze": absaetze}))
        if name == "artikelteile":
            return Antwort(json.dumps({"blick": [{"text": zeilen[0][1][:60], "belege": [int(zeilen[0][0])]}]}))
        if name == "kapitelteile":
            return Antwort(json.dumps({"einleitung": [{"text": "Hier geht es um den Himmel.", "belege": [1]}],
                                       "fragen": [{"frage": "Wie lange dauert ein Umlauf?", "antwort": "Etwa 29 Jahre.", "belege": [1]}],
                                       "glossar": [{"begriff": "Gasplanet", "erklaerung": "Ein Planet aus Gas."},
                                                   {"begriff": "Erfunden", "erklaerung": "Steht nicht im Kapitel."}]}))
        if name == "absatz":
            return Antwort(json.dumps({"text": "Der Saturn ist der sechste Planet und nach Jupiter der zweitgrößte.", "belege": [1]}))
        raise AssertionError(name)


@dataclass
class Knoten:
    etag: str
    id: str


class Kellerwolke:
    def __init__(self) -> None:
        self.dateien: dict[str, bytes] = {}

    async def ich(self):
        return type("Ich", (), {"zweig": "Apps/Nachschlag"})()

    async def ordner(self, pfad):
        return None

    async def finden(self, pfad):
        return Knoten("e", pfad) if pfad in self.dateien else None

    async def schreiben(self, pfad, inhalt, *, stand=None, inhaltstyp=None):
        assert (pfad in self.dateien) == (stand is not None)
        self.dateien[pfad] = inhalt

    async def lesen(self, kennung):
        yield self.dateien[kennung]


class Bilder:
    async def holen(self, adresse, gross=False):
        return Bilddatei(PNG, "image/png", "Jemand" if gross else "", "CC0" if gross else "")


@pytest.fixture
async def db(tmp_path: Path):
    d = await Datenbank(tmp_path / "b.sqlite").oeffnen()
    yield d
    await d.schliessen()


@pytest.fixture
async def dienst(db):
    auftraege = Auftraege(db, [], gleichzeitig=2)
    themen, kw, ls = Themen(), Kellerwolke(), Leitstelle()
    notizen = [Notiz(id="n1", buch_name="wp_de", buch=BUCH.kennung, pfad="Saturn", titel="Saturn", zitat="ungefähr 29 Jahre",
                     text="Mit dem Fernrohr sehen", angelegt="1", geaendert="1"),
               Notiz(id="n2", buch_name="wp_de", buch=BUCH.kennung, pfad="Saturn", titel="Saturn", zitat="keine feste Oberfläche",
                     angelegt="2", geaendert="2")]

    async def alle_notizen(konto):
        return notizen

    async def literatur(konto, t):
        return "# Literatur\n\n## Planeten\n\n- Saturn. In: Probe-Wiki\n"

    b = Buecher(db, auftraege, themen, Bib(), Leser(), Uebersetzer(), alle_notizen, literatur, Vorlagen(lambda: None),
                Buchablage(lambda: kw), Bilder(), lambda: ls, lambda: TEXTMODELL,
                Nachtfenster(lambda: (22, 7), lambda: datetime(2026, 11, 8, 12, 0, tzinfo=ZONE)))
    auftraege.zurueckstellen_wenn(b.zurueckstellen)
    await b.starten()
    await auftraege.starten()
    yield b, auftraege, themen, kw, ls
    await auftraege.stoppen()


async def fertig(auftraege: Auftraege, kennung: str):
    for _ in range(600):
        a = await auftraege.holen(kennung)
        if a.zustand in ("fertig", "fehler", "abgebrochen"):
            assert a.zustand == "fertig", a.fehler
            return a
        await asyncio.sleep(0.01)
    raise AssertionError("nicht fertig")


async def test_probekapitel_mit_neuschreiben(dienst):
    b, auftraege, themen, kw, ls = dienst
    bestellung = Bestellung(thema="t1", vorlage="lernheft", pdf=False, wann="jetzt")
    await fertig(auftraege, (await b.probe_anstossen("k", "Probe", Probewunsch(bestellung=bestellung))).id)
    p = await b.probe("k", "t1")
    assert p.eintrag == "e1" and [o.nr for o in p.original] == [1, 2, 3, 4, 5] and p.original[2].ueberschrift == "Umlaufbahn"
    assert p.artikel.blick.punkte and p.kapitel.fragen[0].frage.startswith("Wie lange")
    assert p.artikel.absaetze[0].ohne_beleg == [ERFUNDEN] and [h.art for h in p.pruefung.hinweise] == ["satz"]
    assert p.artikel.absaetze[2].notizen[0].text == "Mit dem Fernrohr sehen"                  # an ihrer Stelle
    assert p.artikel.absaetze[1].hervorgehoben                                               # gemerkte Stelle
    assert all(o.get("prioritaet") is None for _, o in ls.aufrufe)                          # wer wartet, geht nicht hinten an
    await fertig(auftraege, (await b.probe_anstossen("k", "Probe", Probewunsch(bestellung=bestellung, neu=[{"absatz": 0}]))).id)
    p = await b.probe("k", "t1")
    assert ERFUNDEN not in p.artikel.absaetze[0].text and p.pruefung.hinweise == []
    vorher = len(ls.aufrufe)
    await fertig(auftraege, (await b.bestellen("k", "Probe", bestellung)).id)
    regal = await b.regal("k")
    assert ERFUNDEN not in json.dumps([h.text for h in regal.fertig[0].hinweise], ensure_ascii=False)   # neu Geschriebenes gilt
    assert [n for n, _ in ls.aufrufe[vorher:]].count("umformung") == 1                     # Saturn kam aus dem Zwischenspeicher


async def test_bauen_regal_und_nachbau_nur_des_neuen(dienst):
    b, auftraege, themen, kw, ls = dienst
    bestellung = Bestellung(thema="t1", vorlage="lernheft", pdf=False, wann="jetzt", steckbriefe=True)
    s = await b.schaetzen("k", bestellung)
    assert s.artikel == 2 and s.kapitel == 2 and s.probe_titel == "Saturn" and s.ende and not s.gemessen
    await fertig(auftraege, (await b.bestellen("k", "Probe", bestellung)).id)
    epub = kw.dateien["Apps/Nachschlag/Bücher/Sternenhimmel/Sternenhimmel - Lernheft.epub"]
    dateien = epub_pruefen(epub)
    kapitel = dateien["OEBPS/kapitel-01.xhtml"].decode()
    assert "Hier geht es um den Himmel." in kapitel and "Auf einen Blick" in kapitel and "<dt>Art</dt>" in kapitel
    glossar = dateien["OEBPS/glossar.xhtml"].decode()
    assert "Gasplanet" in glossar and "Erfunden" not in glossar                              # nur Begriffe aus dem Kapitel
    assert "Jemand" in dateien["OEBPS/quellen.xhtml"].decode()                                # Urheber des großen Bilds
    regal = await b.regal("k")
    assert regal.laufend == [] and len(regal.fertig) == 1
    buch = regal.fertig[0]
    assert (buch.titel, buch.vorlage_titel, buch.artikel, buch.veraltet) == ("Sternenhimmel", "Lernheft", 2, None)
    assert [(h.art, h.artikel) for h in buch.hinweise] == [("satz", "Saturn"), ("zahl", "Monde")]   # Antwort ohne Beleg im Kapitel
    assert [f.format for f in buch.formate] == ["epub"]
    assert "Hier geht es um den Himmel." in (await b.leseansicht("k", buch.id)).html
    name, art, inhalt = await b.datei("k", buch.id, "epub")
    assert name == "Sternenhimmel - Lernheft.epub" and art == "application/epub+zip"

    aufrufe = len(ls.aufrufe)
    await fertig(auftraege, (await b.bestellen("k", "Probe", bestellung)).id)
    assert len(ls.aufrufe) == aufrufe                                                         # alles aus dem Zwischenspeicher

    themen.t.eintraege.append(eintrag("e2", "Mars", "b1", 1))
    veraltet = (await b.regal("k")).fertig[0].veraltet
    assert (veraltet.neu, veraltet.weg, veraltet.text) == (1, 0, "Thema geändert: 1 neuer Artikel") and veraltet.sekunden > 0
    await fertig(auftraege, (await b.nachbauen("k", "Probe", buch.id, "jetzt")).id)
    neu = [n for n, _ in ls.aufrufe[aufrufe:]]
    assert neu.count("umformung") == 1 and neu.count("artikelteile") == 1                     # nur Mars ging ans Modell
    assert (await b.regal("k")).fertig[0].veraltet is None


async def test_heute_nacht_wartet_und_nachschlagewerk_ohne_ki(dienst):
    b, auftraege, themen, kw, ls = dienst
    a = await b.bestellen("k", "Probe", Bestellung(thema="t1", vorlage="nachschlagewerk", pdf=False, wann="nachts"))
    await asyncio.sleep(0.05)
    regal = await b.regal("k")
    assert regal.laufend[0].zustand == "wartet" and regal.laufend[0].grund == "wartet auf die Nacht (22 bis 7 Uhr)"
    await auftraege.abbrechen(a.id)
    await fertig(auftraege, (await b.bestellen("k", "Probe", Bestellung(thema="t1", vorlage="nachschlagewerk", pdf=False,
                                                                         wann="jetzt"))).id)
    assert ls.aufrufe == []                                                                   # ohne KI
    dateien = epub_pruefen(kw.dateien["Apps/Nachschlag/Bücher/Sternenhimmel/Sternenhimmel - Nachschlagewerk.epub"])
    assert sorted(n for n in dateien if n.startswith("OEBPS/kapitel")) == ["OEBPS/kapitel-01.xhtml", "OEBPS/kapitel-02.xhtml"]
    m = dateien["OEBPS/kapitel-01.xhtml"].decode()
    assert "<h1>M</h1>" in m and "<td>95 Erdmassen</td>" not in m                            # von A bis Z
    s = dateien["OEBPS/kapitel-02.xhtml"].decode()
    assert "<h1>S</h1>" in s and "<td>95 Erdmassen</td>" in s and "<mark>keine feste Oberfläche</mark>" in s
    assert "Saturn. In: Probe-Wiki" in dateien["OEBPS/literatur.xhtml"].decode()


async def test_ohne_leitstelle_keine_ki_vorlage(db):
    auftraege = Auftraege(db, [], gleichzeitig=1)
    b = Buecher(db, auftraege, Themen(), Bib(), Leser(), Uebersetzer(), None, None, Vorlagen(lambda: None),  # type: ignore[arg-type]
                Buchablage(lambda: None), Bilder(), lambda: None, lambda: TEXTMODELL, Nachtfenster(lambda: (22, 7)))
    await b.starten()
    with pytest.raises(ValueError, match="Leitstelle"):
        await b.bestellen("k", "Probe", Bestellung(thema="t1", vorlage="lernheft"))
    with pytest.raises(LookupError):
        await b.bestellen("k", "Probe", Bestellung(thema="t1", vorlage="gibt-es-nicht"))
