// Stand der Übungen in diesem Browser (WIKI-66): der eigene Code je Aufgabe und welche Aufgaben gelöst sind (alle
// Prüfpunkte erfüllt). Nur eine Annehmlichkeit des Geräts: fehlt der Speicher (privates Fenster), geht alles weiter,
// nur ohne Erinnerung.

const CODE = "nachschlag_uebung_code";
const GELOEST = "nachschlag_uebung_geloest";

function lesen(schluessel: string): string | null {
  try { return localStorage.getItem(schluessel); } catch { return null; }
}

function schreiben(schluessel: string, wert: string | null): void {
  try {
    if (wert === null) localStorage.removeItem(schluessel);
    else localStorage.setItem(schluessel, wert);
  } catch { /* ohne Speicher geht es ohne Erinnerung weiter */ }
}

/** Der eigene Code einer Aufgabe, sonst null (dann gilt der Startcode). */
export function eigenerCode(buch: string, pfad: string): string | null {
  return lesen(`${CODE}:${buch}:${pfad}`);
}

/** Merkt den eigenen Code; gleicht er dem Startcode, wird nichts gemerkt. */
export function codeMerken(buch: string, pfad: string, code: string, startcode: string): void {
  schreiben(`${CODE}:${buch}:${pfad}`, code === startcode ? null : code);
}

export function geloeste(buch: string): Set<string> {
  try { return new Set(JSON.parse(lesen(`${GELOEST}:${buch}`) ?? "[]") as string[]); } catch { return new Set(); }
}

export function geloestMerken(buch: string, pfad: string): void {
  const alle = geloeste(buch);
  alle.add(pfad);
  schreiben(`${GELOEST}:${buch}`, JSON.stringify([...alle]));
}
