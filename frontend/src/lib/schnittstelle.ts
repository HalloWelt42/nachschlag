// Alle Abrufe der Oberfläche an einer Stelle (über `hole` der Schale: Anmeldung, Fehler, gemeinsame Abrufe).
import { hole } from "appkern-oberflaeche";
import type { Abschnitt, Artikel, AutorenSeite, AutorSeite, Bibliotheksstand, FragenSeite, SchlagwortSeite, Sortierung, Suchergebnis,
              Steckbrief, Vorschlag } from "./typen";

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
