// Leseansicht je Gerät (WIKI-7, Entwürfe artikel-a und artikel-c): A wie gewohnt in der Schale, C nur das Blatt
// (ohne Schale, Werkzeuge schwebend unten, Inhalt als Tafel). Gilt für Seiten im Lesedesign.
export type Leseansicht = "a" | "c";
export const ANSICHTEN: { wert: Leseansicht; titel: string }[] = [
  { wert: "a", titel: "Mit Schale" }, { wert: "c", titel: "Nur das Blatt" }];
const SCHLUESSEL = "nachschlag.leseansicht";

function gemerkt(): Leseansicht {
  try {
    const w = localStorage.getItem(SCHLUESSEL);
    return ANSICHTEN.some((a) => a.wert === w) ? (w as Leseansicht) : "a";
  } catch {
    return "a";
  }
}

export const leseansicht = $state({ wert: gemerkt() });

export function ansichtMerken(wert: string): void {
  if (!ANSICHTEN.some((a) => a.wert === wert)) return;
  leseansicht.wert = wert as Leseansicht;
  try {
    localStorage.setItem(SCHLUESSEL, wert);
  } catch {
    // ohne Speicher gilt die Wahl nur jetzt
  }
}
