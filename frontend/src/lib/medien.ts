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
}

export interface Medienergebnis {
  frage: string;
  medien: Medium[];
  artikel: number;
  passend: number;
}

export const medienSuchen = (frage: string) => hole<Medienergebnis>(`/medien?${new URLSearchParams({ frage })}`);

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
