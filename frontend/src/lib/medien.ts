// Medien: Bilder der Artikel mit Unterschrift (Mediensuche, große Bildansicht). Die Dateien liefert /inhalt/medien.
import { hole } from "appkern-oberflaeche";

export interface Medium {
  buch: string;
  pfad: string;
  artikel: string;
  abschnitt: string;
  bild: string;
  breite: number;
  hoehe: number;
  unterschrift: string;
  datei: string;
  /** bild, karte oder ton (WIKI-24); beim Ton ist `bild` die Adresse des Tons */
  art: "bild" | "karte" | "ton";
  /** der Bildholer hat das große Bild schon geholt */
  gross: boolean;
}

export type Medienart = "" | "bild" | "karte" | "ton";

export interface Medienergebnis {
  frage: string;
  medien: Medium[];
  artikel: number;
  passend: number;
}

export const medienSuchen = (frage: string, art: Medienart = "", gross = false) =>
  hole<Medienergebnis>(`/medien?${new URLSearchParams({ frage, ...(art ? { art } : {}), ...(gross ? { gross: "true" } : {}) })}`);

export const medienImArtikel = (buch: string, pfad: string) =>
  hole<Medium[]>(`/medien/artikel/${encodeURIComponent(buch)}/${pfad.split("/").map(encodeURIComponent).join("/")}`);

/** Unterschrift in Teile zerlegt, Wörter der Frage hervorgehoben (als Text gesetzt, nie als HTML). */
export function hervorheben(text: string, frage: string): { text: string; treffer: boolean }[] {
  const woerter = frage.split(/\s+/).filter((w) => w.length > 1).map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!woerter.length) return [{ text, treffer: false }];
  const muster = new RegExp(`(${woerter.join("|")})`, "gi");
  // Teilen an einer Klammergruppe: die Treffer stehen an den ungeraden Stellen
  return text.split(muster).map((t, i) => ({ text: t, treffer: i % 2 === 1 })).filter((t) => t.text);
}

// --- Große Bilder des Bildholers (WIKI-80) ---
export interface Grossangaben {
  breite: number; hoehe: number; original: number; urheber: string; lizenz: string; lizenz_url: string; seite_url: string;
}
const MEDIENWEG = "/api/v1/inhalt/medien/";

/** Angaben zum großen Bild hinter einer Bildadresse des Medienwegs; null, wenn es (noch) keins gibt. */
export async function grossAngaben(bild: string): Promise<Grossangaben | null> {
  if (!bild.startsWith(MEDIENWEG)) return null;
  try {
    return await hole<Grossangaben>(`/bilder/angaben/${bild.slice(MEDIENWEG.length).split("?")[0]}`);
  } catch {
    return null;
  }
}

/** Die Adresse des großen Bilds zu einer Bildadresse des Medienwegs. */
export const grossAdresse = (bild: string) => `${bild.split("?")[0]}?gross=1`;
