"""Einstellungen von Nachschlag. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; die Seite
Einstellungen der Oberfläche entsteht hieraus von selbst (Reiter je Gruppe). Vorgaben sind neutral: Adressen im eigenen
Netz kommen über die Umgebung (`NACHSCHLAG_<FELD>`) oder die Seite Einstellungen, nie ins Repo."""

from typing import Literal

from pydantic import Field, SecretStr

from appkern.app import Grundeinstellungen

BIBLIOTHEK = {"gruppe": "Bibliothek"}
SUCHE = {"gruppe": "Suche"}

#: Welche Bücher einen eigenen Index bekommen (WIKI-17): Stufen in der Reihenfolge des Baus, docs/SUCHE.md
EIGENE_INDIZES = {"keine": "keine", "handbuecher": "Handbücher", "handbuecher_fragen": "Handbücher, Frage und Antwort",
                  "alle": "alle Bücher"}
ARTEN_JE_STUFE: dict[str, list[str]] = {
    "keine": [], "handbuecher": ["dokumentation"], "handbuecher_fragen": ["dokumentation", "frage_antwort"],
    "alle": ["dokumentation", "frage_antwort", "enzyklopaedie", "webseite", "sonstiges"]}


class AppEinstellungen(Grundeinstellungen):
    # --- Bibliothek -------------------------------------------------------------------------------------------------
    buecher_ordner: str = Field("/buecher", title="Ordner der Bücher", json_schema_extra=BIBLIOTHEK,
                                description="Jede ZIM-Datei in diesem Ordner ist ein Buch; neue Dateien erscheinen von selbst. "
                                            "Nachschlag liest nur.")

    # --- Suche ------------------------------------------------------------------------------------------------------
    eigene_indizes: Literal["keine", "handbuecher", "handbuecher_fragen", "alle"] = Field(
        "handbuecher", title="Bücher mit eigenem Index", json_schema_extra={**SUCHE, "beschriftungen": EIGENE_INDIZES},
        description="Ein eigener Index findet Namen aus dem Code (array_map), Rubriken und Einleitungen und sucht in Büchern "
                    "ohne eingebauten Index. Gebaut wird er auf dem Mac, kleine Bücher zuerst; bis er steht, sucht das Buch "
                    "über den Index der ZIM-Datei.")
    eigenindex_ordner: str = Field("/eigenindex", title="Ordner der eigenen Indizes", json_schema_extra=SUCHE,
                                   description="Je Buch eine Datei. Leer: keine eigenen Indizes. Gehört in die Sicherung "
                                               "(Rechenzeit), anders als die Bücher.")
    indexdienst_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel des Index-Dienstes", json_schema_extra=SUCHE,
                                              description="Mit diesem Schlüssel holt der Index-Dienst auf dem Mac die "
                                                          "Aufträge hier ab (dort NACHSCHLAG_INDEX_SCHLUESSEL). Leer: "
                                                          "kein Index-Dienst, es wird nichts gebaut.")
    fundus_adresse: str = Field("", title="Bedeutungssuche (Fundus)", json_schema_extra=SUCHE,
                                description="Adresse des Fundus, der die Artikel eines Buchs nach Abschnitten eingebettet hält. "
                                            "Leer: Nachschlag sucht nur im Index der Bücher.")
    fundus_sammlung: str = Field("", title="Sammlung im Fundus", json_schema_extra=SUCHE,
                                 description="Die Sammlung, in der der Fundus das Buch eingebettet hat.")
    fundus_vorsilbe: str = Field("wikipedia:de/", title="Herkunft der Treffer", json_schema_extra=SUCHE,
                                 description="Vorsilbe, mit der der Fundus die Artikel dieses Buchs kennzeichnet; dahinter "
                                             "steht der Pfad im Buch.")
    bedeutung_buch: str = Field("", title="Buch der Bedeutungssuche", json_schema_extra=SUCHE,
                                description="Das Buch, zu dem die Sammlung gehört; ihre Treffer öffnen dort.")
    bedeutung_warten_s: float = Field(1.5, ge=0.2, le=10, title="Warten auf die Bedeutungssuche",
                                      json_schema_extra={**SUCHE, "schritt": 0.1, "einheit": "Sekunden"},
                                      description="Danach kommen die Treffer aus dem Index allein, mit Hinweis.")
