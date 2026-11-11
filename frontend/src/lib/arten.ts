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
