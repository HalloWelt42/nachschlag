// Wohin die Oberfläche führt, an einer Stelle: Artikel unter /lesen/<buch>/<pfad>, die Suche unter /suche?frage=.
// Ein Treffer der Suche nimmt Frage und Abschnitt mit, damit der Artikel die Stelle zeigen kann.
import { gehe } from "appkern-oberflaeche";

export interface Herkunft {
  frage?: string;
  abschnitt?: string;
  weg?: string;
  notiz?: string;               // zu dieser Notiz springen (aus der Seite Notizen)
}

export function lesenZiel(buch: string, pfad: string, herkunft: Herkunft = {}, anker = ""): string {
  const p = new URLSearchParams();
  if (herkunft.frage) p.set("frage", herkunft.frage);
  if (herkunft.abschnitt) p.set("abschnitt", herkunft.abschnitt);
  if (herkunft.weg) p.set("weg", herkunft.weg);
  if (herkunft.notiz) p.set("notiz", herkunft.notiz);
  if (anker) p.set("anker", anker);
  const zusatz = p.toString();
  return `lesen/${buch}/${pfad}${zusatz ? "?" + zusatz : ""}`;
}

export function lesen(buch: string, pfad: string, herkunft: Herkunft = {}, anker = ""): void {
  gehe(lesenZiel(buch, pfad, herkunft, anker));
}

/** Zur Suche; `buch`: dieses Buch zuerst (der Ort, an dem gesucht wurde), `nur`: nur in diesem Buch. */
export function suchen(frage: string, buch = "", nur = false): void {
  const p = new URLSearchParams({ frage });
  if (buch) p.set("buch", buch);
  if (buch && nur) p.set("nur", "1");
  gehe(`suche?${p}`);
}

/** Ein Verweis im Artikeltext (`/lesen/<buch>/<pfad>#anker`) als Ziel der App. */
export function verweisZiel(href: string): { ziel: string; anker: string } | null {
  if (href.startsWith("/register/")) return { ziel: href.slice(1), anker: "" };     // Schlagwort, Autor (WIKI-39)
  if (!href.startsWith("/lesen/")) return null;
  const [pfad, anker = ""] = href.slice(1).split("#");
  return { ziel: anker ? `${pfad}?${new URLSearchParams({ anker: decodeURIComponent(anker) })}` : pfad, anker };
}
