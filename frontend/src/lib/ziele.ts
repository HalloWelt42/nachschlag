// Wohin die Oberfläche führt, an einer Stelle: Artikel unter /lesen/<buch>/<pfad>, die Suche unter /suche?frage=.
// Ein Treffer der Suche nimmt Frage und Abschnitt mit, damit der Artikel die Stelle zeigen kann.
import { gehe } from "appkern-oberflaeche";

export interface Herkunft {
  frage?: string;
  abschnitt?: string;
  weg?: string;
}

export function lesenZiel(buch: string, pfad: string, herkunft: Herkunft = {}, anker = ""): string {
  const p = new URLSearchParams();
  if (herkunft.frage) p.set("frage", herkunft.frage);
  if (herkunft.abschnitt) p.set("abschnitt", herkunft.abschnitt);
  if (herkunft.weg) p.set("weg", herkunft.weg);
  if (anker) p.set("anker", anker);
  const zusatz = p.toString();
  return `lesen/${buch}/${pfad}${zusatz ? "?" + zusatz : ""}`;
}

export function lesen(buch: string, pfad: string, herkunft: Herkunft = {}, anker = ""): void {
  gehe(lesenZiel(buch, pfad, herkunft, anker));
}

export function suchen(frage: string): void {
  gehe(`suche?${new URLSearchParams({ frage })}`);
}

/** Ein Verweis im Artikeltext (`/lesen/<buch>/<pfad>#anker`) als Ziel der App. */
export function verweisZiel(href: string): { ziel: string; anker: string } | null {
  if (!href.startsWith("/lesen/")) return null;
  const [pfad, anker = ""] = href.slice(1).split("#");
  return { ziel: anker ? `${pfad}?${new URLSearchParams({ anker: decodeURIComponent(anker) })}` : pfad, anker };
}
