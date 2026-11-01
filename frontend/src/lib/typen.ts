// Was die Schnittstelle von Nachschlag liefert (Spiegel der Modelle in backend/app/modell).

export type Art = "enzyklopaedie" | "dokumentation" | "frage_antwort" | "webseite" | "sonstiges";

export interface Faehigkeiten {
  titelindex: boolean;
  volltext: boolean;
  bilder: boolean;
  lesedesign: boolean;
}

export interface Buch {
  kennung: string;
  name: string;
  titel: string;
  beschreibung: string;
  sprache: string;
  stand: string;
  erzeuger: string;
  art: Art;
  eintraege: number;
  artikel: number;
  medien: number;
  groesse: number;
  faehigkeiten: Faehigkeiten;
  startseite: string;
}

export interface Bibliotheksstand {
  ordner: string;
  buecher: Buch[];
  fehler: string[];
}

export interface Abschnitt {
  anker: string;
  titel: string;
  ebene: number;
}

export interface Steckbrief {
  titel: string;
  html: string;
}

export interface Verweiszahlen {
  intern: number;
  ohne_ziel: number;
  koordinaten: number;
  online: number;
}

export interface Kachel {
  pfad: string;
  titel: string;
  bild: string;
}

export interface Artikel {
  buch: string;
  pfad: string;
  angefragt: string;
  anker: string;
  titel: string;
  darstellung: "lesedesign" | "uebersicht" | "original";
  baustein: string;
  html: string;
  einleitung: string;
  abschnitte: Abschnitt[];
  steckbrief: Steckbrief | null;
  bild: string;
  verweise: Verweiszahlen;
  online: string[];
  original: string;
  kacheln: Kachel[];
}

export type Weg = "bedeutung" | "index";

export interface Treffer {
  buch: string;
  pfad: string;
  titel: string;
  abschnitt: string;
  anker: string;
  ausschnitt: string;
  wege: Weg[];
  rang: number;
  bild: string;
}

export interface Suchergebnis {
  frage: string;
  treffer: Treffer[];
  beste_stelle: Treffer | null;
  nur_index: boolean;
  hinweis: string;
  bedeutung_angebunden: boolean;
  zeiten: { index_ms: number; bedeutung_ms: number | null };
  index_gesamt: number;
}

export interface Vorschlag {
  buch: string;
  pfad: string;
  titel: string;
  weiterleitung: string;
  kurztext: string;
  bild: string;
}
