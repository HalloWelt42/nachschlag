// Sprachen der Bücher an einer Stelle: Name und Flagge je Kürzel (die Bücher nennen ISO 639-3, mehrere mit Komma).
// Die Flagge steht für die Sprache, nicht für ein Land; Englisch zeigt die britische.

interface Sprache {
  name: string;
  flagge: string;            // Länderkürzel für flag-icons (fi-<kürzel>); leer: keine Flagge (mehrsprachig)
  lang: string;              // Kennzeichen für HTML (lang): Silbentrennung, Vorlesen, Rechtschreibung
}

const SPRACHEN: Record<string, Sprache> = {
  deu: { lang: "de", name: "Deutsch", flagge: "de" },
  eng: { lang: "en", name: "Englisch", flagge: "gb" },
  fra: { lang: "fr", name: "Französisch", flagge: "fr" },
  spa: { lang: "es", name: "Spanisch", flagge: "es" },
  ita: { lang: "it", name: "Italienisch", flagge: "it" },
  nld: { lang: "nl", name: "Niederländisch", flagge: "nl" },
  por: { lang: "pt", name: "Portugiesisch", flagge: "pt" },
  rus: { lang: "ru", name: "Russisch", flagge: "ru" },
  pol: { lang: "pl", name: "Polnisch", flagge: "pl" },
  mul: { lang: "", name: "mehrsprachig", flagge: "" },
};

/** Die Sprachen hinter einem Kürzel ("eng" oder "eng,deu"); Unbekanntes heißt wie sein Kürzel, ohne Flagge. */
export function sprachen(kuerzel: string): Sprache[] {
  return kuerzel.split(",").map((k) => k.trim()).filter(Boolean).map((k) => SPRACHEN[k] ?? { name: k, flagge: "", lang: "" });
}

/** Sprache in Worten, mehrere mit Komma. */
export const spracheInWorten = (kuerzel: string): string => sprachen(kuerzel).map((s) => s.name).join(", ");

/** Kennzeichen für das lang-Attribut eines Buchs (nur bei genau einer bekannten Sprache, sonst leer). */
export function htmlSprache(kuerzel: string): string {
  const liste = sprachen(kuerzel);
  return liste.length === 1 ? liste[0].lang : "";
}
