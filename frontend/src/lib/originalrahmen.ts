// Originalseite im Rahmen (WIKI-85): sie läuft mit ihren Skripten abgeschirmt ohne eigene Herkunft und spricht mit der
// App nur über die Brücke (backend/app/originalansicht/bruecke.js). Ein Ort ist, was nach dem Schein im Weg steht:
// Buch und Pfad, Abfrage und Anker, etwa "lastcodex.org_de_all_2026-11/de/atlas/index.html?filters=open#liste".

/** Nachricht der Brücke: die Seite ist an einem Ort (geladen, aus dem Verlauf, neuer Anker) oder will zu einem Verweis. */
export interface Rahmenmeldung { nachschlag: 1; art: "ort" | "verweis"; ort: string }

/** So nennt der Browser die Herkunft einer abgeschirmten Seite ohne eigene Herkunft (Absender ihrer Nachrichten). */
export const OHNE_HERKUNFT = "null";

/** Teile der Adresse einer Originalseite vor dem Ort: "", api, v1, original, Schein. */
const VOR_DEM_ORT = 5;

function entschluesselt(text: string): string {
  try { return decodeURIComponent(text); } catch { return text; }
}

/** Ein Ort in einer Form, die sich vergleichen lässt (gleich kodiert, wie ihn die Brücke oder die App schreibt). */
export function ortNormal(ort: string): string {
  const u = new URL(ort, "http://ort/");
  return entschluesselt(u.pathname.slice(1)) + u.search + entschluesselt(u.hash);
}

/** Der Ort einer Adresse der Originalseiten (auch relativ zur App), normal. */
export function ortVon(adresse: string): string {
  const u = new URL(adresse, location.href);
  return ortNormal(u.pathname.split("/").slice(VOR_DEM_ORT).join("/") + u.search + u.hash);
}

/** Wohin der Rahmen soll: die Adresse der Seite mit der Abfrage und dem Anker aus dem Weg der App. */
export function rahmenZiel(original: string, abfrage: string, anker: string): string {
  return original + (abfrage ? `?${abfrage}` : "") + (anker ? `#${encodeURIComponent(anker)}` : "");
}

/** Der Weg der App zu einem Ort: lesen/<buch>/<pfad>, die Abfrage der Seite und der Anker als Zusätze. */
export function lesenWeg(ort: string): string {
  const u = new URL(ort, "http://ort/");
  const zusatz = new URLSearchParams();
  if (u.search.length > 1) zusatz.set("abfrage", u.search.slice(1));
  if (u.hash.length > 1) zusatz.set("anker", entschluesselt(u.hash.slice(1)));
  const z = zusatz.toString();
  return `lesen/${u.pathname.slice(1)}${z ? `?${z}` : ""}`;
}

export function istRahmenmeldung(d: unknown): d is Rahmenmeldung {
  const m = d as Rahmenmeldung | null;
  return !!m && m.nachschlag === 1 && (m.art === "ort" || m.art === "verweis") && typeof m.ort === "string";
}
