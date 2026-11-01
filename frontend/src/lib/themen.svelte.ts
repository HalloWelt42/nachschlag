// Themen in der Oberfläche: die Liste des Kontos und welcher Artikel in welchem Thema steht (Zuordnung), an einer
// Stelle für alle Seiten (Themen, Artikelkopf, Notizen). Ein Thema selbst holt die Seite Themen frisch.
import { hole, json } from "appkern-oberflaeche";

export interface Themenkopf {
  id: string;
  titel: string;
  eintraege: number;
  bereiche: number;
  buecher: number;
  regel: string;
  bilder: string[];
}

export interface Bereich {
  id: string;
  titel: string;
  platz: number;
}

export interface Themeneintrag {
  id: string;
  bereich: string;
  buch_name: string;
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  platz: number;
  anteil: number;
  gelesen_je: boolean;
  notizen: number;
}

export interface Thema {
  id: string;
  titel: string;
  beschreibung: string;
  regel: string;
  regel_buch: string;
  angelegt: string;
  bereiche: Bereich[];
  eintraege: Themeneintrag[];
}

export interface Zuordnung {
  thema: string;
  titel: string;
  eintrag: string;
  buch_name: string;
  pfad: string;
}

export interface Angebot {
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  auszug: string;
}

export interface Artikelangabe {
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
}

const WEG = "/meins/themen";
const weg = (thema: string, rest = "") => `${WEG}/${encodeURIComponent(thema)}${rest}`;

export const themen = $state<{ liste: Themenkopf[]; zuordnung: Zuordnung[]; geladen: boolean }>({ liste: [], zuordnung: [], geladen: false });

let laufend: Promise<void> | null = null;

/** Liste und Zuordnung laden (`neu`: auch wenn schon geladen); nach jeder Änderung neu, damit alle Seiten stimmen. */
export function themenLaden(neu = false): Promise<void> {
  if (laufend && !neu) return laufend;
  laufend = Promise.all([hole<Themenkopf[]>(WEG), hole<Zuordnung[]>(`${WEG}/zuordnung`)])
    .then(([liste, zuordnung]) => {
      themen.liste = liste;
      themen.zuordnung = zuordnung;
      themen.geladen = true;
    })
    .catch(() => {
      laufend = null;
    });
  return laufend;
}

/** In welchen Themen ein Artikel steht (Name des Buchs ohne Datum, Pfad). */
export const themenVon = (buchName: string, pfad: string): Zuordnung[] =>
  themen.zuordnung.filter((z) => z.buch_name === buchName && z.pfad === pfad);

async function nachher<T>(arbeit: Promise<T>): Promise<T> {
  const ergebnis = await arbeit;
  await themenLaden(true);
  return ergebnis;
}

export const themaHolen = (id: string) => hole<Thema>(weg(id));

export const themaAnlegen = (titel: string) => nachher(hole<Thema>(WEG, { method: "POST", ...json({ titel }) }));

export const themaAendern = (id: string, aenderung: Partial<Pick<Thema, "titel" | "beschreibung" | "regel" | "regel_buch">>) =>
  nachher(hole<Thema>(weg(id), { method: "PATCH", ...json(aenderung) }));

export const themaLoeschen = (id: string) => nachher(hole(weg(id), { method: "DELETE" }));

export const bereichAnlegen = (thema: string, titel: string) =>
  nachher(hole<Bereich>(weg(thema, "/bereiche"), { method: "POST", ...json({ titel }) }));

export const bereichAendern = (thema: string, bereich: string, aenderung: { titel?: string; platz?: number }) =>
  nachher(hole(weg(thema, `/bereiche/${encodeURIComponent(bereich)}`), { method: "PATCH", ...json(aenderung) }));

export const bereichLoeschen = (thema: string, bereich: string) =>
  nachher(hole(weg(thema, `/bereiche/${encodeURIComponent(bereich)}`), { method: "DELETE" }));

export const eintragen = (thema: string, artikel: Artikelangabe, bereich = "") =>
  nachher(hole<Themeneintrag>(weg(thema, "/eintraege"), { method: "POST", ...json({ ...artikel, bereich }) }));

export const verschieben = (thema: string, eintrag: string, bereich: string, platz: number) =>
  nachher(hole(weg(thema, `/eintraege/${encodeURIComponent(eintrag)}`), { method: "PATCH", ...json({ bereich, platz }) }));

export const austragen = (thema: string, eintrag: string) =>
  nachher(hole(weg(thema, `/eintraege/${encodeURIComponent(eintrag)}`), { method: "DELETE" }));

export const angeboteHolen = (thema: string) => hole<Angebot[]>(weg(thema, "/angebote"));

export const ablehnen = (thema: string, buch: string, pfad: string) =>
  hole(weg(thema, "/abgelehnt"), { method: "POST", ...json({ buch, pfad }) });

/** Stand eines Artikels im Thema in Worten (Entwurf themen.html). */
export function standVon(e: Themeneintrag): { text: string; art: "notiz" | "gelesen" | "" } {
  if (e.notizen) return { text: `${e.notizen} ${e.notizen === 1 ? "Notiz" : "Notizen"}`, art: "notiz" };
  if (e.anteil >= 0.95) return { text: "gelesen", art: "gelesen" };
  if (e.anteil > 0) return { text: `${Math.round(e.anteil * 100)} % gelesen`, art: "" };
  return { text: e.gelesen_je ? "angesehen" : "noch nicht gelesen", art: "" };
}
