// Bündel (WIKI-83): Bücher derselben Herkunft (etwa die Übungsbücher von freeCodeCamp) stehen in jeder Bücherliste als
// eine Ebene: das Gesamtbuch öffnet sie, darunter die Themen. Welche Bücher ein Bündel bilden, sagt das Backend (Felder
// buendel*); hier wird nur geordnet. Ein Bündel steht dort, wo sein erstes Buch in der Liste stand.
import type { Buch } from "./typen";

export type Listeneintrag =
  | { art: "buch"; buch: Buch }
  | { art: "buendel"; kennung: string; titel: string; gesamt: Buch | null; themen: Buch[] };

export function ordnen(buecher: Buch[]): Listeneintrag[] {
  const aus: Listeneintrag[] = [];
  const buendel = new Map<string, Extract<Listeneintrag, { art: "buendel" }>>();
  for (const b of buecher) {
    if (!b.buendel) { aus.push({ art: "buch", buch: b }); continue; }
    let e = buendel.get(b.buendel);
    if (!e) {
      e = { art: "buendel", kennung: b.buendel, titel: b.buendel_titel, gesamt: null, themen: [] };
      buendel.set(b.buendel, e);
      aus.push(e);
    }
    if (b.buendel_gesamt) e.gesamt = b;
    else e.themen.push(b);
  }
  return aus;
}

/** Dieselben Bücher in der Reihenfolge der Ebenen (Gesamtbuch, dann seine Themen), etwa für eine Auswahl. */
export function reihenfolge(buecher: Buch[]): Buch[] {
  return ordnen(buecher).flatMap((e) => (e.art === "buch" ? [e.buch] : [...(e.gesamt ? [e.gesamt] : []), ...e.themen]));
}

/** Der Name eines Themas ohne den Namen der Ebene davor ("FreeCodeCamp JavaScript" heißt im Bündel "JavaScript"). */
export function themaTitel(b: Buch): string {
  const vorne = b.buendel_titel.trim();
  const rest = vorne && b.titel.toLowerCase().startsWith(vorne.toLowerCase()) ? b.titel.slice(vorne.length).trim() : "";
  return rest || b.titel;
}

/** Hinweis für eine Auswahl: zu welcher Ebene ein Thema gehört. */
export function buendelHinweis(b: Buch): string | undefined {
  return b.buendel ? (b.buendel_gesamt ? `alle Themen von ${b.buendel_titel}` : `Thema im Bündel ${b.buendel_titel}`) : undefined;
}
