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
  code: boolean;
}

export interface Verweiszahlen {
  intern: number;
  ohne_ziel: number;
  koordinaten: number;
  online: number;
}

export interface Nachbar {
  pfad: string;
  titel: string;
}

export interface Gruppe {
  titel: string;
  eintraege: Nachbar[];
}

export interface Fragekarte {
  pfad: string;
  titel: string;
  auszug: string;
  stimmen: number;
  antworten: number;
  akzeptiert: boolean;
  schlagwoerter: string[];
  gefragt: string;
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
  belege: Beleg[];                 // Einzelnachweise; im Text als span.beleg[data-beleg] (WIKI-31)
  quelle_url: string;              // der Artikel im Netz
  original: string;
  kacheln: Kachel[];
  gruppen: Gruppe[];
  rubrik: string;
  nachbarn: Nachbar[];
  titelart: "text" | "code";
  fragen: Fragekarte[];
  zurueck: string;
  weiter: string;
}

export type Weg = "bedeutung" | "index";

/** Zahlen einer Frage auf der Trefferkarte (Frage und Antwort, eigener Index). */
export interface Fragezahlen {
  stimmen: number;
  antworten: number;
  akzeptiert: boolean;
  schlagwoerter: string[];
}

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
  frage?: Fragezahlen | null;
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

// --- Register (WIKI-39): Schlagwörter und Autoren der Frage-Antwort-Bücher ---
export interface SchlagwortEintrag { wort: string; fragen: number; stimmen: number; buecher: string[] }
export interface SchlagwortSeite { eintraege: SchlagwortEintrag[]; gesamt: number; ohne_index: string[] }
export interface RegisterFrage extends Fragekarte { buch: string }
export interface FragenSeite { wort: string; eintraege: RegisterFrage[]; gesamt: number; ohne_index: string[] }
export interface AutorEintrag {
  buch: string; schluessel: string; autor: string; beitraege: number; fragen: number; antworten: number; akzeptiert: number;
  stimmen: number; von: string; bis: string;
}
export interface AutorenSeite { eintraege: AutorEintrag[]; gesamt: number; ohne_index: string[] }
export interface AutorBeitrag { pfad: string; titel: string; art: "frage" | "antwort"; stimmen: number; datum: string; akzeptiert: boolean }
export interface AutorSeite { autor: AutorEintrag; beitraege: AutorBeitrag[]; gesamt: number }
export type Sortierung = "stimmen" | "neueste";

/** Ein Einzelnachweis (in der Oberfläche "Beleg", WIKI-31). */
export interface Beleg { nummer: number; text: string; url: string }
