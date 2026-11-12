// Vorlesen mit Mitlesen (WIKI-8): was vorgelesen wird und das Hervorheben des Satzes, den der Vorleser gerade spricht.
// Hervorgehoben wird über die Hervorhebungen des Browsers (CSS Highlight): der Text selbst bleibt unberührt, Markierungen
// und Notizen auch. Vorgelesen wird nur Text (WIKI-102): ein Abschnitt, der ganze Artikel oder eine Markierung, ohne
// Code, Tabellen, Steckbrief, Bilder, Formeln und Fußnotenzeichen.

const BLOECKE = "h2, h3, h4, p, li, dd, blockquote";
const UEBERSCHRIFTEN = "h2, h3, h4";
/** Teile, die nie vorgelesen werden: was kein Fließtext ist */
const KEIN_TEXT = ".steckbrief, pre, table, .beispiel, figure, figcaption, .codeblock, math, .mwe-math-element, nav, .infobox, .navbox";
/** Zeichen im Fließtext, die nicht gesprochen werden: Fußnoten und Formeln */
const NICHT_SPRECHEN = "sup, .reference, .mw-ref, .noprint, math, .mwe-math-element";
const NAME = "vorlesen";

export type Vorleseumfang = "abschnitt" | "alles";

const ebene = (el: Element) => Number(el.tagName.slice(1));

/** Der Text eines Teils ohne Fußnotenzeichen und Formeln, Leerraum zusammengezogen. */
function nurText(el: Element): string {
  const kopie = el.cloneNode(true) as Element;
  kopie.querySelectorAll(NICHT_SPRECHEN).forEach((x) => x.remove());
  return (kopie.textContent ?? "").replace(/\s+/g, " ").trim();
}

/** Was vorgelesen wird: der Abschnitt, in dem man liest (`anker`; ohne die Einleitung), mit seinen Unterabschnitten bis
 *  zur nächsten Überschrift derselben oder einer höheren Ebene, oder der ganze Artikel; nur Überschriften und Absätze. */
export function vorlesetext(wurzel: HTMLElement, umfang: Vorleseumfang, anker: string): string {
  const bloecke = [...wurzel.querySelectorAll<HTMLElement>(BLOECKE)].filter((b) => !b.closest(KEIN_TEXT));
  let auswahl = bloecke;
  if (umfang === "abschnitt") {
    const start = anker ? wurzel.querySelector<HTMLElement>(`[id="${CSS.escape(anker)}"]`) : null;
    const kopf = start?.matches(UEBERSCHRIFTEN) ? start : start?.closest<HTMLElement>(UEBERSCHRIFTEN) ?? null;
    const von = kopf ? bloecke.indexOf(kopf) : 0;
    const grenze = kopf ? ebene(kopf) : 9;                                 // Einleitung: bis zur ersten Überschrift
    const bis = bloecke.findIndex((b, i) => i > von && b.matches(UEBERSCHRIFTEN) && ebene(b) <= grenze);
    auswahl = bloecke.slice(Math.max(0, von), bis < 0 ? undefined : bis);
  }
  return auswahl.map(nurText).filter(Boolean).join("\n");
}

/** Der markierte Text, ohne das, was kein Fließtext ist; Absätze bleiben getrennt. */
export function markierungstext(bereich: Range): string {
  const huelle = document.createElement("div");
  huelle.append(bereich.cloneContents());
  huelle.querySelectorAll(KEIN_TEXT).forEach((x) => x.remove());
  const bloecke = [...huelle.querySelectorAll(BLOECKE)];
  return (bloecke.length ? bloecke.map(nurText) : [nurText(huelle)]).filter(Boolean).join("\n");
}

/** Den Satz im Text finden (ab dem zuletzt gefundenen) und hervorheben; gibt das erste Element des Satzes zurück. */
let zuletzt: Text | null = null;
export function satzHervorheben(wurzel: HTMLElement, satz: string): HTMLElement | null {
  const ziel = satz.replace(/\s+/g, " ").trim();
  if (!ziel || typeof Highlight === "undefined") return null;
  const knoten: Text[] = [];
  const gang = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT);
  for (let k = gang.nextNode() as Text | null; k; k = gang.nextNode() as Text | null) {
    if (!k.parentElement?.closest(NICHT_SPRECHEN)) knoten.push(k);           // wie gesprochen: ohne Fußnotenzeichen
  }
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
