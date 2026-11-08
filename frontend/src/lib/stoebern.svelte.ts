// Stöbern in der Oberfläche: Zufallsfund mit Filtern, der Entdeckungspfad und Blättern im Buch. Der Zustand lebt hier
// (nicht in der Seite), damit Pfad und Funde bleiben, wenn man einen Artikel liest und zurückkommt.
import { hole } from "appkern-oberflaeche";

export interface Fund {
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  auszug: string;
}

export interface Nachbar {
  pfad: string;
  titel: string;
  hinweis: string;
}

export interface Pfadschritt {
  fund: Fund;
  von_hier: Nachbar[];
  erwaehnt_in: Nachbar[];
  verweist_hierher?: boolean;     // erwaehnt_in sind echte Rückverweise (eigener Index, WIKI-20)
  aehnlich: Nachbar[];
}

export interface Blatteintrag {
  pfad: string;
  titel: string;
}

export interface Buchseite {
  eintraege: Blatteintrag[];
  erste: number;
  naechste: number;
  hier: string;
}

/** Wie viele Funde "Eben gesehen" zeigt */
export const EBEN_HOECHSTENS = 4;
export const SEITE_EINTRAEGE = 13;

const pfadWeg = (buch: string, pfad: string) => `${encodeURIComponent(buch)}/${pfad.split("/").map(encodeURIComponent).join("/")}`;

export const zufallHolen = (buch: string, mitBild: boolean, ungelesen: boolean) =>
  hole<Fund>(`/stoebern/zufall/${encodeURIComponent(buch)}?${new URLSearchParams({ mit_bild: String(mitBild), ungelesen: String(ungelesen) })}`);

export const schrittHolen = (buch: string, pfad: string) => hole<Pfadschritt>(`/stoebern/schritt/${pfadWeg(buch, pfad)}`);

export const fundHolen = (buch: string, pfad: string) => hole<Fund>(`/stoebern/fund/${pfadWeg(buch, pfad)}`);

export function seiteHolen(buch: string, wo: { um?: string; buchstabe?: string; ab?: number; bis?: number }): Promise<Buchseite> {
  const p = new URLSearchParams({ anzahl: String(SEITE_EINTRAEGE) });
  for (const [k, w] of Object.entries(wo)) if (w !== undefined && w !== "") p.set(k, String(w));
  return hole<Buchseite>(`/stoebern/blaettern/${encodeURIComponent(buch)}?${p}`);
}

export const stoebern = $state<{
  buch: string;
  mitBild: boolean;
  ungelesen: boolean;
  fund: Fund | null;
  eben: Fund[];
  pfad: Fund[];                 // die Schritte bis hierher, der letzte ist der aktuelle
  schritt: Pfadschritt | null;
  seite: Buchseite | null;
  buchstabe: string;
  vorschau: Fund | null;
}>({ buch: "", mitBild: true, ungelesen: false, fund: null, eben: [], pfad: [], schritt: null, seite: null, buchstabe: "", vorschau: null });
