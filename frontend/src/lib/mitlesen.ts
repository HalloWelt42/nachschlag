// Vorlesen mit Mitlesen (WIKI-8): der Text ab dem Abschnitt, in dem man gerade liest, und das Hervorheben des Satzes,
// den der Vorleser gerade spricht. Hervorgehoben wird über die Hervorhebungen des Browsers (CSS Highlight): der Text
// selbst bleibt unberührt, Markierungen und Notizen auch.

const BLOECKE = "h2, h3, h4, p, li, dd, blockquote";
const NAME = "vorlesen";

/** Was vorgelesen wird: Überschriften und Absätze ab dem Abschnitt `anker` (sonst von vorn), ohne Steckbrief und Code. */
export function vorlesetext(wurzel: HTMLElement, anker: string): string {
  const start = anker ? wurzel.querySelector<HTMLElement>(`[id="${CSS.escape(anker)}"]`) : null;
  return [...wurzel.querySelectorAll<HTMLElement>(BLOECKE)]
    .filter((b) => !b.closest(".steckbrief, pre, table, .beispiel") && (!start || b === start || !!(start.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)))
    .map((b) => b.innerText.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
}

/** Den Satz im Text finden (ab dem zuletzt gefundenen) und hervorheben; gibt das erste Element des Satzes zurück. */
let zuletzt: Text | null = null;
export function satzHervorheben(wurzel: HTMLElement, satz: string): HTMLElement | null {
  const ziel = satz.replace(/\s+/g, " ").trim();
  if (!ziel || typeof Highlight === "undefined") return null;
  const knoten: Text[] = [];
  const gang = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT);
  for (let k = gang.nextNode() as Text | null; k; k = gang.nextNode() as Text | null) knoten.push(k);
  let text = "";
  const wo: { k: Text; i: number }[] = [];
  for (const k of knoten) {
    for (let i = 0; i < k.data.length; i++) {
      const z = /\s/.test(k.data[i]) ? " " : k.data[i];
      if (z === " " && (text.endsWith(" ") || !text)) continue;
      text += z;
      wo.push({ k, i });
    }
  }
  const ab = zuletzt ? Math.max(0, wo.findIndex((w) => w.k === zuletzt)) : 0;
  let von = text.indexOf(ziel, ab);
  if (von < 0) von = text.indexOf(ziel);
  if (von < 0) return null;
  const bis = von + ziel.length - 1;
  const bereich = document.createRange();
  bereich.setStart(wo[von].k, wo[von].i);
  bereich.setEnd(wo[bis].k, wo[bis].i + 1);
  CSS.highlights.set(NAME, new Highlight(bereich));
  zuletzt = wo[von].k;
  return wo[von].k.parentElement;
}

export function hervorhebungWeg(): void {
  zuletzt = null;
  if (typeof CSS !== "undefined" && CSS.highlights) CSS.highlights.delete(NAME);
}
