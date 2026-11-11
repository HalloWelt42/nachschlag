// Die Arten der Bücher an einer Stelle: Symbol und Name je Art (Startseite, Bibliothek, Leseseite).
import type { Art } from "./typen";

export const ART_SYMBOL: Record<Art, string> = {
  enzyklopaedie: "fa-book", dokumentation: "fa-code", frage_antwort: "fa-comments", anleitung: "fa-screwdriver-wrench", uebung: "fa-graduation-cap", dateiformat: "fa-file-code",
  webseite: "fa-globe", sonstiges: "fa-box-archive",
};

export const ART_NAME: Record<Art, string> = {
  enzyklopaedie: "Nachschlagewerk", dokumentation: "Dokumentation", frage_antwort: "Frage und Antwort", anleitung: "Anleitungen", uebung: "Übungen", dateiformat: "Dateiformate",
  webseite: "Webseite", sonstiges: "unbekannte Art",
};

// Zeichen eines Buchs im Katalog (WIKI-88), solange es nicht in der Bibliothek liegt (dann zeigt die Karte sein eigenes
// Symbol): nach der Kategorie des Katalogs, sonst nach dem Bereich des Verzeichnisses. Bilder fremder Seiten übernimmt
// der Katalog nicht, darum ein eigenes Zeichen je Sammlung.
const KATALOG_ZEICHEN: Record<string, string> = {
  wikipedia: "fa-book-atlas", wiktionary: "fa-spell-check", wikiquote: "fa-quote-left", wikisource: "fa-scroll",
  wikibooks: "fa-book-open", wikiversity: "fa-graduation-cap", wikivoyage: "fa-suitcase-rolling", wikinews: "fa-newspaper",
  vikidia: "fa-child", stack_exchange: "fa-comments", gutenberg: "fa-book-bookmark", devdocs: "fa-code",
  freecodecamp: "fa-laptop-code", ifixit: "fa-screwdriver-wrench", ted: "fa-video", mooc: "fa-chalkboard-user",
  phet: "fa-flask", psiram: "fa-magnifying-glass", zimit: "fa-globe", other: "fa-box-archive", maps: "fa-map-location-dot",
  libretexts: "fa-flask-vial", videos: "fa-video", wikihow: "fa-list-check",
};

export function katalogZeichen(kategorie: string, bereich: string): string {
  return KATALOG_ZEICHEN[kategorie.toLowerCase()] ?? KATALOG_ZEICHEN[bereich.toLowerCase()] ?? "fa-book";
}
