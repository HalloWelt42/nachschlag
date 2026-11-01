"""Einstellungen von Nachschlag. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; die Seite
Einstellungen der Oberfläche entsteht hieraus von selbst (Reiter je Gruppe). Vorgaben sind neutral: Adressen im eigenen
Netz kommen über die Umgebung (`NACHSCHLAG_<FELD>`) oder die Seite Einstellungen, nie ins Repo."""

from typing import Literal

from pydantic import Field, SecretStr

from appkern.app import Grundeinstellungen

BIBLIOTHEK = {"gruppe": "Bibliothek"}
SUCHE = {"gruppe": "Suche"}
VORLESEN = {"gruppe": "Vorlesen"}

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
                                            "Nachschlag liest nur.")

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

    # --- Suche ------------------------------------------------------------------------------------------------------
    suchmodell: str = Field("qwen/qwen3-next-80b", title="Modell für Übersetzung und Korrektur", json_schema_extra=SUCHE,
                            description="Übersetzt eine Frage für englische Quellen ins Englische (Fachbegriffe und Code "
                                        "bleiben), Artikel aus anderen Sprachen ins Deutsche und korrigiert Tippfehler, wenn "
                                        "der Wortschatz der Quellen nichts hergibt. Leer: die Kette der App in der Leitstelle.")
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
    fundus_adresse: str = Field("", title="Bedeutungssuche (Fundus)", json_schema_extra=SUCHE,
                                description="Adresse des Fundus, der die Artikel einer Quelle nach Abschnitten eingebettet hält. "
                                            "Leer: Nachschlag sucht nur im Index der Quellen.")
    fundus_sammlung: str = Field("", title="Sammlung im Fundus", json_schema_extra=SUCHE,
                                 description="Die Sammlung, in der der Fundus die Quelle eingebettet hat.")
    fundus_vorsilbe: str = Field("wikipedia:de/", title="Herkunft der Treffer", json_schema_extra=SUCHE,
                                 description="Vorsilbe, mit der der Fundus die Artikel dieser Quelle kennzeichnet; dahinter "
                                             "steht der Pfad in der Quelle.")
    bedeutung_buch: str = Field("", title="Quelle der Bedeutungssuche", json_schema_extra=SUCHE,
                                description="Die Quelle, zu der die Sammlung gehört; ihre Treffer öffnen dort.")
    bedeutung_warten_s: float = Field(1.5, ge=0.2, le=10, title="Warten auf die Bedeutungssuche",
                                      json_schema_extra={**SUCHE, "schritt": 0.1, "einheit": "Sekunden"},
                                      description="Danach kommen die Treffer aus dem Index allein, mit Hinweis.")
