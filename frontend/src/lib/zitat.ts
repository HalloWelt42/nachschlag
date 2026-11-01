// Ein Zitat mit Herkunft, an einer Stelle für die Leiste über dem Text und das Notizblatt:
// "Text" (Artikel, Abschnitt, Buch). Gerade Anführungszeichen, wie überall in der App.
export function zitatMitHerkunft(zitat: string, titel: string, abschnitt: string, buch: string): string {
  return `"${zitat}" (${[titel, abschnitt, buch].filter(Boolean).join(", ")})`;
}

/** So lange zeigt ein Knopf nach dem Kopieren "Kopiert" (oder "Geht nicht"). */
export const RUECKMELDUNG_MS = 1500;
