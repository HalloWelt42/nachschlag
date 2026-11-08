// Artikel aus Quellen in anderer Sprache (WIKI-8): auf diesem Gerät auf Deutsch zeigen oder in der Sprache der Quelle.
// An zeigt eine vorhandene Übersetzung gleich; eine neue stößt nur der Knopf an (jede kostet Rechenzeit der KI).
import type { ArtikelUebersetzung } from "./schnittstelle";
import type { Artikel } from "./typen";

const SCHLUESSEL = "nachschlag.deutsch";

function gemerkt(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "an";
  } catch {
    return false;
  }
}

export const deutsch = $state({ an: gemerkt() });

export function deutschMerken(an: boolean): void {
  deutsch.an = an;
  try {
    localStorage.setItem(SCHLUESSEL, an ? "an" : "aus");
  } catch {
    // ohne Speicher gilt die Wahl nur jetzt
  }
}

/** Der Artikel mit Titel, Text, Inhalt und Steckbrief der Übersetzung; Anker, Bilder und Verweise bleiben dieselben. */
export function uebersetzt(a: Artikel, u: ArtikelUebersetzung): Artikel {
  return { ...a, titel: u.titel, html: u.html, abschnitte: u.abschnitte, steckbrief: u.steckbrief };
}
