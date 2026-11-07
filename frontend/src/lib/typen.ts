// Was die Schnittstelle von Nachschlag liefert (Spiegel der Modelle in backend/app/modell).

export type Art = "enzyklopaedie" | "dokumentation" | "frage_antwort" | "anleitung" | "webseite" | "sonstiges";

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
  archiv: Archivstand | null;        // im Archiv (WIKI-46); null: aktive Quelle
}

/** Eine Quelle im Archiv: ersetzt durch eine neuere Fassung oder von Hand; ohne "mitnutzen" nicht in Suche und Stöbern. */
export interface Archivstand { grund: "ersetzt" | "von_hand"; ersetzt_durch: string; mitnutzen: boolean }

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
  darstellung: "lesedesign" | "uebersicht" | "original" | "anleitung" | "geraet" | "anleitungen";
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
  rubrik_pfad: string;              // Seite der Rubrik; leer: die Startseite des Buchs filtert nach ihr
  nachbarn: Nachbar[];
  titelart: "text" | "code";
  fragen: Fragekarte[];
  zurueck: string;
  weiter: string;
  anleitung: Anleitungsangaben | null;    // Anleitung oder Zerlegung (iFixit, WIKI-64)
  geraet: Geraeteangaben | null;          // Gerät, Kategorie oder Startseite (iFixit, WIKI-64)
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

// --- Bücherlader (WIKI-57): Spiegel von backend/app/modell/buecherlader.py ---
/** Wie ein Buch des Verzeichnisses zur eigenen Bibliothek steht. */
export type Laderzustand = "nicht_da" | "aktuell" | "neuer_da" | "laedt" | "wartet_auf_umschalten";

/** Was die Quellen über ein Buch wissen (WIKI-62). */
export interface Angaben {
  titel: string;
  beschreibung: string;
  artikel: number;
  medien: number;
  autor: string;
  herausgeber: string;
  kategorie: string;
  schlagworte: string[];
  bilder: boolean | null;
  videos: boolean | null;
  volltext: boolean | null;
  datum: string;
}

export interface Quellstand {
  nr: number;
  art: "verzeichnis" | "katalog";
  name: string;
  adresse: string;
  an: boolean;
  rang: number;
  zuletzt: string;
  funde: number;
  meldung: string;
}

export interface Quellvorschlag { name: string; adresse: string; land: string }

export interface Variante {
  stamm: string;
  ausgabe: string;                   // maxi, nopic, mini; leer bei nur einer Ausgabe
  stand: string;                     // JJJJ-MM
  groesse: number;
  neu: "" | "buch" | "fassung";
  abonniert: boolean;
  lokal_stand: string;
  zustand: Laderzustand;
  quellen: number;                   // aus so vielen Quellen ladbar
}

export interface Verzeichnisbuch {
  basis: string;
  ordner: string;
  sprache: string;
  titel: string;
  beschreibung: string;
  eintraege: number;
  angaben: Angaben;
  varianten: Variante[];
}

export interface Verzeichnisseite { eintraege: Verzeichnisbuch[]; gesamt: number; bereiche: string[]; sprachen: string[]; kategorien: string[] }

/** Filter des Katalogs (WIKI-61); Ausgabe und Größe gelten je Ausgabe. */
export interface Katalogfilter {
  suche: string;
  bereich: string;
  sprache: string;                                           // de, en, mul; leer: alle gewählten
  ausgabe: "" | "maxi" | "nopic" | "mini" | "einzeln";
  groesse_bis: number;                                       // Bytes; 0: jede Größe
  bibliothek: "" | "da" | "nicht_da" | "neuer_da";
  nur_neu: boolean;
  nur_abonniert: boolean;
  kategorie: string;                                         // laut Katalog; leer: alle
  sortierung: "titel" | "neueste" | "groesste" | "kleinste";
}

export interface Durchgang {
  begonnen: string;
  beendet: string;
  ordner: number;
  quellen: number;
  dateien: number;
  buecher: number;
  neue_buecher: number;
  neue_fassungen: number;
  erstaufnahme: boolean;
  hinweise: string[];
}

export interface Ladefortschritt {
  auftrag: string;
  zustand: "wartet" | "laeuft";
  fortschritt: number | null;        // 0 bis 1; null: unbestimmt
  schritt: string;
  zurueckgestellt: string;
}

export interface Abo {
  stamm: string;
  titel: string;
  seit: string;
  lokal_stand: string;
  neuester_stand: string;
  neueste_groesse: number;
  zustand: Laderzustand;
  wartet: string;
  rueckfall: { kennung: string; entfernt_ab: string; bleibt: string } | null;   // bleibt: warum sie nach der Frist noch da ist
  hinweis: string;
  laden: Ladefortschritt | null;
}

export interface Platz { ordner: string; frei: number; gesamt: number; reserve: number; buecher: number; im_laden: number; hoechstens: number }

export interface Laderstand {
  bereit: boolean;
  grund: string;
  regeln: { sprachen: string[]; durchsicht: string; neue_fassung: string; laden_wann: string; vorige_tage: number };
  letzter_durchgang: Durchgang | null;
  naechster_durchgang: string;
  neu_ungesehen: number;
  abos: Abo[];
  platz: Platz | null;
  quellen: Quellstand[];
}

// --- Anleitungen (iFixit, WIKI-64): Spiegel von backend/app/modell/anleitung.py ---
export interface Anleitungszeile { stufe: number; marke: "" | "hinweis" | "vorsicht" | "erinnerung"; farbe: string; text: string }
export interface Anleitungsschritt { nr: number; titel: string; bilder: string[]; zeilen: Anleitungszeile[] }
export interface Werkzeug { name: string; bild: string }
export interface Anleitungsangaben {
  art: "anleitung" | "zerlegung";
  sprache: string;
  autor: string;
  schwierigkeit: number;           // 1 bis 5; 0 unbekannt
  schwierigkeit_text: string;
  zeit: string;
  zeit_von: number | null;
  zeit_bis: number | null;
  einleitung: string;
  hauptbild: string;
  werkzeuge: Werkzeug[];
  teile: Werkzeug[];
  schritte: Anleitungsschritt[];
  abschluss: string;
}
export interface Geraeteeintrag { pfad: string; titel: string; kurz: string; bild: string; empfohlen: boolean; bauteil: string }
export interface Geraeteangaben { kurz: string; bild: string; unterkategorien: Geraeteeintrag[]; anleitungen: Geraeteeintrag[]; werkzeuge: string[] }
