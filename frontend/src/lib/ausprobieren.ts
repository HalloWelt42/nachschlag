// Ausprobieren (WIKI-48, Bauplan docs/AUSPROBIEREN.md): welche Codeblöcke sich ausprobieren lassen, der Probelauf über
// die Codeschmiede als Aufzeichner der Debug-Sitzung und die eigenen Beispiele am Artikel (die behaltenen Kopien).
import { hole, json } from "appkern-oberflaeche";
import type { Aufzeichner, Debuglauf } from "appkern-oberflaeche/code";

/** Sprachen eigener Beispiele und der Ebene Ausprobieren; was davon heute läuft, sagt der Stand der Sandbox. */
export type Codesprache = "php" | "python" | "javascript";

export interface Ausprobierstand {
  bereit: boolean;
  sprachen: Codesprache[];
  grund: string;
}

/** Ein Codeblock zum Ausprobieren: das Original aus dem Artikel oder ein eigenes Beispiel. */
export interface Probe {
  titel: string;                   // wie das Beispiel im Artikel heißt
  quelle: string;                  // Buch, aus dem es stammt
  sprache: Codesprache;
  code: string;
  buch: string;
  pfad: string;
  block: number;                   // Codeblock im Artikel (ab 0), hinter dem ein behaltenes Beispiel steht
  eigen: Beispiel | null;          // geöffnet aus einem eigenen Beispiel: Behalten ändert dieses
}

export interface Beispiel {
  id: string;
  buch_name: string;
  buch: string;
  pfad: string;
  titel: string;
  sprache: Codesprache;
  code: string;
  vorlage: string;
  block: number;
  angelegt: string;
  geaendert: string;
}

export type BeispielNeu = Pick<Beispiel, "buch" | "pfad" | "titel" | "sprache" | "code" | "vorlage" | "block">;

export const SPRACHNAMEN: Record<Codesprache, string> = { php: "PHP", python: "Python", javascript: "JavaScript" };
export const DATEINAMEN: Record<Codesprache, string> = { php: "beispiel.php", python: "beispiel.py", javascript: "beispiel.js" };
export const SYMBOLE: Record<Codesprache, string> = { php: "fa-brands fa-php", python: "fa-brands fa-python", javascript: "fa-brands fa-js" };

/** Sprache eines Codeblocks: vom Backend gefärbter Code nennt sie (`data-sprache`), sonst die der Färbung im Browser. */
export function codeSprache(pre: HTMLElement): Codesprache | null {
  const sprache = pre.dataset.sprache || pre.dataset.gefaerbt || "";
  return sprache === "php" || sprache === "python" || sprache === "javascript" ? sprache : null;
}

let stand: Promise<Ausprobierstand> | null = null;

/** Ob und was die Sandbox gerade kann; einmal je Sitzung der Seite gefragt, ein Fehler gilt als "nicht bereit". */
export function ausprobierstand(): Promise<Ausprobierstand> {
  stand ??= hole<Ausprobierstand>("/ausprobieren").catch((f) => {
    stand = null;
    return { bereit: false, sprachen: [], grund: f instanceof Error ? f.message : String(f) };
  });
  return stand;
}

/** Aufzeichner der Debug-Sitzung: der Probelauf in der Sandbox der Codeschmiede; geht es nicht, wird der Grund zur
 *  Meldung der Sitzung. */
export function probelauf(sprache: Codesprache): Aufzeichner {
  return async (code) => {
    const lauf = await hole<{ aufzeichnung: Debuglauf | null; grund: string }>("/ausprobieren", {
      method: "POST", ...json({ code, sprache, eingabe: [] }) });
    if (!lauf.aufzeichnung) throw new Error(lauf.grund || "Der Probelauf kam ohne Ergebnis zurück");
    return lauf.aufzeichnung;
  };
}

export const beispieleHolen = (buch: string, pfad: string) =>
  hole<Beispiel[]>(`/meins/beispiele?${new URLSearchParams({ buch, pfad })}`);

export const beispielAnlegen = (neu: BeispielNeu) => hole<Beispiel>("/meins/beispiele", { method: "POST", ...json(neu) });

export const beispielAendern = (id: string, titel: string, code: string) =>
  hole<Beispiel>(`/meins/beispiele/${encodeURIComponent(id)}`, { method: "PATCH", ...json({ titel, code }) });

export const beispielLoeschen = (id: string) => hole<void>(`/meins/beispiele/${encodeURIComponent(id)}`, { method: "DELETE" });
