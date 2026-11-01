// Leseansicht je Gerät (WIKI-7, Entwürfe artikel-a, -b und -c): A wie gewohnt in der Schale, B dazu rechts die
// Wissensleiste (Steckbrief, Notizen, Medien; auf schmalen Schirmen wie A), C nur das Blatt (ohne Schale, Werkzeuge
// schwebend unten, Inhalt als Tafel). Gilt für Seiten im Lesedesign.
export type Leseansicht = "a" | "b" | "c";
export const ANSICHTEN: { wert: Leseansicht; titel: string }[] = [
  { wert: "a", titel: "Mit Schale" }, { wert: "b", titel: "Mit Wissensleiste" }, { wert: "c", titel: "Nur das Blatt" }];
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

// Startseite je Gerät (WIKI-7, Entwürfe start-a und start-b): A mit der Suche in der Mitte, B wie ein Magazin mit dem
// Artikel für heute aus den eigenen Themen (die Suche steht dann nur im Kopf)
export type Startansicht = "a" | "b";
export const STARTANSICHTEN: { wert: Startansicht; titel: string }[] = [
  { wert: "a", titel: "Suche zuerst" }, { wert: "b", titel: "Magazin" }];
const START_SCHLUESSEL = "nachschlag.startansicht";

function gemerkterStart(): Startansicht {
  try {
    return localStorage.getItem(START_SCHLUESSEL) === "b" ? "b" : "a";
  } catch {
    return "a";
  }
}

export const startansicht = $state({ wert: gemerkterStart() });

export function startansichtMerken(wert: string): void {
  if (!STARTANSICHTEN.some((a) => a.wert === wert)) return;
  startansicht.wert = wert as Startansicht;
  try {
    localStorage.setItem(START_SCHLUESSEL, wert);
  } catch {
    // ohne Speicher gilt die Wahl nur jetzt
  }
}
