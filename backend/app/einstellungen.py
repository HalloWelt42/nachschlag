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

#: Wie oft der Bücherlader das Verzeichnis durchsieht (WIKI-57)
DURCHSICHT = {"taeglich": "täglich", "woechentlich": "wöchentlich", "monatlich": "monatlich"}
NEUE_FASSUNG = {"laden": "laden und prüfen", "melden": "nur melden"}
LADEN_WANN = {"immer": "immer", "nachts": "nur nachts (Fenster unter Über Nacht)"}

#: Vorgabe für Übersetzung und Korrektur. Das Modell wählt immer die App, nie die Leitstelle (LS-19): jede Textanfrage
#: nennt es, eine leere Einstellung gilt als diese Vorgabe.
TEXTMODELL = "qwen/qwen3-next-80b"

#: Welche Bücher einen eigenen Index bekommen (WIKI-17): Stufen in der Reihenfolge des Baus, docs/SUCHE.md
EIGENE_INDIZES = {"keine": "keine", "handbuecher": "Handbücher", "handbuecher_fragen": "Handbücher, Frage und Antwort",
                  "alle": "alle Quellen"}
ARTEN_JE_STUFE: dict[str, list[str]] = {
    "keine": [], "handbuecher": ["dokumentation"], "handbuecher_fragen": ["dokumentation", "frage_antwort"],
    "alle": ["dokumentation", "frage_antwort", "enzyklopaedie", "webseite", "sonstiges"]}


class AppEinstellungen(Grundeinstellungen):
    # --- Bibliothek -------------------------------------------------------------------------------------------------
    buecher_ordner: str = Field("/buecher", title="Ordner der ZIM-Libs", json_schema_extra=BIBLIOTHEK,
                                description="Jede ZIM-Datei in diesem Ordner ist eine Quelle; neue Dateien erscheinen von selbst. "
                                            "Nachschlag liest nur; hinein schreibt allein der Bücherlader (in die "
                                            "verborgenen Ordner .laden und .neu und beim Umschalten).")

    # --- Bücherlader (WIKI-57): Verzeichnis durchsehen, Neues melden, Abos laden --------------------------------------
    verzeichnis_adresse: str = Field("https://ftp.uni-erlangen.de/kiwix/zim/", title="Verzeichnis der Bücher",
                                     json_schema_extra=BUECHERLADER,
                                     description="Adresse des Verzeichnisses mit einem Unterordner je Bereich (Seiten, wie "
                                                 "sie ein Webserver für Ordner ausgibt). Von hier lädt der Bücherlader. "
                                                 "Leer: kein Bücherlader.")
    pruefsummen_adresse: str = Field("https://download.kiwix.org/zim/", title="Quelle der Prüfsummen",
                                     json_schema_extra=BUECHERLADER,
                                     description="Hier liegt zu jeder Datei eine Prüfsumme (SHA-256, Endung .sha256), mit "
                                                 "demselben Pfad wie im Verzeichnis. Ohne Prüfsumme lädt nichts.")
    katalog_adresse: str = Field("https://opds.library.kiwix.org/catalog/v2", title="Katalog der Bücher",
                                 json_schema_extra=BUECHERLADER,
                                 description="Liefert Titel, Beschreibung und Zahl der Artikel zu den Dateien. Leer: das "
                                             "Verzeichnis zeigt nur die Namen der Dateien.")
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
    indexdienst_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel des Index-Dienstes", json_schema_extra=SUCHE,
                                              description="Mit diesem Schlüssel holt der Index-Dienst auf dem Mac die "
                                                          "Aufträge hier ab (dort NACHSCHLAG_INDEX_SCHLUESSEL). Leer: "
                                                          "kein Index-Dienst, es wird nichts gebaut.")
    codeschmiede_adresse: str = Field("", title="Ausprobieren (Codeschmiede)", json_schema_extra=VERBINDUNGEN,
                                      description="Adresse der Codeschmiede: in ihrer Sandbox laufen Beispiele aus Handbüchern "
                                                  "zum Ausprobieren und Debuggen (sie muss Nachschlag zulassen). Leer: ohne "
                                                  "Ausprobieren.")
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

    @field_validator("suchmodell", mode="before")
    @classmethod
    def _modell_nie_leer(cls, wert: object) -> object:
        """Leer (auch ein früher gespeicherter leerer Wert) heißt die Vorgabe: ohne Modell lehnt die Leitstelle ab."""
        return TEXTMODELL if isinstance(wert, str) and not wert.strip() else wert
