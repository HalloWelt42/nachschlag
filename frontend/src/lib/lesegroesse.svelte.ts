// Lesegröße je Gerät (WIKI-29): eine Vorgabe für alle Bücher und auf Wunsch eine eigene Stufe je Buch, denn Bücher
// sind verschieden gebaut (Enzyklopädie, Handbuch, Frage und Antwort, Originalseiten). Gemerkt im Browser dieses
// Geräts, nicht im Konto: am Telefon darf anders eingestellt sein als am Rechner. Wirkt als Zoom auf den Lesebereich.

const SCHLUESSEL = "nachschlag.lesegroesse";
export const STUFEN = [80, 90, 100, 110, 125, 140, 160];
const VORGABE = 100;
const FRUEHER_GROSS = 125;                       // der frühere Schalter "Größer lesen"

interface Gemerkt {
  vorgabe: number;
  buecher: Record<string, number>;               // Name des Buchs (ohne Datum) -> Stufe
}

function laden(): Gemerkt {
  try {
    const roh = localStorage.getItem(SCHLUESSEL);
    if (roh === "gross") return { vorgabe: FRUEHER_GROSS, buecher: {} };
    const wert = roh ? JSON.parse(roh) : null;
    if (wert && typeof wert.vorgabe === "number") return { vorgabe: wert.vorgabe, buecher: wert.buecher ?? {} };
  } catch {
    /* ohne Speicher oder mit altem Wert: Vorgabe */
  }
  return { vorgabe: VORGABE, buecher: {} };
}

export const lesegroesse = $state<Gemerkt>(laden());

function sichern(): void {
  try {
    localStorage.setItem(SCHLUESSEL, JSON.stringify(lesegroesse));
  } catch {
    /* ohne Speicher gilt die Wahl bis zum Neuladen */
  }
}

/** Die Stufe, die für ein Buch gilt (seine eigene, sonst die Vorgabe), in Prozent. */
export const groesseFuer = (buchName: string): number => lesegroesse.buecher[buchName] ?? lesegroesse.vorgabe;

/** Nächste Stufe in eine Richtung (am Rand bleibt sie). */
export function naechste(wert: number, richtung: 1 | -1): number {
  const i = STUFEN.indexOf(wert);
  const von = i >= 0 ? i : STUFEN.indexOf(VORGABE);
  return STUFEN[Math.min(STUFEN.length - 1, Math.max(0, von + richtung))];
}

export function vorgabeSetzen(wert: number): void {
  lesegroesse.vorgabe = wert;
  sichern();
}

/** Eigene Stufe für ein Buch; null: es folgt wieder der Vorgabe. */
export function buchSetzen(buchName: string, wert: number | null): void {
  if (wert === null) delete lesegroesse.buecher[buchName];
  else lesegroesse.buecher[buchName] = wert;
  sichern();
}
