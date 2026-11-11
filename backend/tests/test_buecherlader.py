"""Bücherlader (WIKI-57): Verzeichnisseiten und Katalog lesen, Durchgänge mit Erstaufnahme und Neuigkeiten, Abos mit
Laden (fortsetzbar, Prüfsumme, Reserve), Warten aufs Umschalten, Rückfall und Aufräumen nach der Frist, Liste für den
Bücherserver. Das Verzeichnis ist ein nachgestellter Webserver; die Bücher kommen aus dem Schreiber von libzim."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from appkern.auftraege import Auftraege
from appkern.datenbank import Datenbank

sys.path.insert(0, str(Path(__file__).parent))
import buch as probebuch  # noqa: E402

from app.buecherlader import Buecherlader, LaderFehler, Regeln  # noqa: E402
from app.zeitfenster import ZONE  # noqa: E402
from app.modell.buecherlader import Katalogfilter, NeueQuelle, QuellAenderung  # noqa: E402
from app.buecherlader.bibliotheksliste import Bibliotheksliste  # noqa: E402
from app.buecherlader.katalog import eintraege_aus  # noqa: E402
from app.buecherlader.verzeichnis import basis_und_ausgabe, dateien_aus, neueste, ordner_aus, zerlegen  # noqa: E402

VERZEICHNIS = "http://spiegel.test/zim/"
SUMMEN = "http://quelle.test/zim/"
KATALOG = "http://katalog.test/catalog/v2"


def zeile(name: str, groesse: str = "1.2G", datum: str = "2026-10-02 18:05") -> str:
    return f'<img src="/icons/x.gif" alt="[ ]"> <a href="{name}">{name}</a>   {datum}  {groesse}  \n'


def seite(*zeilen: str) -> str:
    return ('<html><body><pre><a href="?C=N;O=D">Name</a> <a href="?C=M;O=A">Last modified</a>\n'
            '<a href="/kiwix/">Parent Directory</a>                             -   \n' + "".join(zeilen) + "</pre></body></html>")


def test_stand_auch_tagesgenau():
    """Eigene Bücher kommen auch mehrmals im Monat (WIKI-87): der Stand darf einen Tag tragen und ordnet sich als Text."""
    assert zerlegen("dateiformate_de_all_2026-11-12.zim").stand == "2026-11-12"
    assert zerlegen("wikipedia_de_all_maxi_2026-10.zim").stand == "2026-10"
    assert "2026-11" < "2026-11-12" < "2026-12"


def test_verzeichnisseite_lesen():
    wurzel = seite(zeile("wikipedia/", "-"), zeile("stack_exchange/", "-"))
    assert ordner_aus(wurzel) == ["wikipedia", "stack_exchange"]
    html = seite(zeile("wikipedia_de_all_maxi_2026-01.zim", "49G"), zeile("wikipedia_de_all_maxi_2026-10.zim", "45G"),
                 zeile("wikipedia_en_all_nopic_2026-06.zim", "490M"), zeile("liesmich.txt", "1K"))
    dateien = dateien_aus("wikipedia", html)
    assert [(d.stamm, d.sprache, d.stand) for d in dateien] == [
        ("wikipedia_de_all_maxi", "de", "2026-01"), ("wikipedia_de_all_maxi", "de", "2026-10"),
        ("wikipedia_en_all_nopic", "en", "2026-06")]
    assert dateien[1].groesse == 45 * 1024**3 and dateien[2].groesse == 490 * 1024**2
    assert neueste(dateien)["wikipedia_de_all_maxi"].stand == "2026-10"
    assert zerlegen("stackoverflow.com_en_all_2026-07.zim").sprache == "en"
    assert zerlegen("ohne_stand.zim") is None
    assert basis_und_ausgabe("wikipedia_de_all_mini") == ("wikipedia_de_all", "mini")
    assert basis_und_ausgabe("devdocs_en_php") == ("devdocs_en_php", "")


FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/terms/">
<entry><title>Probelexikon</title><summary>Buch für die Tests</summary><articleCount>9</articleCount><mediaCount>2</mediaCount>
<tags>lexikon;tiere;_category:wikipedia;_pictures:yes;_videos:no;_ftindex:yes</tags>
<author><name>Tests</name></author><publisher><name>openZIM</name></publisher><dc:issued>2026-10-02T00:00:00Z</dc:issued>
<link rel="http://opds-spec.org/acquisition/open-access" type="application/x-zim" length="4096"
      href="https://lb.test/zim/probe/probe_de_all_2026-10.zim.meta4"/></entry>
<entry><title>Ohne Datei</title></entry></feed>"""


def test_katalog_mit_angaben():
    [e] = eintraege_aus(FEED)
    assert (e.ordner, e.stamm, e.stand, e.groesse) == ("probe", "probe_de_all", "2026-10", 4096)
    a = e.angaben
    assert (a.titel, a.artikel, a.medien, a.autor, a.herausgeber, a.kategorie) == ("Probelexikon", 9, 2, "Tests", "openZIM", "wikipedia")
    assert a.schlagworte == ["lexikon", "tiere"] and a.bilder is True and a.videos is False and a.volltext is True
    assert a.datum == "2026-10-02"


def test_verzeichnisse_aller_spiegel():
    """Apache als Text, lighttpd mit span und GiB, nginx als Text (WIKI-62)."""
    lighttpd = ('<tr><td class="link"><span href="wikivoyage/" title="wikivoyage">wikivoyage/</span></td><td class="size">-</td></tr>'
                '<tr><td class="link"><span href="w_de_all_maxi_2026-10.zim">w_de_all_maxi_2026-10.zim</span></td>'
                '<td class="size">1.2 GiB</td><td class="date">2026-10-13 07:09:58</td></tr>')
    nginx = ('<a href="../">../</a>\n<a href="wikivoyage/">wikivoyage/</a>   01-Nov-2026 17:05  -\n'
             '<a href="w_de_all_maxi_2026-10.zim">w_de_all_maxi_2026-10.zim</a>   13-Oct-2026 01:09   1G\n')
    for html in (lighttpd, nginx):
        assert ordner_aus(html) == ["wikivoyage"]
        [d] = dateien_aus("wikivoyage", html)
        assert d.stamm == "w_de_all_maxi" and d.groesse in (int(1.2 * 1024**3), 1024**3)


def test_vereinigung_und_ladedatei():
    from app.buecherlader.katalog import ladedatei_aus
    from app.buecherlader.quellen import Ergebnis, Fund, Katalogquelle, Verzeichnisquelle, vereinigen
    from app.modell.buecherlader import Angaben
    k, s1, s2 = Katalogquelle(1, "K", "http://k"), Verzeichnisquelle(2, "S1", "http://s1/"), Verzeichnisquelle(3, "S2", "http://s2/")
    f = lambda adresse, groesse, angaben=None, stand="2026-10": Fund("p", f"p_de_all_{stand}.zim", "p_de_all", "de", stand,  # noqa: E731
                                                                     groesse, adresse, "", angaben)
    vereint = vereinigen([(s1, Ergebnis([f("http://s1/p", 1000), f("http://s1/alt", 900, stand="2026-01")])),
                          (k, Ergebnis([f("http://k/p", 1234, Angaben(titel="P", kategorie="x"))])),
                          (s2, Ergebnis([f("http://s2/p", 0)]))])
    neu = next(v for v in vereint if v.stand == "2026-10")
    assert [b.quelle for b in neu.bezuege] == [1, 2, 3] and neu.groesse == 1234 and neu.angaben.titel == "P"
    assert len(vereint) == 2                                       # der ältere Stand nur aus einer Quelle
    meta4 = """<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="p.zim">
      <hash type="sha-256">""" + "a" * 64 + """</hash>
      <url location="se" priority="2">https://s2/p_de_all_2026-10.zim</url><url location="de" priority="1">https://s1/p_de_all_2026-10.zim</url>
    </file></metalink>"""
    l = ladedatei_aus(meta4)
    assert l.sha256 == "a" * 64 and l.spiegel == [("https://s1/p_de_all_2026-10.zim", "de"), ("https://s2/p_de_all_2026-10.zim", "se")]


class Server:
    """Verzeichnis, Prüfsummen und Katalog; zählt Anfragen mit Bereich (Fortsetzen)."""

    def __init__(self, quelle: Path) -> None:
        self.dateien: dict[str, bytes] = {}          # Bereich/Datei -> Inhalt
        self.summen: dict[str, str] = {}
        self.bereiche: list[tuple[str, str]] = []    # (Bereich/Datei, Größe in der Liste)
        self.fortgesetzt: list[str] = []
        self.mit_ladedatei = False                   # Ladedateien (meta4) bei der Quelle der Prüfsummen
        self.quelle = quelle

    def anbieten(self, bereich: str, datei: Path, falsche_summe: bool = False) -> None:
        inhalt = datei.read_bytes()
        pfad = f"{bereich}/{datei.name}"
        self.dateien[pfad] = inhalt
        self.summen[pfad] = "0" * 64 if falsche_summe else hashlib.sha256(inhalt).hexdigest()
        self.bereiche.append((pfad, f"{max(1, len(inhalt) // 1024)}K"))

    def listen(self, bereich: str, dateien: list[str]) -> None:
        """Nur in der Liste (für die Sprachfilter), nie geladen."""
        self.bereiche += [(f"{bereich}/{d}", "3M") for d in dateien]

    def __call__(self, anfrage: httpx.Request) -> httpx.Response:
        url = str(anfrage.url)
        if url == VERZEICHNIS:
            return httpx.Response(200, text=seite(*(zeile(b + "/", "-") for b in sorted({p.split("/")[0] for p, _ in self.bereiche}))))
        if url.startswith(VERZEICHNIS) and url.endswith("/"):
            bereich = url[len(VERZEICHNIS):-1]
            return httpx.Response(200, text=seite(*(zeile(p.split("/")[1], g) for p, g in self.bereiche if p.startswith(bereich + "/"))))
        if url.startswith(SUMMEN) and url.endswith(".meta4") and self.mit_ladedatei:
            pfad = url[len(SUMMEN):-len(".meta4")]
            if pfad not in self.summen:
                return httpx.Response(404)
            return httpx.Response(200, text='<metalink xmlns="urn:ietf:params:xml:ns:metalink"><file name="x">'
                                            f'<hash type="sha-256">{self.summen[pfad]}</hash>'
                                            f'<url location="de" priority="1">{VERZEICHNIS}{pfad}</url></file></metalink>')
        if url.startswith(SUMMEN) and url.endswith(".sha256"):
            pfad = url[len(SUMMEN):-len(".sha256")]
            return httpx.Response(200, text=f"{self.summen[pfad]}  {pfad.split('/')[1]}\n") if pfad in self.summen else httpx.Response(404)
        if url.startswith(KATALOG):
            return httpx.Response(200, text=FEED)
        if url.startswith(VERZEICHNIS):
            inhalt = self.dateien[url[len(VERZEICHNIS):]]
            if anfrage.method == "HEAD":
                return httpx.Response(200, headers={"content-length": str(len(inhalt))})
            if bereich := anfrage.headers.get("range"):
                ab = int(bereich.removeprefix("bytes=").rstrip("-"))
                self.fortgesetzt.append(url)
                return httpx.Response(206, content=inhalt[ab:])
            return httpx.Response(200, content=inhalt)
        return httpx.Response(404)


class Uhr:
    def __init__(self) -> None:
        self.jetzt = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.jetzt


@pytest.fixture
async def umgebung(tmp_path: Path):
    """Ordner der Bücher mit der Fassung 2026-01 eines Probebuchs; im Verzeichnis dieselbe und eine neuere 2026-10."""
    buecher, quelle = tmp_path / "buecher", tmp_path / "quelle"
    probebuch.bauen(buecher, "probe_de_all_2026-01")
    server = Server(quelle)
    server.anbieten("probe", probebuch.bauen(quelle, "probe_de_all_2026-01"))
    server.anbieten("probe", probebuch.bauen(quelle, "probe_de_all_2026-10"))
    server.anbieten("probe", probebuch.bauen(quelle, "neues_de_all_2026-10"))
    server.listen("probe", ["fremd_fr_all_2026-10.zim", "andere_en_all_maxi_2026-09.zim", "andere_en_all_nopic_2026-09.zim"])
    werte = dict(ordner=buecher, pruefsummen=SUMMEN,
                 sprachen=frozenset({"de", "en"}), durchsicht="woechentlich", neue_fassung="laden", laden_wann="immer",
                 fenster=(22, 7), reserve=0, hoechstens=0, vorige_tage=14, liste=buecher / "library.xml")
    db = await Datenbank(tmp_path / "l.sqlite").oeffnen()
    auftraege = Auftraege(db, [])
    hand: set[str] = set()
    fundus: dict[str, set[str] | None] = {"dateien": set()}

    async def von_hand(kennung: str) -> bool:
        return kennung in hand

    async def in_gebrauch() -> set[str] | None:
        return fundus["dateien"]

    uhr = Uhr()
    lader = Buecherlader(db, auftraege, lambda: Regeln(**werte), von_hand, transport=httpx.MockTransport(server), uhr=uhr,
                        zeitplan=False, in_gebrauch=in_gebrauch)
    await lader.starten()
    await auftraege.starten()
    for q in await lader.quellen():                               # statt der echten Spiegel die nachgestellten (WIKI-62)
        await lader.quelle_entfernen(q.nr)
    await lader.quelle_anlegen(NeueQuelle(art="katalog", adresse=KATALOG, name="Katalog"))
    await lader.quelle_anlegen(NeueQuelle(art="verzeichnis", adresse=VERZEICHNIS, name="Spiegel"))
    lader.fundus = fundus                                          # für die Tests: was der Fundus noch liest
    yield lader, auftraege, server, werte, buecher, uhr, hand
    await auftraege.stoppen()
    await lader.stoppen()
    await db.schliessen()


async def fertig(auftraege: Auftraege, art: str | None = None):
    """Wartet, bis keine Aufträge mehr offen sind; liefert die beendeten (neueste zuerst)."""
    for _ in range(400):
        offen = (await auftraege.liste(zustand=("wartet", "laeuft"), art=art)).eintraege
        if not offen:
            return (await auftraege.liste(art=art)).eintraege
        await asyncio.sleep(0.02)
    raise AssertionError("Aufträge wurden nicht fertig")


async def test_durchgang_erstaufnahme_und_neues(umgebung):
    lader, auftraege, server, *_ = umgebung
    await lader.durchsehen("probe")
    [a] = await fertig(auftraege)
    assert a.zustand == "fertig" and a.ergebnis["erstaufnahme"] and a.ergebnis["neue_buecher"] == 0
    assert a.ergebnis["buecher"] == 4                            # fremd_fr fällt weg
    stand = await lader.stand()
    assert stand.neu_ungesehen == 0 and stand.letzter_durchgang.buecher == 4

    server.listen("probe", ["andere_en_all_maxi_2026-11.zim", "noch_de_all_2026-11.zim"])
    await lader.durchsehen("probe")
    await fertig(auftraege)
    stand = await lader.stand()
    assert stand.letzter_durchgang.neue_buecher == 1 and stand.letzter_durchgang.neue_fassungen == 1
    assert stand.neu_ungesehen == 2
    seite = await lader.verzeichnis(Katalogfilter(nur_neu=True))
    assert [b.basis for b in seite.eintraege] == ["andere_en_all", "noch_de_all"]
    andere = seite.eintraege[0]
    assert [(v.ausgabe, v.neu) for v in andere.varianten] == [("maxi", "fassung")]      # nur die neue Ausgabe
    alle = await lader.verzeichnis()
    probe = next(b for b in alle.eintraege if b.basis == "probe_de_all")
    assert probe.titel == "Probelexikon" and probe.varianten[0].zustand == "neuer_da" and alle.bereiche == ["probe"]
    assert probe.varianten[0].quellen == 2 and probe.angaben.kategorie == "wikipedia" and alle.kategorien == ["wikipedia"]
    assert [(q.name, q.funde > 0) for q in await lader.quellen()] == [("Katalog", True), ("Spiegel", True)]
    assert (await lader.verzeichnis(Katalogfilter(suche="tiere"))).eintraege[0].basis == "probe_de_all"   # Schlagwort
    await lader.gesehen()
    assert (await lader.stand()).neu_ungesehen == 0


async def test_abo_laedt_wartet_schaltet_um_und_raeumt_auf(umgebung):
    lader, auftraege, server, werte, buecher, uhr, hand = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    assert await lader.bestand_abonnieren("probe") == 1         # nur probe_de_all liegt in der Bibliothek
    laden = await fertig(auftraege, "buch_laden")
    assert [a.zustand for a in laden] == ["fertig"] and laden[0].ergebnis["ort"] == "wartet aufs Umschalten"
    assert (buecher / ".neu" / "probe_de_all_2026-10.zim").is_file()
    [abo] = (await lader.stand()).abos
    assert abo.zustand == "wartet_auf_umschalten" and abo.wartet == "probe_de_all_2026-10" and abo.lokal_stand == "2026-01"

    await lader.umschalten("probe_de_all")
    [abo] = (await lader.stand()).abos
    assert abo.zustand == "aktuell" and abo.rueckfall.kennung == "probe_de_all_2026-01"
    frist = (uhr.jetzt + timedelta(days=14)).astimezone(ZONE).date().isoformat()   # die Frist misst sich an der Uhr des Laders
    assert abo.rueckfall.entfernt_ab == frist
    assert "probe_de_all_2026-10.zim" in (buecher / "library.xml").read_text()

    await lader.zurueck("probe_de_all")
    [abo] = (await lader.stand()).abos
    assert abo.zustand == "wartet_auf_umschalten" and abo.lokal_stand == "2026-01" and abo.rueckfall is None
    assert "probe_de_all_2026-10.zim" not in (buecher / "library.xml").read_text()
    with pytest.raises(LaderFehler):
        await lader.zurueck("probe_de_all")

    await lader.umschalten("probe_de_all")
    hand.add("probe_de_all_2026-01")                            # von Hand aktiv: bleibt über die Frist
    uhr.jetzt += timedelta(days=15)
    await lader.takt()
    assert (buecher / "probe_de_all_2026-01.zim").is_file()
    assert (await lader.stand()).abos[0].rueckfall.bleibt == "von Hand wieder aktiv gesetzt"
    hand.clear()
    lader.fundus["dateien"] = {"probe_de_all_2026-01.zim"}       # der Fundus liest sie noch ein (WIKI-58)
    await lader.takt()
    assert (buecher / "probe_de_all_2026-01.zim").is_file()
    assert "liest sie noch ein" in (await lader.stand()).abos[0].rueckfall.bleibt
    lader.fundus["dateien"] = None                               # er antwortet nicht: nichts löschen
    await lader.takt()
    assert (buecher / "probe_de_all_2026-01.zim").is_file()
    lader.fundus["dateien"] = {"probe_de_all_2026-10.zim"}       # er ist auf die neue umgestiegen
    await lader.takt()
    assert not (buecher / "probe_de_all_2026-01.zim").is_file()
    assert (buecher / "probe_de_all_2026-10.zim").is_file() and (await lader.stand()).abos[0].rueckfall is None
    # der Zeitplan hat nach 15 Tagen auch wieder durchgesehen (je Takt höchstens eine Durchsicht zugleich)
    assert len(await fertig(auftraege, "verzeichnis_durchsehen")) >= 2


async def test_neues_buch_direkt_in_die_bibliothek_und_fortsetzen(umgebung):
    lader, auftraege, server, werte, buecher, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    inhalt = server.dateien["probe/neues_de_all_2026-10.zim"]
    (buecher / ".laden").mkdir()
    (buecher / ".laden" / "neues_de_all_2026-10.zim").write_bytes(inhalt[:1000])      # abgebrochen
    await lader.abonnieren("neues_de_all", "probe")
    [a] = await fertig(auftraege, "buch_laden")
    assert a.zustand == "fertig" and a.ergebnis["ort"] == "Bibliothek" and a.ergebnis["artikel"] > 0
    assert server.fortgesetzt == [VERZEICHNIS + "probe/neues_de_all_2026-10.zim"]
    assert (buecher / "neues_de_all_2026-10.zim").read_bytes() == inhalt
    assert "neues_de_all_2026-10.zim" in (buecher / "library.xml").read_text()
    with pytest.raises(LookupError):
        await lader.abonnieren("gibt_es_nicht", "probe")


async def test_reserve_und_pruefsumme(umgebung):
    lader, auftraege, server, werte, buecher, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    werte["reserve"] = 10**18                                   # nie genug frei
    await lader.abonnieren("neues_de_all", "probe")
    assert not (await auftraege.liste(art="buch_laden")).eintraege
    abo = next(a for a in (await lader.stand()).abos if a.stamm == "neues_de_all")
    assert abo.zustand == "nicht_da" and abo.laden is None
    # beim Laden selbst greift die Reserve auch (etwa wenn sie nach dem Einreihen steigt)
    await auftraege.einreihen("buch_laden", {"stamm": "neues_de_all", "ordner": "probe", "datei": "neues_de_all_2026-10.zim"})
    [a] = await fertig(auftraege, "buch_laden")
    assert a.zustand == "fehler" and a.fehler.startswith("Zu wenig Platz")
    await auftraege.entfernen(a.id)
    werte["reserve"] = 0
    await lader.abbestellen("neues_de_all")
    server.summen["probe/neues_de_all_2026-10.zim"] = "0" * 64
    await lader.abonnieren("neues_de_all", "probe")
    [a] = await fertig(auftraege, "buch_laden")
    assert a.zustand == "fehler" and "Prüfsumme stimmt nicht" in a.fehler
    assert not (buecher / ".laden" / "neues_de_all_2026-10.zim").exists()


async def test_nur_nachts_stellt_zurueck(umgebung):
    lader, auftraege, server, werte, *_ = umgebung
    werte["laden_wann"] = "nachts"
    auftraege.zurueckstellen_wenn(lader.zurueckstellen)
    await lader.durchsehen("probe")
    await fertig(auftraege, "verzeichnis_durchsehen")
    await lader.abonnieren("neues_de_all", "probe")
    [abo] = [a for a in (await lader.stand()).abos if a.stamm == "neues_de_all"]
    assert abo.zustand == "laedt" and abo.laden.zustand == "wartet"
    assert abo.laden.zurueckgestellt == "lädt nur nachts (22 bis 7 Uhr)"   # 12 Uhr UTC ist 13 Uhr Ortszeit
    a = (await auftraege.liste(art="buch_laden")).eintraege[0]
    await auftraege.abbrechen(a.id)


def test_bibliotheksliste_ersetzt_und_traegt_aus(tmp_path: Path):
    datei = probebuch.bauen(tmp_path, "probe_de_all_2026-10")
    liste = Bibliotheksliste(tmp_path / "library.xml")
    (tmp_path / "library.xml").write_text('<library version="20110515">\n  <book id="a" path="anderes.zim" title="X"/>\n</library>')
    liste.eintragen(datei)
    liste.eintragen(datei)
    text = (tmp_path / "library.xml").read_text()
    assert text.count('path="probe_de_all_2026-10.zim"') == 1 and 'path="anderes.zim"' in text
    assert 'name="probe_de_all"' in text and 'language="deu"' in text
    liste.austragen("probe_de_all_2026-10.zim")
    assert "probe_de_all" not in (tmp_path / "library.xml").read_text()


async def test_einstellung_mit_stand_folgt_der_juengsten_fassung(tmp_path: Path):
    """Die Quelle der Bedeutungssuche nennt eine Datei mit Stand; nach dem Umschalten gilt die neue (WIKI-58)."""
    from app.bibliothek import Bibliothek
    for name in ("probe_de_all_2026-01", "probe_de_all_2026-10", "probedoku_en_php_2026-12"):
        probebuch.bauen(tmp_path, name)
    bib = Bibliothek(lambda: str(tmp_path))
    assert await bib.juengste_fassung("probe_de_all_2026-01") == "probe_de_all_2026-10"
    assert await bib.juengste_fassung("gibt_es_nicht_2026-01") == "gibt_es_nicht_2026-01"
    assert await bib.juengste_fassung("ohne_stand") == "ohne_stand"


async def test_katalogfilter(umgebung):
    """Sprache, Ausgabe, Größe, Stand zur Bibliothek und Sortierung (WIKI-61)."""
    lader, auftraege, server, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    alle = await lader.verzeichnis()
    assert alle.sprachen == ["de", "en"] and alle.gesamt == 3
    englisch = await lader.verzeichnis(Katalogfilter(sprache="en"))
    assert [b.basis for b in englisch.eintraege] == ["andere_en_all"]
    ohne_bilder = await lader.verzeichnis(Katalogfilter(ausgabe="nopic"))
    assert [[v.ausgabe for v in b.varianten] for b in ohne_bilder.eintraege] == [["nopic"]]   # nur die passende Ausgabe
    assert {b.basis for b in (await lader.verzeichnis(Katalogfilter(ausgabe="einzeln"))).eintraege} == {"probe_de_all", "neues_de_all"}
    da = await lader.verzeichnis(Katalogfilter(bibliothek="da"))
    assert [b.basis for b in da.eintraege] == ["probe_de_all"] and da.eintraege[0].varianten[0].zustand == "neuer_da"
    assert [b.basis for b in (await lader.verzeichnis(Katalogfilter(bibliothek="neuer_da"))).eintraege] == ["probe_de_all"]
    assert (await lader.verzeichnis(Katalogfilter(groesse_bis=1))).gesamt == 0
    neueste = await lader.verzeichnis(Katalogfilter(sortierung="neueste"))
    assert neueste.eintraege[-1].basis == "andere_en_all"                 # 2026-09 hinter 2026-10


async def test_spiegel_bittet_um_geduld(monkeypatch):
    """429 mit Retry-After: warten und erneut fragen (WIKI-62)."""
    from app.buecherlader import quellen
    antworten = iter([httpx.Response(429, headers={"retry-after": "0"}), httpx.Response(503), httpx.Response(200, text="da")])
    async def schlafen(_s):
        return None
    monkeypatch.setattr(quellen.asyncio, "sleep", schlafen)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _r: next(antworten))) as c:
        assert await quellen._text(c, "http://s/") == "da"


async def test_laden_ohne_bezugsquellen_ueber_die_ladedatei(umgebung):
    """Ein Auftrag aus der Zeit vor den Quellen (keine Bezugsquellen in der Datenbank): Prüfsumme und Spiegel kommen aus
    der Ladedatei der Quelle der Prüfsummen (WIKI-62)."""
    lader, auftraege, server, werte, buecher, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    for q in await lader.quellen():                                # keine Quelle nennt die Datei mehr
        await lader.quelle_aendern(q.nr, QuellAenderung(an=False))
    await lader.quelle_aendern((await lader.quellen())[0].nr, QuellAenderung(an=True))   # bereit, aber ohne Bezug
    await lader._bestand._db.ausfuehren("DELETE FROM buecherlader_bezug")
    server.mit_ladedatei = True
    # der Auftrag kennt aus seinem ersten Lauf nur die Prüfsumme (so standen die Aufträge beim Umstieg auf die Quellen)
    werte["laden_wann"] = "nachts"
    auftraege.zurueckstellen_wenn(lader.zurueckstellen)
    a = await auftraege.einreihen("buch_laden", {"stamm": "neues_de_all", "ordner": "probe", "datei": "neues_de_all_2026-10.zim"})
    soll = server.summen["probe/neues_de_all_2026-10.zim"]
    await lader._bestand._db.ausfuehren("UPDATE auftrag SET zwischenstand=? WHERE id=?", (json.dumps({"soll": soll}), a.id))
    werte["laden_wann"] = "immer"
    auftraege.wecken()
    [a] = await fertig(auftraege, "buch_laden")
    assert a.zustand == "fertig", a.fehler
    assert (buecher / "neues_de_all_2026-10.zim").is_file()


async def test_ungelesene_quelle_macht_die_durchsicht_faellig(umgebung):
    """Kam eine Quelle nach der letzten Durchsicht dazu (oder alle, wie bei der Umstellung auf Quellen), sieht der
    Zeitplan sofort durch statt nach einer Woche; danach kennt der Ladeauftrag ihre Bezüge (WIKI-72)."""
    lader, auftraege, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    await lader.takt()
    assert len(await fertig(auftraege, "verzeichnis_durchsehen")) == 1          # alle gelesen, Woche nicht um: nichts
    spiegel = next(q for q in await lader.quellen() if q.adresse == VERZEICHNIS)
    await lader.quelle_entfernen(spiegel.nr)                                     # wieder angelegt: noch nie gelesen
    await lader.quelle_anlegen(NeueQuelle(art="verzeichnis", adresse=VERZEICHNIS, name="Spiegel"))
    await lader.takt()
    assert len(await fertig(auftraege, "verzeichnis_durchsehen")) == 2          # die neue: gleich durchgesehen
    assert all(q.zuletzt for q in await lader.quellen())
    await lader.takt()
    assert len(await fertig(auftraege, "verzeichnis_durchsehen")) == 2          # und dann wieder Ruhe


async def test_kein_doppeltes_laden_und_erledigte_fehler_weg(umgebung):
    """WIKI-73: ein zweiter Auftrag an derselben Datei lädt sie nicht noch einmal (sie liegt schon da), und der fertige
    räumt den alten Fehler derselben Datei aus der Liste."""
    lader, auftraege, server, werte, buecher, *_ = umgebung
    await lader.durchsehen("probe")
    await fertig(auftraege)
    eingabe = {"stamm": "neues_de_all", "ordner": "probe", "datei": "neues_de_all_2026-10.zim"}
    werte["reserve"] = 10**18                                   # erst scheitert er am Platz
    alt = await auftraege.einreihen("buch_laden", eingabe)
    await fertig(auftraege, "buch_laden")
    assert (await auftraege.holen(alt.id)).zustand == "fehler"
    werte["reserve"] = 0
    neu = await auftraege.wiederholen(alt.id)
    await fertig(auftraege, "buch_laden")
    assert (await auftraege.holen(neu.id)).ergebnis["ort"] == "Bibliothek"
    assert [a.id for a in (await auftraege.liste(art="buch_laden")).eintraege] == [neu.id]    # der Fehler ist weg
    noch = await auftraege.einreihen("buch_laden", eingabe)     # noch einmal: liegt schon da, nichts geladen
    await fertig(auftraege, "buch_laden")
    assert (await auftraege.holen(noch.id)).ergebnis["ort"] == "Bibliothek (lag schon da)"


async def test_buch_loeschen(umgebung):
    """WIKI-77: ein Buch ganz löschen. Bleibt keine Fassung, endet das Abo und der Index darf mit; liest der Fundus es
    gerade ein, bleibt es; ein unbekanntes gibt es nicht."""
    lader, auftraege, server, werte, buecher, *_ = umgebung
    geloescht: list[tuple[str, bool]] = []

    async def nach(kennung: str, letzte: bool) -> None:
        geloescht.append((kennung, letzte))

    lader._nach_loeschen = nach
    await lader.durchsehen("probe")
    await fertig(auftraege)
    await lader.abonnieren("probe_de_all", "probe")               # lädt 2026-10 neben 2026-01 (wartet aufs Umschalten)
    await fertig(auftraege, "buch_laden")
    assert (buecher / ".neu" / "probe_de_all_2026-10.zim").is_file()
    lader.fundus["dateien"] = {"probe_de_all_2026-01.zim"}
    with pytest.raises(LaderFehler):
        await lader.loeschen("probe_de_all_2026-01")
    lader.fundus["dateien"] = set()
    g = await lader.loeschen("probe_de_all_2026-01")               # die wartende bleibt: Abo bleibt, Index bleibt Vorlage
    assert not (buecher / "probe_de_all_2026-01.zim").exists() and g.groesse > 0 and not g.abo_beendet
    assert geloescht == [("probe_de_all_2026-01", False)] and "probe_de_all" in await lader._bestand.abos()
    g = await lader.loeschen("probe_de_all_2026-10")               # die letzte Fassung: Abo endet, Index darf mit
    assert g.abo_beendet and geloescht[-1] == ("probe_de_all_2026-10", True)
    assert "probe_de_all" not in await lader._bestand.abos() and not (buecher / ".neu" / "probe_de_all_2026-10.zim").exists()
    with pytest.raises(LookupError):
        await lader.loeschen("probe_de_all_2026-10")


async def test_eigene_buecher_aus_einem_ordner(umgebung, tmp_path: Path):
    """WIKI-87: ein Ordner auf dem Rechner der App als Quelle (Bereich je Unterordner, Prüfsumme daneben); das Buch
    lädt wie jedes andere, ohne Prüfsumme lädt nichts, ein falscher Pfad fällt beim Anlegen auf."""
    import hashlib
    lader, auftraege, server, werte, buecher, *_ = umgebung
    eigene = tmp_path / "eigene"
    datei = probebuch.bauen(eigene / "other", "eigenes_de_all_2026-11")
    with pytest.raises(LaderFehler):
        await lader.quelle_anlegen(NeueQuelle(art="ordner", adresse=str(tmp_path / "fehlt"), name="Eigene"))
    await lader.quelle_anlegen(NeueQuelle(art="ordner", adresse=str(eigene), name="Eigene Bücher"))
    await lader.durchsehen("probe")
    await fertig(auftraege)
    assert any(q.art == "ordner" and q.funde == 1 for q in await lader.quellen())

    await lader.abonnieren("eigenes_de_all", "other")
    [a] = await fertig(auftraege, "buch_laden")
    assert a.zustand == "fehler" and "Keine Prüfsumme" in a.fehler

    Path(str(datei) + ".sha256").write_text(f"{hashlib.sha256(datei.read_bytes()).hexdigest()}  {datei.name}\n")
    await auftraege.wiederholen(a.id)
    laden = await fertig(auftraege, "buch_laden")
    assert laden[0].zustand == "fertig" and laden[0].ergebnis["ort"] == "Bibliothek"
    assert (buecher / "eigenes_de_all_2026-11.zim").read_bytes() == datei.read_bytes()
    assert "eigenes_de_all_2026-11.zim" in (buecher / "library.xml").read_text()
