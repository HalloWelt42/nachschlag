"""Bücherlader (WIKI-57): Verzeichnisseiten und Katalog lesen, Durchgänge mit Erstaufnahme und Neuigkeiten, Abos mit
Laden (fortsetzbar, Prüfsumme, Reserve), Warten aufs Umschalten, Rückfall und Aufräumen nach der Frist, Liste für den
Bücherserver. Das Verzeichnis ist ein nachgestellter Webserver; die Bücher kommen aus dem Schreiber von libzim."""

from __future__ import annotations

import asyncio
import hashlib
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
from app.modell.buecherlader import Katalogfilter  # noqa: E402
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


FEED = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Probelexikon</title><summary>Buch für die Tests</summary><articleCount>9</articleCount>
<link rel="http://opds-spec.org/acquisition/open-access" type="application/x-zim"
      href="https://lb.test/zim/probe/probe_de_all_2026-10.zim.meta4"/></entry>
<entry><title>Ohne Datei</title></entry></feed>"""


def test_katalog_ordnet_ueber_den_dateinamen_zu():
    k = eintraege_aus(FEED)
    assert list(k) == ["probe_de_all"] and k["probe_de_all"].titel == "Probelexikon" and k["probe_de_all"].eintraege == 9


class Server:
    """Verzeichnis, Prüfsummen und Katalog; zählt Anfragen mit Bereich (Fortsetzen)."""

    def __init__(self, quelle: Path) -> None:
        self.dateien: dict[str, bytes] = {}          # Bereich/Datei -> Inhalt
        self.summen: dict[str, str] = {}
        self.bereiche: list[tuple[str, str]] = []    # (Bereich/Datei, Größe in der Liste)
        self.fortgesetzt: list[str] = []
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
    werte = dict(ordner=buecher, verzeichnis=VERZEICHNIS, pruefsummen=SUMMEN, katalog=KATALOG,
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
    assert abo.rueckfall.entfernt_ab == "2026-11-21"
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
