"""Nachschlag: liest jedes Buch der Bibliothek. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port 8711
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI

from appkern.app import Geruest
from appkern.einstellungen import Angebot, Option

from .api import router
from .artikel import Artikelleser
from .bibliothek import Bibliothek
from .eigenindex.ablage import Eigenindizes
from .eigenindex.api import router as indexdienst_router
from .eigenindex.auftrag import Indexauftraege
from .einstellungen import ARTEN_JE_STUFE, AppEinstellungen
from .meins import Meins
from .meins.api import router as meins_router
from .register import Register
from .korrektur import Korrektor
from .korrektur.api import router as korrektur_router
from .sprache.api import router as sprache_router
from .uebersetzung import Uebersetzer
from .uebersetzung.api import router as uebersetzung_router
from .register.api import router as register_router
from .medien import Medien
from .medien.api import router as medien_router
from .stoebern import Stoebern
from .stoebern.api import router as stoebern_router
from .themen import Themen
from .themen.api import router as themen_router
from .fassung import FASSUNG, WURZEL
from .suche import Suche
from .suche.bedeutung import FundusBedeutung


def app_bauen(daten: Path, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """`transport` nur für Tests (Kellerwolke, Leitstelle und Fundus nachgestellt)."""
    geruest = Geruest(name="Nachschlag", kennung="nachschlag", rolle="liest jede Quelle der Bibliothek", symbol="fa-book-open", symbolbild="/favicon.svg",
                      farbe="#08758b", fassung=FASSUNG, daten=daten, einstellungen=AppEinstellungen,
                      oberflaeche=WURZEL / "frontend" / "dist", transport=transport)
    e = lambda: geruest.einstellungen.stand  # noqa: E731

    bibliothek = Bibliothek(lambda: e().buecher_ordner)
    leser = Artikelleser(bibliothek)
    bedeutung = FundusBedeutung(lambda: geruest.verbund, lambda: e().fundus_adresse, lambda: e().fundus_sammlung,
                                lambda: e().fundus_vorsilbe)
    eigen = Eigenindizes(lambda: e().eigenindex_ordner)
    suche = Suche(bibliothek, bedeutung, lambda: e().bedeutung_warten_s, lambda: e().bedeutung_buch,
                  lambda buch, pfad: "", eigen)
    indexauftraege = Indexauftraege(eigen, bibliothek, geruest.auftraege, lambda: e().indexdienst_schluessel.get_secret_value(),
                                    lambda: ARTEN_JE_STUFE[e().eigene_indizes], lambda: e().eigenindex_hoechstens_gb)

    meins = Meins(geruest.db, bibliothek.name_von, bibliothek.kennung_von)
    geruest.begleiter_anmelden(meins)
    themen = Themen(geruest.db, bibliothek.name_von, bibliothek.kennung_von)
    geruest.begleiter_anmelden(themen)                   # nach Meins: Einträge lesen Lesestand und Notizen von dort
    geruest.begleiter_anmelden(indexauftraege)
    uebersetzer = Uebersetzer(geruest.db, lambda: geruest.leitstelle, lambda: e().suchmodell)
    geruest.begleiter_anmelden(uebersetzer)
    geruest.verbindung_anmelden("Index-Dienst", indexauftraege.verbindung)

    # Was das System kennt, ist kein Textfeld: die Bücher der Bibliothek als Auswahl, der Fundus aus dem Verzeichnis
    async def buecher() -> Angebot:
        stand = await bibliothek.stand()
        return Angebot(optionen=[Option(wert=b.kennung, titel=b.titel, hinweis=f"{b.kennung}, Stand {b.stand}")
                                 for b in stand.buecher], eigener_wert=False, stand=f"{len(stand.buecher)} Quellen")

    geruest.einstellungen.anbieten("bedeutung_buch", buecher)
    geruest.einstellungen.anbieten("hoerdienst", geruest.leitstelle_angebot("hoeren"))
    geruest.einstellungen.anbieten("suchmodell", geruest.leitstelle_angebot("text", leer="Kette der App"))
    geruest.einstellungen.anbieten("fundus_adresse", geruest.verbund.angebot("Fundus", "fundus", lambda: e().fundus_adresse))
    geruest.verbund.anmelden("Fundus", lambda: e().fundus_adresse)

    app = geruest.fastapi()
    app.state.geruest = geruest
    app.state.bibliothek = bibliothek
    app.state.indexauftraege = indexauftraege
    app.include_router(router(geruest, bibliothek, leser, suche))
    app.include_router(meins_router(geruest, meins))
    app.include_router(themen_router(geruest, themen, suche, bibliothek, meins))
    app.include_router(medien_router(geruest, Medien(leser, suche)))
    app.include_router(stoebern_router(geruest, Stoebern(bibliothek, leser, suche, meins.gelesen)))
    app.include_router(register_router(geruest, Register(bibliothek, eigen)))
    app.include_router(uebersetzung_router(geruest, uebersetzer))
    app.include_router(sprache_router(geruest, lambda: e().hoerdienst))
    app.include_router(korrektur_router(geruest, Korrektor(eigen.alle, lambda: geruest.leitstelle, lambda: e().suchmodell)))
    app.include_router(indexdienst_router(indexauftraege))           # nur mit dem Schlüssel des Index-Dienstes
    # unter /lesen trägt der Weg Pfade aus Büchern, oft mit Punkt (function.array-map.php): immer eine Seite
    geruest.oberflaeche_ausliefern(app, seiten=["lesen"])
    return app


def daten_ordner() -> Path:
    """Wo die App ihre Daten hält: `NACHSCHLAG_DATEN` (im Container /app/daten), sonst daten/ im Repo."""
    return Path(os.environ.get("NACHSCHLAG_DATEN") or WURZEL / "daten")


app = app_bauen(daten_ordner())
