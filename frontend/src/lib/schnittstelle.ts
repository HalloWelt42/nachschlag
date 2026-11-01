// Alle Abrufe der Oberfläche an einer Stelle (über `hole` der Schale: Anmeldung, Fehler, gemeinsame Abrufe).
import { hole } from "appkern-oberflaeche";
import type { Artikel, Bibliotheksstand, Suchergebnis, Vorschlag } from "./typen";

function pfadTeil(pfad: string): string {
  return pfad.split("/").map(encodeURIComponent).join("/");
}

function abfrage(werte: Record<string, string | number | string[]>): string {
  const p = new URLSearchParams();
  for (const [k, w] of Object.entries(werte)) {
    for (const einzeln of Array.isArray(w) ? w : [w]) p.append(k, String(einzeln));
  }
  return p.toString();
}

export const buecherHolen = () => hole<Bibliotheksstand>("/buecher");

export const artikelHolen = (buch: string, pfad: string, signal?: AbortSignal) =>
  hole<Artikel>(`/artikel/${encodeURIComponent(buch)}/${pfadTeil(pfad)}`, { signal });

export const zufallHolen = (buch: string) => hole<{ buch: string; pfad: string }>(`/zufall/${encodeURIComponent(buch)}`);

export const vorschlaegeHolen = (anfang: string, buecher: string[] = [], anzahl = 8, signal?: AbortSignal) =>
  hole<Vorschlag[]>(`/vorschlaege?${abfrage({ anfang, buecher, anzahl })}`, { signal });

export const sucheHolen = (frage: string, optionen: { buecher?: string[]; wege?: "beide" | "bedeutung" | "index"; anzahl?: number } = {},
                           signal?: AbortSignal) =>
  hole<Suchergebnis>(`/suche?${abfrage({ frage, buecher: optionen.buecher ?? [], wege: optionen.wege ?? "beide",
                                         anzahl: optionen.anzahl ?? 20 })}`, { signal });
