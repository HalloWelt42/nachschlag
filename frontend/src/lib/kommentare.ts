// Kommentare im Code (WIKI-8): je Codeabschnitt zwischen Original und Übersetzung umschalten. Die Paare kommen mit der
// Übersetzung des Artikels; getauscht wird nur Text, der genau einem Kommentar entspricht, der Code bleibt unberührt.
export interface Kommentarpaar { block: number; original: string; uebersetzt: string }

/** Im Codeabschnitt die Kommentare auf Deutsch oder ins Original setzen; gibt zurück, ob etwas getauscht wurde. */
export function kommentareSetzen(pre: HTMLElement, paare: Kommentarpaar[], deutsch: boolean): boolean {
  const gang = document.createTreeWalker(pre, NodeFilter.SHOW_TEXT);
  let getauscht = false;
  for (let k = gang.nextNode() as Text | null; k; k = gang.nextNode() as Text | null) {
    for (const p of paare) {
      const von = deutsch ? p.original : p.uebersetzt, nach = deutsch ? p.uebersetzt : p.original;
      if (k.data.includes(von)) {
        k.data = k.data.replace(von, nach);
        getauscht = true;
      }
    }
  }
  return getauscht;
}
