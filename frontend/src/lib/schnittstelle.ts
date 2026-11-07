// Alle Abrufe der Oberfläche an einer Stelle (über `hole` der Schale: Anmeldung, Fehler, gemeinsame Abrufe).
import { hole } from "appkern-oberflaeche";
import type { Abschnitt, Anleitungsfrage, Anleitungsfunde, Artikel, Einordnung, Werkzeugeintrag, AutorenSeite, AutorSeite, Bibliotheksstand, FragenSeite, Katalogfilter, Laderstand, Quellstand,
              Quellvorschlag, SchlagwortSeite, Sortierung,
              Suchergebnis, Steckbrief, Verzeichnisseite, Vorschlag } from "./typen";

function pfadTeil(pfad: string): string {
  return pfad.split("/").map(encodeURIComponent).join("/");
}

function abfrage(werte: Record<string, string | number | string[]>): string {
  const p = new URLSearchParams();
  for (const [k, w] of Object.entries(werte)) {
    for (const einzeln of Array.isArray(w) ? w : [w]) p.append(k, String(einzeln));
  }
  return p.toString();
}

export const buecherHolen = () => hole<Bibliotheksstand>("/buecher");

export const artikelHolen = (buch: string, pfad: string, signal?: AbortSignal) =>
  hole<Artikel>(`/artikel/${encodeURIComponent(buch)}/${pfadTeil(pfad)}`, { signal });

export const zufallHolen = (buch: string) => hole<{ buch: string; pfad: string }>(`/zufall/${encodeURIComponent(buch)}`);

export const vorschlaegeHolen = (anfang: string, buecher: string[] = [], anzahl = 8, signal?: AbortSignal) =>
  hole<Vorschlag[]>(`/vorschlaege?${abfrage({ anfang, buecher, anzahl })}`, { signal });

export const sucheHolen = (frage: string, optionen: { buecher?: string[]; wege?: "beide" | "bedeutung" | "index"; anzahl?: number } = {},
                           signal?: AbortSignal) =>
  hole<Suchergebnis>(`/suche?${abfrage({ frage, buecher: optionen.buecher ?? [], wege: optionen.wege ?? "beide",
                                         anzahl: optionen.anzahl ?? 20 })}`, { signal });

// --- Übersetzte Suche (WIKI-40): Frage für englische Quellen, gemerkt; die Korrektur des Nutzers gilt ---
export interface Uebersetzung { frage: string; ziel: string; text: string; von: "modell" | "nutzer" | "keine"; grund: string }

export const uebersetzungHolen = (frage: string, signal?: AbortSignal) =>
  hole<Uebersetzung>(`/uebersetzung?${abfrage({ frage })}`, { signal });

export const uebersetzungKorrigieren = (frage: string, text: string) =>
  hole<Uebersetzung>("/uebersetzung", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ frage, text }) });

// --- Suchkorrektur (WIKI-41): zuerst aus dem Wortschatz der Quellen, mit `modell` (null Treffer) auch übers Modell ---
export interface Korrektur { frage: string; vorschlag: string; quelle: "" | "wortschatz" | "modell" }

export const korrekturHolen = (frage: string, buecher: string[], modell: boolean, signal?: AbortSignal) =>
  hole<Korrektur>(`/korrektur?${abfrage({ frage, buecher, modell: modell ? "true" : "false" })}`, { signal });

// --- Register (WIKI-39): ohne Buch über alle Frage-Antwort-Bücher, seitenweise ---
export const schlagwoerterHolen = (buch: string, anfang: string, ab: number, anzahl = 60) =>
  hole<SchlagwortSeite>(`/register/schlagwoerter?${abfrage({ buch, anfang, ab, anzahl })}`);

export const fragenZumSchlagwort = (wort: string, buch: string, sortierung: Sortierung, ab: number, anzahl = 30) =>
  hole<FragenSeite>(`/register/schlagwoerter/${encodeURIComponent(wort)}?${abfrage({ buch, sortierung, ab, anzahl })}`);

export const autorenHolen = (buch: string, anfang: string, ab: number, anzahl = 60) =>
  hole<AutorenSeite>(`/register/autoren?${abfrage({ buch, anfang, ab, anzahl })}`);

export const autorHolen = (buch: string, schluessel: string, ab: number, anzahl = 30) =>
  hole<AutorSeite>(`/register/autoren/${encodeURIComponent(buch)}/${encodeURIComponent(schluessel)}?${abfrage({ ab, anzahl })}`);

// --- Artikel übersetzen (WIKI-8): ein Auftrag je Artikel, das Ergebnis gilt für alle Konten ---
export interface ArtikelUebersetzung {
  titel: string;
  html: string;
  abschnitte: Abschnitt[];
  steckbrief: Steckbrief | null;
  aus: string;                     // Sprache des Originals für "aus dem ..." (Englischen)
  modell: string;
  wann: string;
  stuecke: number;
  im_original: number;             // so viele Stücke bestanden die Prüfung nicht und stehen im Original (mit lang)
  kommentare: { block: number; original: string; uebersetzt: string }[];   // Kommentare im Code, je Abschnitt umschaltbar
}

export interface Artikelstand {
  zustand: "fertig" | "laeuft" | "fehlt" | "fehler" | "nicht_moeglich" | "nicht_noetig";
  auftrag: string;
  anteil: number | null;
  schritt: string;
  grund: string;
  uebersetzung: ArtikelUebersetzung | null;
}

export const artikelstandHolen = (buch: string, pfad: string, signal?: AbortSignal) =>
  hole<Artikelstand>(`/uebersetzung/artikel/${encodeURIComponent(buch)}/${pfadTeil(pfad)}`, { signal });

export const artikelUebersetzen = (buch: string, pfad: string) =>
  hole<Artikelstand>(`/uebersetzung/artikel/${encodeURIComponent(buch)}/${pfadTeil(pfad)}`, { method: "POST" });

// --- Zitieren (WIKI-31): eine Seite in allen Zitierformen, vorab geholt (Zwischenablage nur direkt im Klick) ---
export interface Zitate {
  angaben: { titel: string; quelle: string; stand: string; url: string; autor: string; datum: string };
  einfach: string;
  apa: string;
  din: string;
  bibtex: string;
}

export const zitateHolen = (buch: string, pfad: string, signal?: AbortSignal) =>
  hole<Zitate>(`/zitate/${encodeURIComponent(buch)}/${pfadTeil(pfad)}`, { signal });

// --- Artikel für heute (WIKI-7, Startseite B): aus den eigenen Themen, mit Grund; ohne Thema null ---
export interface Heute { buch: string; pfad: string; titel: string; bild: string; einleitung: string; thema_id: string; thema: string; grund: string }

export const heuteHolen = () => hole<Heute | null>("/meins/themen/heute");

// --- Markierte Stelle übersetzen (WIKI-47): ins Deutsche, in deutschem Text ins Englische ---
export interface Stellenuebersetzung { ziel: "de" | "en"; text: string; modell: string; grund: string }

export const stellenstandHolen = () => hole<{ bereit: boolean; grund: string }>("/uebersetzung/stelle");

export const stelleUebersetzen = (text: string, ziel: "de" | "en") =>
  hole<Stellenuebersetzung>("/uebersetzung/stelle", { method: "POST", headers: { "Content-Type": "application/json" },
                                                     body: JSON.stringify({ text, ziel }) });

// --- Bücherlader (WIKI-57): Verzeichnis, Neues, Abos, Umschalten ---
const LADER = "/buecherlader";
const ohneInhalt = (weg: string, method: string) => hole<void>(`${LADER}${weg}`, { method });

export const laderstandHolen = () => hole<Laderstand>(LADER);
export const verzeichnisHolen = (f: Katalogfilter, versatz: number, grenze: number, signal?: AbortSignal) =>
  hole<Verzeichnisseite>(`${LADER}/verzeichnis?${abfrage({ ...f, nur_neu: String(f.nur_neu), nur_abonniert: String(f.nur_abonniert),
                                                         versatz, grenze })}`, { signal });
export const durchsichtStarten = () => hole<unknown>(`${LADER}/durchsicht`, { method: "POST" });
export const neuesGesehen = () => ohneInhalt("/gesehen", "POST");
export const abonnieren = (stamm: string) => ohneInhalt(`/abo/${encodeURIComponent(stamm)}`, "PUT");
export const abbestellen = (stamm: string) => ohneInhalt(`/abo/${encodeURIComponent(stamm)}`, "DELETE");
export const bestandAbonnieren = () => hole<{ anzahl: number }>(`${LADER}/abo/bestand`, { method: "POST" });
export const umschalten = (stamm: string) => ohneInhalt(`/umschalten/${encodeURIComponent(stamm)}`, "POST");
export const zurueckSchalten = (stamm: string) => ohneInhalt(`/zurueck/${encodeURIComponent(stamm)}`, "POST");

// --- Quellen des Bücherladers (WIKI-62) ---
const json = (method: string, daten: unknown) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(daten) });
export const quelleAnlegen = (art: Quellstand["art"], adresse: string, name = "") =>
  hole<Quellstand[]>(`${LADER}/quellen`, json("POST", { art, adresse, name }));
export const quelleAendern = (nr: number, aenderung: { an?: boolean; rang?: number; name?: string }) =>
  hole<Quellstand[]>(`${LADER}/quellen/${nr}`, json("PATCH", aenderung));
export const quelleEntfernen = (nr: number) => hole<Quellstand[]>(`${LADER}/quellen/${nr}`, { method: "DELETE" });
export const quellvorschlaegeHolen = () => hole<Quellvorschlag[]>(`${LADER}/quellen/vorschlaege`);

// --- Anleitungen finden (iFixit, WIKI-64) ---
export const anleitungenFinden = (buch: string, frage: Anleitungsfrage, signal?: AbortSignal) => {
  const werte: Record<string, string | number | string[]> = {};
  for (const [k, w] of Object.entries(frage)) {
    if (w === null || w === "" || w === false || (Array.isArray(w) && !w.length && k !== "sprachen")) continue;
    werte[k] = Array.isArray(w) ? w.map(String) : typeof w === "boolean" ? "true" : w;
  }
  return hole<Anleitungsfunde>(`/anleitungen/${encodeURIComponent(buch)}?${abfrage(werte)}`, { signal });
};

export const werkzeugeHolen = (buch: string, sprachen: string[], anfang = "") =>
  hole<Werkzeugeintrag[]>(`/anleitungen/${encodeURIComponent(buch)}/werkzeuge?${abfrage({ sprachen, anfang })}`);

export const einordnungHolen = (buch: string, pfad: string) =>
  hole<Einordnung>(`/anleitungen/${encodeURIComponent(buch)}/einordnung?${abfrage({ pfad })}`);
