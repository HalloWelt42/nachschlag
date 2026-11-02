// Ausprobieren (WIKI-48, Bauplan docs/AUSPROBIEREN.md): welche Codeblöcke sich ausprobieren lassen, der Probelauf über
// die Codeschmiede als Aufzeichner der Debug-Sitzung, die eigenen Beispiele am Artikel (die behaltenen Kopien) und je
// PHP-Fassung der Bestand an Funktionen für den Editor (WIKI-52).
import { hole, json } from "appkern-oberflaeche";
import type { Aufzeichner, Debuglauf, Funktionsbestand } from "appkern-oberflaeche/code";

/** Sprachen eigener Beispiele und der Ebene Ausprobieren; was davon heute läuft, sagt der Stand der Sandbox. */
export type Codesprache = "php" | "python" | "javascript";

/** Was die Sandbox der Codeschmiede für eine Sprache kann: die Fassungen (neueste zuerst; leer: eine) und ob der
 *  Debugger den Lauf aufzeichnet (sonst nur ausführen). */
export interface Sprachangebot {
  sprache: Codesprache;
  fassungen: string[];
  aufzeichnen: boolean;
}

export interface Ausprobierstand {
  bereit: boolean;
  sprachen: Sprachangebot[];
  grund: string;
}

/** Ein Lauf, wie die Ebene ihn zeigt; ohne Aufzeichnung leere Schritte und dazu die Hinweise (Warnungen) */
export type Probelauf = Debuglauf & { hinweise?: string };

/** Ein Codeblock zum Ausprobieren: das Original aus dem Artikel oder ein eigenes Beispiel. */
export interface Probe {
  titel: string;                   // wie das Beispiel im Artikel heißt
  quelle: string;                  // Buch, aus dem es stammt
  sprache: Codesprache;
  code: string;
  buch: string;
  pfad: string;
  block: number;                   // Codeblock im Artikel (ab 0), hinter dem ein behaltenes Beispiel steht
  fassung: string;                 // gewünschte Fassung der Sprache (Meine Fassung, "8" oder "8.3"); leer: die neueste
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
  fassung: string;                 // Fassung, in der es lief (PHP); leer: keine Wahl
  angelegt: string;
  geaendert: string;
}

export type BeispielNeu = Pick<Beispiel, "buch" | "pfad" | "titel" | "sprache" | "code" | "vorlage" | "block" | "fassung">;

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

/** Aufzeichner der Debug-Sitzung: der Probelauf in der Sandbox der Codeschmiede (in der Fassung, wo es eine Wahl gibt);
 *  geht es nicht, wird der Grund zur Meldung der Sitzung. */
export function probelauf(sprache: Codesprache, fassung: string): Aufzeichner {
  return async (code) => {
    const lauf = await hole<{ aufzeichnung: Probelauf | null; grund: string }>("/ausprobieren", {
      method: "POST", ...json({ code, sprache, fassung, eingabe: [] }) });
    if (!lauf.aufzeichnung) throw new Error(lauf.grund || "Der Probelauf kam ohne Ergebnis zurück");
    return lauf.aufzeichnung;
  };
}

/** Zahlen einer Fassung zum Vergleichen: "8.3" -> [8, 3] */
function zahlen(fassung: string): number[] {
  return fassung.split(".").map((t) => Number.parseInt(t, 10) || 0);
}

function vergleich(a: string, b: string): number {
  const x = zahlen(a), y = zahlen(b);
  for (let i = 0; i < Math.max(x.length, y.length); i++) if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) - (y[i] ?? 0);
  return 0;
}

/** Die Fassung der Sandbox zu einem Wunsch (Meine Fassung): genau sie, sonst die neueste ihrer Reihe ("8" -> 8.5),
 *  sonst die nächstältere, sonst die älteste; ohne Wunsch die neueste. `fassungen` neueste zuerst. */
export function passendeFassung(fassungen: string[], wunsch: string): string {
  if (!fassungen.length) return "";
  if (!wunsch) return fassungen[0];
  return fassungen.find((f) => f === wunsch || f.startsWith(`${wunsch}.`))
    ?? fassungen.find((f) => vergleich(f, wunsch) <= 0)
    ?? fassungen[fassungen.length - 1];
}

let funktionen: Promise<Record<string, string[]>> | null = null;

/** Je PHP-Fassung die eingebauten Funktionen (klein geschrieben); einmal je Sitzung der Seite gefragt. */
export function phpFunktionen(): Promise<Record<string, string[]>> {
  funktionen ??= hole<Record<string, string[]>>("/ausprobieren/funktionen/php").then((b) => {
    if (!Object.keys(b).length) funktionen = null;              // noch kein Bestand: beim nächsten Öffnen neu fragen
    return b;
  }).catch(() => {
    funktionen = null;
    return {};
  });
  return funktionen;
}

/** Der Bestand einer Fassung für den Editor: was es dort nicht gibt, sagt, ab oder bis wann es die Funktion gibt.
 *  Was keine Fassung kennt (Erweiterungen, die die Sandbox nicht hat), bleibt unmarkiert. */
export function bestandFuer(produkt: string, fassung: string, alle: Record<string, string[]>): Funktionsbestand | null {
  const eigene = alle[fassung];
  if (!eigene) return null;
  const mengen = Object.entries(alle).map(([f, namen]) => [f, new Set(namen)] as const);
  const hier = new Set(eigene);
  return {
    funktionen: eigene,
    pruefe: (name) => {
      if (hier.has(name)) return null;
      const mit = mengen.filter(([, m]) => m.has(name)).map(([f]) => f).sort(vergleich);
      if (!mit.length) return null;
      const aelter = mit.filter((f) => vergleich(f, fassung) < 0), neuer = mit.filter((f) => vergleich(f, fassung) > 0);
      if (!aelter.length) return `${name}() gibt es erst ab ${produkt} ${neuer[0]}, gewählt ist ${produkt} ${fassung}`;
      if (!neuer.length) return `${name}() gibt es nur bis ${produkt} ${aelter[aelter.length - 1]}, gewählt ist ${produkt} ${fassung}`;
      return `${name}() gibt es in ${produkt} ${fassung} nicht, wohl aber in ${mit.map((f) => `${produkt} ${f}`).join(", ")}`;
    },
  };
}

export const beispieleHolen = (buch: string, pfad: string) =>
  hole<Beispiel[]>(`/meins/beispiele?${new URLSearchParams({ buch, pfad })}`);

export const beispielAnlegen = (neu: BeispielNeu) => hole<Beispiel>("/meins/beispiele", { method: "POST", ...json(neu) });

export const beispielAendern = (id: string, titel: string, code: string, fassung: string) =>
  hole<Beispiel>(`/meins/beispiele/${encodeURIComponent(id)}`, { method: "PATCH", ...json({ titel, code, fassung }) });

export const beispielLoeschen = (id: string) => hole<void>(`/meins/beispiele/${encodeURIComponent(id)}`, { method: "DELETE" });
