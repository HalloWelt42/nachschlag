// Stellen im Artikeltext: aus einer Auswahl wird ein Zitat mit dem Text davor (so unterscheiden sich gleiche Stellen),
// und eine gespeicherte Stelle wird im Text wiedergefunden und markiert. Gerechnet wird über den Text des Artikels mit
// zusammengefassten Leerräumen; was die Oberfläche selbst einfügt (Knöpfe, Fassungsmarken), zählt nicht mit.

const DAVOR_ZEICHEN = 60;
const ZITAT_HOECHSTENS = 4000;
const NICHT_TEXT = "button, .gilt-marke, .notiz-marke";

export interface Stelle {
  zitat: string;
  davor: string;
  abschnitt: string;
}

export interface Markierbar {
  id: string;
  zitat: string;
  davor: string;
  text: string;
}

interface Textkarte {
  text: string;                                    // zusammengefasst: Leerräume zu einem Leerzeichen
  roh: { knoten: Text; versatz: number }[];        // je Zeichen von `text`: wo es im DOM steht
}

function karte(wurzel: HTMLElement): Textkarte {
  const gang = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT, {
    acceptNode: (k) => (k.parentElement?.closest(NICHT_TEXT) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  let text = "";
  const roh: Textkarte["roh"] = [];
  for (let k = gang.nextNode() as Text | null; k; k = gang.nextNode() as Text | null) {
    for (let i = 0; i < k.data.length; i++) {
      const z = /\s/.test(k.data[i]) ? " " : k.data[i];
      if (z === " " && (text.endsWith(" ") || !text)) continue;
      text += z;
      roh.push({ knoten: k, versatz: i });
    }
  }
  return { text, roh };
}

const fassen = (s: string) => s.replace(/\s+/g, " ").trim();

const FOLGT = Node.DOCUMENT_POSITION_FOLLOWING;

/** Index in `text` zu einem Punkt der Auswahl (Knoten und Versatz wie in Range): das erste Zeichen ab diesem Punkt. */
function index(k: Textkarte, knoten: Node, versatz: number): number {
  let ab: (t: Text) => boolean;
  if (knoten instanceof Text) {
    ab = (t) => t === knoten || !!(knoten.compareDocumentPosition(t) & FOLGT);
  } else if (versatz < knoten.childNodes.length) {
    const vor = knoten.childNodes[versatz];                       // Punkt vor diesem Kind: es selbst und alles danach
    ab = (t) => vor === t || !!(vor.compareDocumentPosition(t) & FOLGT);
  } else {
    ab = (t) => !knoten.contains(t) && !!(knoten.compareDocumentPosition(t) & FOLGT);   // Punkt hinter dem Element
  }
  const i = k.roh.findIndex((r) => ab(r.knoten) && (r.knoten !== knoten || r.versatz >= versatz));
  return i < 0 ? k.text.length : i;
}

/** Die markierte Stelle zu einer Auswahl im Artikeltext; null, wenn die Auswahl nicht (nur) im Text liegt. */
export function stelleAus(wurzel: HTMLElement, auswahl: Selection | null): Stelle | null {
  if (!auswahl || auswahl.isCollapsed || !auswahl.rangeCount) return null;
  const r = auswahl.getRangeAt(0);
  if (!wurzel.contains(r.commonAncestorContainer)) return null;
  const k = karte(wurzel);
  const von = index(k, r.startContainer, r.startOffset);
  const bis = index(k, r.endContainer, r.endOffset);
  const zitat = k.text.slice(von, bis).trim();
  if (!zitat || zitat.length > ZITAT_HOECHSTENS) return null;
  return { zitat, davor: k.text.slice(Math.max(0, von - DAVOR_ZEICHEN), von).trimStart(), abschnitt: abschnittVor(wurzel, r.startContainer) };
}

/** Titel der letzten Überschrift vor einem Punkt im Text. */
function abschnittVor(wurzel: HTMLElement, punkt: Node): string {
  let titel = "";
  for (const h of wurzel.querySelectorAll<HTMLElement>("h2, h3, h4")) {
    if (h.compareDocumentPosition(punkt) & Node.DOCUMENT_POSITION_FOLLOWING) titel = h.innerText.trim();
  }
  return titel;
}

/** Wo eine gespeicherte Stelle heute im Text steht: das Vorkommen, vor dem `davor` steht, sonst das erste. */
function finden(k: Textkarte, s: Markierbar): [number, number] | null {
  const zitat = fassen(s.zitat), davor = fassen(s.davor);
  let erstes = -1;
  for (let i = k.text.indexOf(zitat); i >= 0; i = k.text.indexOf(zitat, i + 1)) {
    if (erstes < 0) erstes = i;
    if (!davor || k.text.slice(0, i).trimEnd().endsWith(davor)) return [i, i + zitat.length];
  }
  return erstes < 0 ? null : [erstes, erstes + zitat.length];
}

/** Markierungen neu setzen: jede Stelle als `mark.notiz`, dahinter ein Zeichen, wenn sie eine Notiz trägt. Stellen,
 *  die der Text nicht mehr enthält (neue Fassung des Buchs), bleiben ohne Markierung; die Notiz bleibt. */
export function markieren(wurzel: HTMLElement, stellen: Markierbar[]): void {
  for (const m of wurzel.querySelectorAll(".notiz-marke")) m.remove();
  for (const m of wurzel.querySelectorAll("mark.notiz")) m.replaceWith(...m.childNodes);
  wurzel.normalize();
  for (const s of stellen) {
    if (!s.zitat) continue;
    const k = karte(wurzel);               // nach jeder Stelle neu: das Einwickeln teilt Textknoten
    const fund = finden(k, s);
    if (!fund) continue;
    const teile = new Map<Text, [number, number]>();
    for (let i = fund[0]; i < fund[1]; i++) {
      const { knoten, versatz } = k.roh[i];
      const t = teile.get(knoten);
      teile.set(knoten, t ? [t[0], versatz + 1] : [versatz, versatz + 1]);
    }
    let letzte: HTMLElement | null = null;
    for (const [knoten, [von, bis]] of teile) {
      const stueck = knoten.splitText(von);
      stueck.splitText(bis - von);
      const mark = document.createElement("mark");
      mark.className = "notiz";
      mark.dataset.notiz = s.id;
      stueck.replaceWith(mark);
      mark.append(stueck);
      letzte = mark;
    }
    if (letzte && s.text.trim()) {
      const marke = document.createElement("span");
      marke.className = "notiz-marke";
      marke.dataset.notiz = s.id;
      marke.title = "Notiz zeigen";
      marke.innerHTML = '<i class="fa-solid fa-note-sticky"></i>';
      letzte.after(marke);
    }
  }
}
