// Die Bücher der Bibliothek, einmal geladen und von allen Seiten geteilt.
import { seitenFehler } from "appkern-oberflaeche";
import { buecherHolen } from "./schnittstelle";
import type { Buch } from "./typen";

export const bibliothek = $state<{ buecher: Buch[]; fehler: string[]; geladen: boolean; meldung: string }>({
  buecher: [], fehler: [], geladen: false, meldung: "" });

let laufend: Promise<void> | null = null;

export function bibliothekLaden(neu = false): Promise<void> {
  if (laufend && !neu) return laufend;
  laufend = buecherHolen()
    .then((stand) => {
      bibliothek.buecher = stand.buecher;
      bibliothek.fehler = stand.fehler;
      bibliothek.meldung = "";
    })
    .catch((f) => {
      bibliothek.meldung = seitenFehler(f);
      laufend = null;
    })
    .finally(() => {
      bibliothek.geladen = true;
    });
  return laufend;
}

export function buch(kennung: string): Buch | undefined {
  return bibliothek.buecher.find((b) => b.kennung === kennung);
}

/** Das Buch, mit dem man ohne Wahl beginnt: das größte mit eigenem Lesedesign, sonst das größte. */
export function hauptbuch(): Buch | undefined {
  const sortiert = [...bibliothek.buecher].sort((a, b) => b.artikel - a.artikel);
  return sortiert.find((b) => b.faehigkeiten.lesedesign) ?? sortiert[0];
}

export function zahl(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString("de-DE", { maximumFractionDigits: 2 })} Mio`;
  return n.toLocaleString("de-DE");
}

export function datum(stand: string): string {
  const [j, m, t] = stand.split("-");
  return t ? `${t}.${m}.${j}` : m ? `${m}.${j}` : stand;
}

const SPRACHEN: Record<string, string> = { deu: "Deutsch", eng: "Englisch", fra: "Französisch", spa: "Spanisch", ita: "Italienisch",
                                           nld: "Niederländisch", por: "Portugiesisch", rus: "Russisch", mul: "mehrsprachig" };

/** Sprache eines Buchs in Worten (das Buch nennt sie als Kürzel nach ISO 639-3, mehrere mit Komma). */
export function sprache(kuerzel: string): string {
  return kuerzel.split(",").map((k) => SPRACHEN[k.trim()] ?? k.trim()).join(", ");
}
