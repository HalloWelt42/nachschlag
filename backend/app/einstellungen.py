"""Einstellungen von Nachschlag. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; die Seite
Einstellungen der Oberfläche entsteht hieraus von selbst (Reiter je Gruppe). Vorgaben sind neutral: Adressen im eigenen
Netz kommen über die Umgebung (`NACHSCHLAG_<FELD>`) oder die Seite Einstellungen, nie ins Repo."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator

from appkern.app import Grundeinstellungen
from appkern.app.einstellungen import VERBINDUNGEN

BIBLIOTHEK = {"gruppe": "Bibliothek"}
SUCHE = {"gruppe": "Suche"}
VORLESEN = {"gruppe": "Vorlesen"}
UEBER_NACHT = {"gruppe": "Über Nacht"}
BUECHERLADER = {"gruppe": "Bücherlader"}
BILDER = {"gruppe": "Bilder"}
MEINS = {"gruppe": "Meins"}

#: Wie oft der Bücherlader das Verzeichnis durchsieht (WIKI-57)
DURCHSICHT = {"taeglich": "täglich", "woechentlich": "wöchentlich", "monatlich": "monatlich"}
NEUE_FASSUNG = {"laden": "laden und prüfen", "melden": "nur melden"}
LADEN_WANN = {"immer": "immer", "nachts": "nur nachts (Fenster unter Über Nacht)"}

#: Vorgabe für Übersetzung und Korrektur. Das Modell wählt immer die App, nie die Leitstelle (LS-19): jede Textanfrage
#: nennt es, eine leere Einstellung gilt als diese Vorgabe.
TEXTMODELL = "qwen/qwen3-next-80b"

#: Welche Bücher einen eigenen Index bekommen (WIKI-17): Stufen in der Reihenfolge des Baus, docs/SUCHE.md
EIGENE_INDIZES = {"keine": "keine", "handbuecher": "Handbücher und Übungen",
                  "handbuecher_fragen": "Handbücher, Übungen, Frage und Antwort, Anleitungen", "alle": "alle Quellen"}
ARTEN_JE_STUFE: dict[str, list[str]] = {
    "keine": [], "handbuecher": ["dokumentation", "uebung"],
    "handbuecher_fragen": ["dokumentation", "uebung", "frage_antwort", "anleitung"],
    "alle": ["dokumentation", "uebung", "frage_antwort", "anleitung", "enzyklopaedie", "webseite", "sonstiges"]}


class AppEinstellungen(Grundeinstellungen):
    # --- Bibliothek -------------------------------------------------------------------------------------------------
    buecher_ordner: str = Field("/buecher", title="Ordner der ZIM-Libs", json_schema_extra=BIBLIOTHEK,
                                description="Jede ZIM-Datei in diesem Ordner ist eine Quelle; neue Dateien erscheinen von selbst. "
                                            "Nachschlag liest nur; hinein schreibt allein der Bücherlader (in die "
                                            "verborgenen Ordner .laden und .neu und beim Umschalten).")

    # --- Bücherlader (WIKI-57): Verzeichnis durchsehen, Neues melden, Abos laden --------------------------------------
    pruefsummen_adresse: str = Field("https://download.kiwix.org/zim/", title="Quelle der Prüfsummen",
                                     json_schema_extra=BUECHERLADER,
                                     description="Hier liegt zu jeder Datei ihre Ladedatei (.meta4 mit Prüfsumme und Spiegeln) "
                                                 "oder eine Prüfsumme (.sha256), mit demselben Pfad wie in den Verzeichnissen; "
                                                 "gilt, wenn die Quelle selbst keine nennt. Ohne Prüfsumme lädt nichts. Die "
                                                 "Quellen selbst stehen in der Bibliothek unter Fassungen und Laden.")
    sprache_deutsch: bool = Field(True, title="Deutsche Bücher", json_schema_extra=BUECHERLADER,
                                  description="Deutsche Bücher erscheinen im Verzeichnis und werden gemeldet.")
    sprache_englisch: bool = Field(True, title="Englische Bücher", json_schema_extra=BUECHERLADER,
                                   description="Englische Bücher erscheinen im Verzeichnis und werden gemeldet.")
    sprache_mehrsprachig: bool = Field(False, title="Mehrsprachige Bücher", json_schema_extra=BUECHERLADER,
                                       description="Bücher in mehreren Sprachen (etwa Vorträge mit Untertiteln).")
    durchsicht: Literal["taeglich", "woechentlich", "monatlich"] = Field(
        "woechentlich", title="Verzeichnis durchsehen", json_schema_extra={**BUECHERLADER, "beschriftungen": DURCHSICHT},
        description="So oft geht der Bücherlader das ganze Verzeichnis durch, meldet Neues und lädt neuere Fassungen "
                    "abonnierter Bücher.")
    neue_fassung: Literal["laden", "melden"] = Field(
        "laden", title="Neue Fassung eines Abos", json_schema_extra={**BUECHERLADER, "beschriftungen": NEUE_FASSUNG},
        description="Laden holt und prüft sie von selbst; umgeschaltet wird in beiden Fällen erst, wenn du es bestätigst.")
    laden_wann: Literal["immer", "nachts"] = Field(
        "immer", title="Laden wann", json_schema_extra={**BUECHERLADER, "beschriftungen": LADEN_WANN},
        description="Ein Buch nach dem anderen, fortsetzbar nach einem Abbruch.")
    reserve_gb: float = Field(200, ge=0, title="Immer frei halten", json_schema_extra={**BUECHERLADER, "schritt": 10, "einheit": "GB"},
                              description="So viel bleibt auf dem Datenträger der Bücher immer frei. Passt eine Datei "
                                          "nicht, wird sie gemeldet statt geladen; fällt der freie Platz beim Laden darunter, "
                                          "hält das Laden an.")
    buecher_hoechstens_gb: float = Field(0, ge=0, title="Platz für Bücher höchstens",
                                         json_schema_extra={**BUECHERLADER, "schritt": 50, "einheit": "GB"},
                                         description="Grenze für alle Bücher zusammen, auch angefangene. 0: keine Grenze, "
                                                     "nur die Reserve.")
    vorige_tage: int = Field(14, ge=0, le=365, title="Vorige Fassung behalten",
                             json_schema_extra={**BUECHERLADER, "einheit": "Tage"},
                             description="Nach dem Umschalten bleibt die vorige Fassung so lange als Rückfall, danach wird "
                                         "sie gelöscht; nie, wenn du sie von Hand wieder aktiv gesetzt hast.")
    bibliotheksliste: str = Field("", title="Liste für den Bücherserver", json_schema_extra=BUECHERLADER,
                                  description="Pfad einer library.xml, die ein Bücherserver neben Nachschlag liest; der "
                                              "Bücherlader trägt Bücher dort ein und aus. Leer: keine Liste.")

    # --- Vorlesen (WIKI-43): über den Sprechdienst der Leitstelle ------------------------------------------------------
    sprechdienst: str = Field("klangwerk-sprechen", title="Sprechdienst", json_schema_extra=VORLESEN,
                              description="Dienst der Leitstelle, der vorliest; das Modell läuft dort, nie in Nachschlag. "
                                          "Die Leitstelle muss ihn für Nachschlag freigeben. Leer: ohne Vorlesen.")
    vorlesestimme: str = Field("", title="Stimme", json_schema_extra=VORLESEN,
                               description="Eine eigene Stimme, die die Vertonung Nachschlag freigibt (sie spricht der "
                                           "Klondienst), oder eine Stimme aus dem Katalog des Sprechdienstes. Leer: die "
                                           "Vorgabe des Sprechdienstes.")
    klondienst: str = Field("klangwerk-klonen", title="Klondienst", json_schema_extra=VORLESEN,
                            description="Dienst der Leitstelle, der mit einer eigenen Stimme spricht; er bekommt die Probe "
                                        "der Stimme mit jedem Satz.")
    vertonung_adresse: str = Field("", title="Eigene Stimmen (Vertonung)", json_schema_extra=VORLESEN,
                                   description="Adresse der Vertonung: dort liegen die eigenen Stimmen und wer sie nutzen "
                                               "darf (Vertonung, Einstellungen, Private Stimmen für). Nachschlag holt dort "
                                               "nur die Probe; gesprochen wird über die Leitstelle. Leer: nur "
                                               "Katalogstimmen.")

    # --- Über Nacht (WIKI-44): Arbeiten an Sammlungen, die für heute Nacht bestellt sind --------------------------------
    nachts_von: int = Field(22, ge=0, le=23, title="Nacht beginnt um", json_schema_extra={**UEBER_NACHT, "einheit": "Uhr"},
                            description="Ab dieser Stunde laufen Arbeiten an Sammlungen, die für heute Nacht bestellt sind "
                                        "(Ortszeit).")
    nachts_bis: int = Field(7, ge=0, le=23, title="Nacht endet um", json_schema_extra={**UEBER_NACHT, "einheit": "Uhr"},
                            description="Bis zu dieser Stunde; was dann nicht fertig ist, läuft in der nächsten Nacht weiter.")

    # --- Suche ------------------------------------------------------------------------------------------------------
    suchmodell: str = Field(TEXTMODELL, title="Modell für Übersetzung und Korrektur", json_schema_extra=SUCHE,
                            description="Übersetzt eine Frage für englische Quellen ins Englische (Fachbegriffe und Code "
                                        "bleiben), Artikel aus anderen Sprachen ins Deutsche und korrigiert Tippfehler, wenn "
                                        "der Wortschatz der Quellen nichts hergibt. Jede Anfrage an die Leitstelle nennt dieses "
                                        "Modell; leer gilt die Vorgabe Qwen 80B.")
    hoerdienst: str = Field("klangwerk-hoeren", title="Hördienst für die Spracheingabe", json_schema_extra=SUCHE,
                            description="Dienst der Leitstelle, der gesprochene Fragen und Notizen verschriftet. Das "
                                        "Mikrofon erscheint nur, wenn die Leitstelle ihn für Nachschlag freigibt.")
    eigene_indizes: Literal["keine", "handbuecher", "handbuecher_fragen", "alle"] = Field(
        "handbuecher_fragen", title="Quellen mit eigenem Index", json_schema_extra={**SUCHE, "beschriftungen": EIGENE_INDIZES},
        description="Ein eigener Index findet Namen aus dem Code (array_map), Rubriken und Einleitungen und sucht in Quellen "
                    "ohne eingebauten Index. Gebaut wird er auf dem Mac, kleine Quellen zuerst; bis er steht, sucht die Quelle "
                    "über den Index der ZIM-Datei.")
    eigenindex_hoechstens_gb: float = Field(
        5, ge=0, title="Eigener Index von selbst bis", json_schema_extra={**SUCHE, "schritt": 1, "einheit": "GB"},
        description="Quellen bis zu dieser Größe bekommen ihren Index von selbst. Größere (etwa Stack Overflow, 115 GB) "
                    "brauchen auf dem Mac viele Stunden und mehrere hundert GB Platz; sie beginnen erst, wenn die Grenze "
                    "darüber liegt.")
    eigenindex_ordner: str = Field("/eigenindex", title="Ordner der eigenen Indizes", json_schema_extra=SUCHE,
                                   description="Je Quelle eine Datei. Leer: keine eigenen Indizes. Gehört in die Sicherung "
                                               "(Rechenzeit), anders als die ZIM-Libs.")
    kategorien_aus_abzuegen: bool = Field(
        True, title="Kategorien für Wikipedia", json_schema_extra=SUCHE,
        description="Die Bücher der Wikipedia (und anderer Wikis von Wikimedia) bringen keine Kategorien mit. Der "
                    "Index-Dienst auf dem Mac lädt dafür die Datenabzüge von Wikimedia (gut 1 GB je Wiki, monatlich neu) "
                    "und baut je Buch die Kategorien; danach stehen sie am Ende jedes Artikels und als eigene Seiten.")
    indexdienst_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel des Index-Dienstes", json_schema_extra=SUCHE,
                                              description="Mit diesem Schlüssel holt der Index-Dienst auf dem Mac die "
                                                          "Aufträge hier ab (dort NACHSCHLAG_INDEX_SCHLUESSEL). Leer: "
                                                          "kein Index-Dienst, es wird nichts gebaut.")
    codeschmiede_adresse: str = Field("", title="Ausprobieren (Codeschmiede)", json_schema_extra=VERBINDUNGEN,
                                      description="Adresse der Codeschmiede: in ihrer Sandbox laufen Beispiele aus Handbüchern "
                                                  "zum Ausprobieren und Debuggen (sie muss Nachschlag zulassen). Leer: ohne "
                                                  "Ausprobieren.")
    notizen_als_markdown: bool = Field(True, title="Notizen als Markdown in die Kellerwolke", json_schema_extra=MEINS,
                                       description="Nach jeder Änderung liegen die Notizen eines Artikels als Markdown im "
                                                   "Ordner Notizen der App in der Kellerwolke (je Quelle und Artikel); "
                                                   "aus: nur in Nachschlag.")
    fundus_adresse: str = Field("", title="Bedeutungssuche (Fundus)", json_schema_extra=SUCHE,
                                description="Adresse des Fundus, der die Artikel einer Quelle nach Abschnitten eingebettet hält. "
                                            "Leer: Nachschlag sucht nur im Index der Quellen.")
    fundus_sammlung: str = Field("", title="Sammlung im Fundus", json_schema_extra=SUCHE,
                                 description="Die Sammlung, in der der Fundus die Quelle eingebettet hat.")
    fundus_vorsilbe: str = Field("wikipedia:de/", title="Herkunft der Treffer", json_schema_extra=SUCHE,
                                 description="Vorsilbe, mit der der Fundus die Artikel dieser Quelle kennzeichnet; dahinter "
                                             "steht der Pfad in der Quelle.")
    bedeutung_buch: str = Field("", title="Quelle der Bedeutungssuche", json_schema_extra=SUCHE,
                                description="Die Quelle, zu der die Sammlung gehört; ihre Treffer öffnen dort. Nach dem "
                                            "Umschalten auf eine neue Fassung gilt die neue.")
    bedeutung_warten_s: float = Field(1.5, ge=0.2, le=10, title="Warten auf die Bedeutungssuche",
                                      json_schema_extra={**SUCHE, "schritt": 0.1, "einheit": "Sekunden"},
                                      description="Danach kommen die Treffer aus dem Index allein, mit Hinweis.")
    # --- Suche: Mischung und Komfort (WIKI-79, Entwurf einstellungen-suche.html) ---------------------------------------
    mischung: Literal["index", "ausgewogen", "bedeutung"] = Field(
        "ausgewogen", title="Mischung", json_schema_extra={**SUCHE, "beschriftungen": {
            "index": "Mehr Index", "ausgewogen": "Ausgewogen", "bedeutung": "Mehr Bedeutung"}},
        description="Wie Treffer beider Wege zu einer Liste werden. Ausgewogen nutzt die Rangfolge beider gleich; mehr Index "
                    "oder mehr Bedeutung zählt den einen Weg doppelt.")
    vorschlaege: Literal["titel", "titel_stellen"] = Field(
        "titel_stellen", title="Vorschläge beim Tippen", json_schema_extra={**SUCHE, "beschriftungen": {
            "titel": "Nur Titel", "titel_stellen": "Titel und Stellen"}},
        description="Titel mit Bild und Kurztext, auf Wunsch darunter passende Stellen (fragt die Suche schon beim Tippen).")
    tippfehler: bool = Field(True, title="Tippfehler verzeihen", json_schema_extra=SUCHE,
                             description="Schlägt bei einem Tippfehler die gemeinte Frage vor (\"Andromeda galaxie\" findet "
                                         "Andromedagalaxie); ohne Treffer sucht die Suche gleich mit dem Vorschlag.")
    suche_buecher: list[str] = Field(default_factory=list, title="Bücher in der Suche", json_schema_extra=SUCHE,
                                     description="In welchen Büchern die Suche sucht, solange nichts anderes gewählt ist; leer: in "
                                                 "allen. Gilt über neue Fassungen eines Buchs hinweg.")
    an_der_stelle: bool = Field(True, title="Treffer direkt an der Stelle öffnen", json_schema_extra=SUCHE,
                                description="Ein Bedeutungstreffer springt in seinen Abschnitt und markiert die Fundstelle; aus: "
                                            "der Artikel öffnet oben.")

    # --- Bilder (WIKI-80): der Bildholer lädt große Bilder zu den Vorschaubildern (eigenes Programm, eigener Container) ---
    bilder_an: bool = Field(True, title="Große Bilder nachladen", json_schema_extra=BILDER,
                            description="Der Bildholer lädt zu den Vorschaubildern der Wikipedia (und anderer Wikis) das große "
                                        "Bild aus der Bildquelle, mit Urheber und Lizenz. Bis es da ist, zeigt Nachschlag das "
                                        "Vorschaubild. Stand und Anhalten: Reiter Bildholer.")
    bilder_beim_oeffnen: bool = Field(True, title="Beim Öffnen eines Artikels zuerst", json_schema_extra=BILDER,
                                      description="Die Bilder eines geöffneten Artikels kommen als Nächstes; danach geht es mit "
                                                  "Gelesenem, Gemerktem und Themen weiter.")
    bilder_abstand_s: float = Field(3, ge=1, le=3600, title="Abstand zwischen zwei Bildern",
                                    json_schema_extra={**BILDER, "schritt": 1, "einheit": "Sekunden"},
                                    description="Ein Bild nach dem anderen, nie gleichzeitig. Kleiner heißt schneller, aber mehr "
                                                "Last bei der Bildquelle.")
    bilder_wann: Literal["immer", "nachts"] = Field(
        "immer", title="Wann laden", json_schema_extra={**BILDER, "beschriftungen": {"immer": "Immer", "nachts": "Nur nachts"}},
        description="Nur nachts gilt das Zeitfenster für Nachtarbeit (Einstellungen, Über Nacht).")
    bilder_breite: Literal["960", "1280", "1920"] = Field(
        "1280", title="Größte Breite", json_schema_extra={**BILDER, "beschriftungen": {"960": "960 px", "1280": "1.280 px", "1920": "1.920 px"}},
        description="Die Bildquelle hält diese Breiten vorrätig. Ist das Original schmaler, kommt das Original; nie aufgeblasen.")
    bilder_platz_gb: float = Field(200, ge=1, title="Platz höchstens", json_schema_extra={**BILDER, "schritt": 10, "einheit": "GB"},
                                   description="Ist die Grenze erreicht, hält der Bildholer an und meldet es; nichts wird gelöscht.")
    bilder_bei_drosselung: Literal["langsamer", "anhalten"] = Field(
        "langsamer", title="Wenn die Bildquelle drosselt", json_schema_extra={
            **BILDER, "beschriftungen": {"langsamer": "Warten und langsamer", "anhalten": "Anhalten"}},
        description="Bei zu vielen Anfragen wartet der Bildholer die verlangte Zeit und verdoppelt den Abstand (nach einer "
                    "Stunde Ruhe gilt wieder der eingestellte), oder er hält an, bis du fortsetzt.")
    bilder_absender: str = Field("Nachschlag-Bildholer/1.0 (https://github.com/HalloWelt42/nachschlag)", min_length=8, max_length=200,
                                 title="Absender bei der Bildquelle", json_schema_extra=BILDER,
                                 description="Die Bildquelle verlangt eine Kennung mit Kontakt (Webseite oder E-Mail), sonst "
                                             "sperrt sie (gemessen 08.11.2026). Vorgabe: die Seite des Projekts.")
    bildholer_adresse: str = Field("http://bildholer:8000", title="Adresse des Bildholers", json_schema_extra=BILDER,
                                   description="Im eigenen Netz der Container. Leer: kein Bildholer.")
    bilder_ordner: str = Field("/bilder", title="Ablage der großen Bilder", json_schema_extra=BILDER,
                               description="Hier legt der Bildholer die Bilder ab; Nachschlag liest sie nur.")

    @field_validator("suchmodell", mode="before")
    @classmethod
    def _modell_nie_leer(cls, wert: object) -> object:
        """Leer (auch ein früher gespeicherter leerer Wert) heißt die Vorgabe: ohne Modell lehnt die Leitstelle ab."""
        return TEXTMODELL if isinstance(wert, str) and not wert.strip() else wert
