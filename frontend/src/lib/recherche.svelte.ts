// Recherchemodus (WIKI-31): je Gerät an oder aus. An nehmen Markierungen und Notizen die Belege ihres Absatzes und den
// Artikel im Netz mit (für Arbeiten, die ihre Quellen nennen müssen).
const SCHLUESSEL = "nachschlag.recherche";

function gemerkt(): boolean {
  try {
    return localStorage.getItem(SCHLUESSEL) === "an";
  } catch {
    return false;
  }
}

export const recherche = $state({ an: gemerkt() });

export function rechercheUmschalten(): void {
  recherche.an = !recherche.an;
  try {
    localStorage.setItem(SCHLUESSEL, recherche.an ? "an" : "aus");
  } catch {
    // ohne Speicher gilt die Wahl nur jetzt
  }
}

/** Die Nummern der Belege in den Absätzen, die eine Auswahl berührt (vom ersten bis zum letzten berührten Absatz). */
export function belegeDerAuswahl(wurzel: HTMLElement, bereich: Range): number[] {
  const BLOCK = "p, li, dd, dt, td, th, blockquote, figcaption, h2, h3, h4";
  const block = (k: Node) => (k instanceof Element ? k : k.parentElement)?.closest(BLOCK) ?? null;
  const von = block(bereich.startContainer), bis = block(bereich.endContainer);
  if (!von || !bis) return [];
  const nummern = new Set<number>();
  for (const b of wurzel.querySelectorAll<HTMLElement>(BLOCK)) {
    const ab = b === von || !!(von.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
    const vor = b === bis || !!(bis.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_PRECEDING);
    if (!ab || !vor) continue;
    for (const m of b.querySelectorAll<HTMLElement>(".beleg[data-beleg]")) nummern.add(Number(m.dataset.beleg));
  }
  return [...nummern].sort((a, b) => a - b);
}

// Zitierform (WIKI-31), je Gerät gemerkt: so zeigt das Notizblatt den Zitiervorschlag, so kommt die Literaturliste
export type Zitierform = "einfach" | "apa" | "din" | "bibtex";
export const ZITIERFORMEN: { wert: Zitierform; titel: string }[] = [
  { wert: "einfach", titel: "Einfach" }, { wert: "apa", titel: "APA" }, { wert: "din", titel: "DIN ISO 690" },
  { wert: "bibtex", titel: "BibTeX" }];
const FORM_SCHLUESSEL = "nachschlag.zitierform";

function gemerkteForm(): Zitierform {
  try {
    const f = localStorage.getItem(FORM_SCHLUESSEL);
    return ZITIERFORMEN.some((z) => z.wert === f) ? (f as Zitierform) : "einfach";
  } catch {
    return "einfach";
  }
}

export const zitierform = $state({ form: gemerkteForm() });

export function zitierformMerken(form: string): void {
  if (!ZITIERFORMEN.some((z) => z.wert === form)) return;
  zitierform.form = form as Zitierform;
  try {
    localStorage.setItem(FORM_SCHLUESSEL, form);
  } catch {
    // ohne Speicher gilt die Wahl nur jetzt
  }
}
