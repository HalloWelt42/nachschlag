// Die Bücher der Bibliothek, einmal geladen und von allen Seiten geteilt.
import { hole, seitenFehler } from "appkern-oberflaeche";
import { spracheInWorten } from "./sprache";
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

/** Wie ein Buch in reinem Text heißt (Auswahllisten, Sätze): sein Titel; tragen mehrere Bücher denselben, mit der
 *  Sprache dahinter: "Wikipedia (Deutsch)". Wo eine Buchmarke stehen kann, zeigt sie Titel und Flagge. */
export function bezeichnung(b: Buch): string {
  const gleich = bibliothek.buecher.filter((x) => x.titel === b.titel).length > 1;
  return gleich ? `${b.titel} (${sprache(b.sprache)})` : b.titel;
}

/** Bezeichnung zu einer Kennung; ein Buch, das es nicht (mehr) gibt, heißt wie seine Kennung. */
export function buchName(kennung: string): string {
  const b = buch(kennung);
  return b ? bezeichnung(b) : kennung;
}

/** Sprache eines Buchs in Worten (Kürzel nach ISO 639-3, mehrere mit Komma). */
export const sprache = spracheInWorten;

// --- Archiv der Quellen (WIKI-46) ---
/** Zählt in Suche, Stöbern und Startseite mit: aktiv oder im Archiv mit "mitnutzen". */
/** Zählt in Suche, Stöbern und Startseite mit: aktiv oder mitgenutzt, und kein Thema, das sein Gesamtbuch schon enthält
 *  (Bündel, WIKI-83; eine Regel mit dem Backend). */
export const nutzbar = (b: Buch): boolean => (!b.archiv || b.archiv.mitnutzen) && !b.buendel_im_gesamt;

/** Archivieren (zustand archiv), wieder aktiv setzen (aktiv), wie von selbst (null) oder mitnutzen; danach die
 *  Bibliothek neu, damit jede Seite den neuen Stand sieht. */
export async function archivAendern(kennung: string, aenderung: { zustand?: "archiv" | "aktiv" | null; mitnutzen?: boolean }): Promise<void> {
  await hole<Buch>(`/buecher/${encodeURIComponent(kennung)}/archiv`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(aenderung) });
  await bibliothekLaden(true);
}
