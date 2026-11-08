"""Nachschlag: liest jedes Buch der Bibliothek. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port 8711
"""

import os
from pathlib import Path
from typing import get_args

import httpx
from fastapi import FastAPI

from appkern.app import Geruest
from appkern.einstellungen import Angebot, Option
from appkern.leitstelle import LeitstellenFehler
from appkern.verbund import VerbundFehler

from .anleitungen.api import router as anleitungen_router
from .mcp.api import router as mcp_router
from .mcp.werkzeuge import werkzeuge as mcp_werkzeuge
from .anleitungen.dienst import Anleitungen
from .api import router
from .artikel import Artikelleser, wege
from .bibliothek import Bibliothek
from .buecherlader import Buecherlader, Regeln as Laderregeln
from .bilder import Grossbilder
from .bilder.api import router as bilder_router
from .buecherlader.api import router as buecherlader_router
from .eigenindex.ablage import Eigenindizes
from .eigenindex.api import router as indexdienst_router
from .eigenindex.auftrag import Indexauftraege
from .einstellungen import ARTEN_JE_STUFE, AppEinstellungen
from .kategorien import schema as kategorienschema
from .kategorien.abfrage import Kategorienindex
from .kategorien.api import router as kategorien_router
from .kategorien.wikis import wiki
from bildholer.modelle import Regeln as Bildregeln
from .markdownablage import Markdownablage
from .themen.ordnen import ThemenOrdner
from .meins import Meins
from .meins.api import inhalt_router as notizbilder_router
from .meins.api import router as meins_router
from .meins.bilder import Notizbilder
from .register import Register
from .korrektur import Korrektor
from .korrektur.api import router as korrektur_router
from .sprache.api import router as sprache_router
from .uebersetzung import Artikeluebersetzer, Stellenuebersetzer, Uebersetzer
from .uebersetzung.api import router as uebersetzung_router
from .vorlesen import NichtBereit, Sprechdienst
from .vorlesen.stimmen import PRIVAT, Stimmenquelle
from .vorlesen.api import router as vorlesen_router
from .register.api import router as register_router
from .medien import Medien
from .medien.api import router as medien_router
from .stoebern import Stoebern
from .quellenarchiv import Quellenarchiv
from .sammlung import Sammlungen
from .ausprobieren import Ausprobieren
from .ausprobieren.api import router as ausprobieren_router
from .sammlung.api import router as sammlung_router
from .quellenarchiv.api import router as quellenarchiv_router
from .stoebern.api import router as stoebern_router
from .themen import Themen
from .themen.api import router as themen_router
from .zitieren.api import router as zitieren_router
from .fassung import FASSUNG, WURZEL
from .modell.buch import Art as Buchart
from .modell.suche import Suchregeln
from .suche import Suche
from .suche.anbindung import Bedeutungsanbindung
from .suche.bedeutung import FundusBedeutung


def app_bauen(daten: Path, transport: httpx.AsyncBaseTransport | None = None,
              lader_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """`transport` nur für Tests (Kellerwolke, Leitstelle und Fundus nachgestellt); der Bücherlader nimmt ihn mit, außer
    `lader_transport` ist gesetzt (der Probebetrieb stellt nur die Kellerwolke nach und liest das echte Verzeichnis)."""
    geruest = Geruest(name="Nachschlag", kennung="nachschlag", rolle="liest jede Quelle der Bibliothek", symbol="fa-book-open", symbolbild="/favicon.svg",
                      farbe="#08758b", fassung=FASSUNG, daten=daten, einstellungen=AppEinstellungen,
                      oberflaeche=WURZEL / "frontend" / "dist", transport=transport,
                      gleichzeitig=3)                    # Indexbau, Übersetzungen und Sammlungen nebeneinander, je Art höchstens einer
    e = lambda: geruest.einstellungen.stand  # noqa: E731

    bibliothek = Bibliothek(lambda: e().buecher_ordner)
    # Kategorien aus den Datenabzügen von Wikimedia (WIKI-75): je Buch eine Datei im Unterordner der eigenen Indizes
    kategorienablage = Eigenindizes(lambda: str(Path(e().eigenindex_ordner) / "kategorien") if e().eigenindex_ordner else "",
                                    gueltig=kategorienschema.gueltig)
    kategorien = Kategorienindex(kategorienablage)
    leser = Artikelleser(bibliothek, kategorien)
    async def buchkennungen() -> list[str]:
        return [b.kennung for b in (await bibliothek.stand()).buecher]

    # welche Sammlung und welches Buch gelten: gewählt oder von selbst gefunden (WIKI-56)
    anbindung = Bedeutungsanbindung(lambda: geruest.verbund, lambda: e().fundus_adresse, lambda: e().fundus_sammlung,
                                    lambda: e().bedeutung_buch, buchkennungen, bibliothek.juengste_fassung)
    geruest.begleiter_anmelden(anbindung)
    bedeutung = FundusBedeutung(lambda: geruest.verbund, lambda: e().fundus_adresse, anbindung.sammlung,
                                lambda: e().fundus_vorsilbe)
    eigen = Eigenindizes(lambda: e().eigenindex_ordner)
    quellen = Quellenarchiv(geruest.db, bibliothek)           # Archiv der Quellen (WIKI-46)
    geruest.begleiter_anmelden(quellen)
    async def bedeutungsbuch() -> str:
        """Die Quelle der Bedeutungssuche in ihrer jüngsten Fassung (die Einstellung nennt eine Datei mit Stand)."""
        return await anbindung.buch()

    async def vorgewaehlte_buecher() -> list[str]:
        """Einstellung Bücher in der Suche (Namen, über Fassungen hinweg) als Kennungen der jüngsten Fassung (WIKI-79)."""
        return [k for name in e().suche_buecher if (k := await bibliothek.kennung_von(name))]

    suche = Suche(bibliothek, bedeutung, lambda: e().bedeutung_warten_s, bedeutungsbuch,
                  wege(bibliothek).medien, eigen, nutzbare=quellen.nutzbare, mischung=lambda: e().mischung,
                  vorgewaehlt=vorgewaehlte_buecher)
    indexauftraege = Indexauftraege(eigen, bibliothek, geruest.auftraege, lambda: e().indexdienst_schluessel.get_secret_value(),
                                    lambda: ARTEN_JE_STUFE[e().eigene_indizes], lambda: e().eigenindex_hoechstens_gb,
                                    nutzbare=quellen.nutzbare)

    stimmenquelle = Stimmenquelle(geruest, lambda: e().vertonung_adresse)      # eigene Stimmen: nur die Probe
    sprechdienst = Sprechdienst(lambda: geruest.leitstelle, lambda: e().sprechdienst, lambda: e().vorlesestimme,
                                lambda: e().klondienst, stimmenquelle)
    meins = Meins(geruest.db, bibliothek.name_von, bibliothek.kennung_von)
    # Notizen und Themen als Markdown in der Kellerwolke (WIKI-23)
    markdown = Markdownablage(lambda: geruest.kellerwolke, meins.notizen, lambda: e().adresse, lambda: e().notizen_als_markdown)
    geruest.begleiter_anmelden(meins)
    themen = Themen(geruest.db, bibliothek.name_von, bibliothek.kennung_von)
    # große Bilder (WIKI-80): Regeln aus den Einstellungen an den Bildholer, geöffnete und gelesene Artikel vormerken
    grossbilder = Grossbilder(lambda: e().bilder_ordner, lambda: e().bildholer_adresse, lambda: Bildregeln(
        an=e().bilder_an, abstand_s=e().bilder_abstand_s, wann=e().bilder_wann, nacht_von=e().nachts_von,
        nacht_bis=e().nachts_bis, breite=int(e().bilder_breite), platz_gb=e().bilder_platz_gb,
        bei_drosselung=e().bilder_bei_drosselung, absender=e().bilder_absender),
        lambda: e().bilder_an and e().bilder_beim_oeffnen, leser, [meins.artikel_aller, themen.artikel_aller])
    geruest.verbindung_anmelden("Bildholer", grossbilder.verbindung)
    geruest.begleiter_anmelden(themen)                   # nach Meins: Einträge lesen Lesestand und Notizen von dort
    geruest.begleiter_anmelden(grossbilder)              # nach Meins und Themen: liest deren Artikel
    geruest.begleiter_anmelden(indexauftraege)
    kategorienauftraege = Indexauftraege(kategorienablage, bibliothek, geruest.auftraege,
                                         lambda: e().indexdienst_schluessel.get_secret_value(),
                                         lambda: list(get_args(Buchart)) if e().kategorien_aus_abzuegen else [],
                                         nutzbare=quellen.nutzbare, sorte="kategorien", art="kategorien", titel="Kategorien",
                                         passt=lambda b: wiki(b.kennung) is not None)
    geruest.begleiter_anmelden(kategorienauftraege)
    uebersetzer = Uebersetzer(geruest.db, lambda: geruest.leitstelle, lambda: e().suchmodell)
    geruest.begleiter_anmelden(uebersetzer)
    artikeluebersetzer = Artikeluebersetzer(geruest.db, geruest.auftraege, bibliothek, leser, lambda: geruest.leitstelle,
                                            lambda: e().suchmodell)
    geruest.begleiter_anmelden(artikeluebersetzer)
    geruest.verbindung_anmelden("Index-Dienst", indexauftraege.verbindung)

    # Was das System kennt, ist kein Textfeld: die Bücher der Bibliothek als Auswahl, der Fundus aus dem Verzeichnis
    async def buecher() -> Angebot:
        stand = await bibliothek.stand()
        return Angebot(optionen=[Option(wert=b.kennung, titel=b.titel, hinweis=f"{b.kennung}, Stand {b.stand}")
                                 for b in stand.buecher], eigener_wert=False, stand=f"{len(stand.buecher)} Quellen")

    geruest.einstellungen.anbieten("bedeutung_buch", buecher)
    geruest.einstellungen.anbieten("fundus_sammlung", anbindung.angebot)

    async def buchnamen() -> Angebot:
        """Bücher in der Suche: je Buch einmal, über den Namen (gilt für jede Fassung)."""
        stand = await bibliothek.stand()
        je = {b.name: b for b in sorted(stand.buecher, key=lambda b: b.stand)}
        return Angebot(optionen=[Option(wert=n, titel=b.titel, hinweis=f"{b.sprache}, {b.artikel} Artikel") for n, b in sorted(je.items())],
                       eigener_wert=False, stand=f"{len(je)} Bücher")

    geruest.einstellungen.anbieten("suche_buecher", buchnamen)
    geruest.einstellungen.anbieten("hoerdienst", geruest.leitstelle_angebot("hoeren"))
    geruest.einstellungen.anbieten("sprechdienst", geruest.leitstelle_angebot("stimme"))
    geruest.einstellungen.anbieten("klondienst", geruest.leitstelle_angebot("stimme_klonen"))
    geruest.einstellungen.anbieten("vertonung_adresse", geruest.verbund.angebot("Vertonung", "vertonung", lambda: e().vertonung_adresse))

    async def stimmen() -> Angebot:
        """Die eigenen Stimmen, die die Vertonung freigibt, und der Katalog des Sprechdienstes, jedes Mal von dort;
        leer: die Vorgabe des Sprechdienstes."""
        optionen, stand = [Option(wert="", titel="Vorgabe des Sprechdienstes")], []
        try:
            eigene = await stimmenquelle.eigene()
            optionen += [Option(wert=PRIVAT + s.id, titel=s.name, hinweis="eigene Stimme, für Nachschlag freigegeben") for s in eigene]
            stand.append(f"{len(eigene)} eigene")
        except VerbundFehler as f:
            stand.append(f"Vertonung antwortet nicht: {f.meldung}")
        try:
            katalog = await sprechdienst.katalog()
            optionen += [Option(wert=s, titel=s, hinweis="Katalog") for s in katalog]
            stand.append(f"{len(katalog)} im Katalog")
        except (LeitstellenFehler, NichtBereit) as f:
            stand.append(f"Katalog nicht erreichbar: {f}")
        return Angebot(optionen=optionen, eigener_wert=False, stand=", ".join(stand))

    geruest.einstellungen.anbieten("vorlesestimme", stimmen)
    geruest.einstellungen.anbieten("suchmodell", geruest.leitstelle_angebot("text"))
    geruest.einstellungen.anbieten("fundus_adresse", geruest.verbund.angebot("Fundus", "fundus", lambda: e().fundus_adresse))
    geruest.verbund.anmelden("Fundus", lambda: e().fundus_adresse)
    geruest.verbund.anmelden("Codeschmiede", lambda: e().codeschmiede_adresse)   # Ausprobieren (WIKI-48)
    geruest.einstellungen.anbieten("codeschmiede_adresse",
                                   geruest.verbund.angebot("Codeschmiede", "codeschmiede", lambda: e().codeschmiede_adresse))
    geruest.verbund.anmelden("Vertonung", lambda: e().vertonung_adresse)   # nur Proben eigener Stimmen

    # Stapelarbeit je Sammlung (WIKI-44): jede Arbeit mit eigener Stimme spricht über einen eigenen Sprechdienst
    sammlungen = Sammlungen(geruest.db, geruest.auftraege, themen, bibliothek, leser, artikeluebersetzer,
                            lambda stimme: Sprechdienst(lambda: geruest.leitstelle, lambda: e().sprechdienst,
                                                        lambda: stimme or e().vorlesestimme, lambda: e().klondienst, stimmenquelle),
                            lambda: geruest.leitstelle, lambda: e().suchmodell, lambda: geruest.kellerwolke,
                            lambda: (e().nachts_von, e().nachts_bis))
    geruest.begleiter_anmelden(sammlungen)

    # Bücherlader (WIKI-57): Verzeichnis durchsehen, Neues melden, Abos laden; schreibt als Einziger in den Ordner der Bücher
    def laderregeln() -> Laderregeln:
        s = e()
        return Laderregeln(
            ordner=Path(s.buecher_ordner), pruefsummen=s.pruefsummen_adresse.strip(),
            sprachen=frozenset(k for k, an in (("de", s.sprache_deutsch), ("en", s.sprache_englisch),
                                               ("mul", s.sprache_mehrsprachig)) if an),
            durchsicht=s.durchsicht, neue_fassung=s.neue_fassung, laden_wann=s.laden_wann,
            fenster=(s.nachts_von, s.nachts_bis), reserve=int(s.reserve_gb * 1024**3),
            hoechstens=int(s.buecher_hoechstens_gb * 1024**3), vorige_tage=s.vorige_tage,
            liste=Path(s.bibliotheksliste) if s.bibliotheksliste.strip() else None)

    async def fundus_dateien() -> set[str] | None:
        """Dateien, die der Fundus noch einliest (WIKI-58): ohne Fundus keine; antwortet er nicht, unbekannt."""
        if not e().fundus_adresse.strip():
            return set()
        try:
            antwort = await geruest.verbund.anfrage("GET", e().fundus_adresse, "/api/v1/quellenstand/dateien")
            return set(antwort.json().get("dateien", []))
        except (VerbundFehler, ValueError):
            return None

    async def nach_loeschen(kennung: str, letzte: bool) -> None:
        """Ein Buch ist gelöscht (WIKI-77) oder seine vorige Fassung nach der Frist entfernt: der Vermerk im Archiv geht,
        die Kategorien der Fassung auch (die neue Fassung baut ihre eigenen, WIKI-75); der eigene Index nur mit der
        letzten Fassung (sonst bleibt er Vorlage für den Index einer anderen Fassung, WIKI-58)."""
        await quellen.vergessen(kennung)
        kategorienablage.entfernen(kennung)
        if letzte:
            eigen.entfernen(kennung)

    lader = Buecherlader(geruest.db, geruest.auftraege, laderregeln, quellen.von_hand_aktiv,
                         transport=lader_transport or transport, in_gebrauch=fundus_dateien, nach_loeschen=nach_loeschen)
    geruest.begleiter_anmelden(lader)
    # eine Regel zum Zurückstellen für alle Dienste: Sammlungen warten auf die Nacht, Laden mit "nur nachts" auch
    geruest.auftraege.zurueckstellen_wenn(lambda a: sammlungen.zurueckstellen(a) or lader.zurueckstellen(a))

    app = geruest.fastapi()
    app.state.geruest = geruest
    app.state.bibliothek = bibliothek
    app.state.indexauftraege = indexauftraege
    app.state.kategorienauftraege = kategorienauftraege
    app.include_router(router(geruest, bibliothek, leser, suche, quellen,
                              suchregeln=lambda: Suchregeln(vorschlaege=e().vorschlaege, an_der_stelle=e().an_der_stelle),
                              eigen=eigen, grossbilder=grossbilder))
    app.include_router(mcp_router(geruest, mcp_werkzeuge(bibliothek, suche, leser)))   # MCP-Werkzeuge für KI (WIKI-78)
    app.include_router(quellenarchiv_router(geruest, quellen))
    app.include_router(buecherlader_router(geruest, lader))
    app.include_router(sammlung_router(geruest, sammlungen, stimmen))
    app.include_router(ausprobieren_router(geruest, Ausprobieren(lambda: geruest.verbund, lambda: e().codeschmiede_adresse)))
    notizbilder = Notizbilder(meins, lambda: geruest.kellerwolke)
    app.include_router(meins_router(geruest, meins, notizbilder, markdown))
    app.include_router(notizbilder_router(geruest, notizbilder))                 # Bilder für <img> (Cookie)
    app.include_router(themen_router(geruest, themen, suche, bibliothek, meins, leser, markdown,
                                     ThemenOrdner(geruest.auftraege, themen, leser, lambda: geruest.leitstelle, lambda: e().suchmodell)))
    app.include_router(zitieren_router(geruest, bibliothek, leser))
    app.include_router(medien_router(geruest, Medien(leser, suche, lambda buch, pfad: grossbilder.finden(buch, pfad) is not None)))
    async def themenartikel(konto: str) -> list[tuple[str, str]]:
        """Buch (heutige Fassung) und Pfad jedes Artikels in den Themen des Kontos (Stöbern: nahe an meinen Themen)."""
        return [(k, z.pfad) for z in await themen.zuordnung(konto) if (k := await bibliothek.kennung_von(z.buch_name))]

    app.include_router(stoebern_router(geruest, Stoebern(bibliothek, leser, suche, meins.gelesen, eigen, themenartikel)))
    app.include_router(register_router(geruest, Register(bibliothek, eigen)))
    app.include_router(anleitungen_router(geruest, Anleitungen(bibliothek, eigen, wege(bibliothek))))
    app.include_router(uebersetzung_router(geruest, uebersetzer, artikeluebersetzer,
                                           Stellenuebersetzer(lambda: geruest.leitstelle, lambda: e().suchmodell)))
    app.include_router(vorlesen_router(geruest, sprechdienst))     # Vorlesen über die Leitstelle (WIKI-43)
    app.include_router(sprache_router(geruest, lambda: e().hoerdienst))
    app.include_router(korrektur_router(geruest, Korrektor(eigen.alle, lambda: geruest.leitstelle, lambda: e().suchmodell),
                                         an=lambda: e().tippfehler))
    app.include_router(kategorien_router(geruest, kategorien))
    app.include_router(bilder_router(geruest, grossbilder))
    app.include_router(indexdienst_router([indexauftraege, kategorienauftraege]))   # nur mit dem Schlüssel des Index-Dienstes
    # unter /lesen trägt der Weg Pfade aus Büchern, oft mit Punkt (function.array-map.php): immer eine Seite
    geruest.oberflaeche_ausliefern(app, seiten=["lesen"])
    return app


def daten_ordner() -> Path:
    """Wo die App ihre Daten hält: `NACHSCHLAG_DATEN` (im Container /app/daten), sonst daten/ im Repo."""
    return Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten")


app = app_bauen(daten_ordner())
