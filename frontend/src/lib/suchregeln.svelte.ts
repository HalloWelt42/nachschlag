// Regeln der Suche aus den Einstellungen (WIKI-79): Vorschläge beim Tippen (nur Titel oder auch Stellen) und ob ein
// Treffer an seiner Stelle öffnet. Einmal geholt, gilt für Suchfeld und Suchseite; bis dahin die Vorgaben.
import { hole } from "appkern-oberflaeche";

export interface Suchregeln { vorschlaege: "titel" | "titel_stellen"; an_der_stelle: boolean }

export const suchregeln = $state<Suchregeln>({ vorschlaege: "titel_stellen", an_der_stelle: true });
let geholt: Promise<void> | null = null;

export function suchregelnLaden(): Promise<void> {
  if (!geholt) {
    geholt = hole<Suchregeln>("/suche/regeln")
      .then((r) => { Object.assign(suchregeln, r); })
      .catch(() => { geholt = null; });           // beim nächsten Mal erneut fragen
  }
  return geholt;
}

/** Wohin ein Treffer öffnet: mit Abschnitt nur, wenn die Einstellung "an der Stelle öffnen" an ist. */
export const abschnittFuer = (abschnitt: string) => (suchregeln.an_der_stelle ? abschnitt : "");
