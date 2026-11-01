// Meins in der Oberfläche: Merkzettel, Verlauf mit Lesestand, Vorlieben des Kontos (auf allen Geräten gleich, der
// Server hält sie). Eine Stelle für alle Seiten: Artikel (Merken, Lesestand), Start (Weiterlesen, Merkzettel), Suche
// (gesucht), Merkzettel und Verlauf.
import { hole, json } from "appkern-oberflaeche";

export interface Merkeintrag {
  id: string;
  buch_name: string;
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  abschnitt: string;
  angelegt: string;
  anteil: number;
}

export interface Verlaufseintrag {
  id: string;
  art: "artikel" | "suche";
  buch_name: string;
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  abschnitt: string;
  anteil: number;
  sekunden: number;
  frage: string;
  treffer: number;
  zuletzt: string;
}

export const meins = $state<{ merkzettel: Merkeintrag[]; geladen: boolean; vorlieben: Record<string, string> }>({
  merkzettel: [], geladen: false, vorlieben: {} });

let laufend: Promise<void> | null = null;

/** Merkzettel und Vorlieben einmal laden (danach hält diese Stelle sie aktuell). */
export function meinsLaden(neu = false): Promise<void> {
  if (laufend && !neu) return laufend;
  laufend = Promise.all([hole<Merkeintrag[]>("/meins/merkzettel"), hole<Record<string, string>>("/meins/vorlieben")])
    .then(([liste, vorlieben]) => {
      meins.merkzettel = liste;
      meins.vorlieben = vorlieben;
      meins.geladen = true;
    })
    .catch(() => {
      laufend = null;           // ohne Antwort beim nächsten Mal erneut
    });
  return laufend;
}

export function gemerkt(buchName: string, pfad: string): Merkeintrag | undefined {
  return meins.merkzettel.find((m) => m.buch_name === buchName && m.pfad === pfad && !m.abschnitt);
}

export async function merken(buch: string, pfad: string, titel: string, bild = ""): Promise<void> {
  const eintrag = await hole<Merkeintrag>("/meins/merkzettel", { method: "POST", ...json({ buch, pfad, titel, bild }) });
  meins.merkzettel = [eintrag, ...meins.merkzettel.filter((m) => m.id !== eintrag.id)];
}

export async function vergessen(id: string): Promise<void> {
  await hole("/meins/merkzettel/" + encodeURIComponent(id), { method: "DELETE" });
  meins.merkzettel = meins.merkzettel.filter((m) => m.id !== id);
}

export const verlaufHolen = (anzahl = 50, ab = 0, art = "") =>
  hole<Verlaufseintrag[]>(`/meins/verlauf?${new URLSearchParams({ anzahl: String(anzahl), ab: String(ab), art })}`);

/** Lesestand melden (die Artikelseite ruft das gedrosselt beim Lesen und beim Verlassen). Fehler stören das Lesen nie. */
export async function lesestandMelden(stand: { buch: string; pfad: string; titel: string; bild: string; abschnitt: string;
                                               anteil: number; sekunden: number }): Promise<void> {
  try {
    await hole("/meins/verlauf/lesestand", { method: "PUT", ...json(stand) });
  } catch {
    /* der nächste Stand kommt ohnehin */
  }
}

export async function gesuchtMelden(frage: string, treffer: number): Promise<void> {
  try {
    await hole("/meins/verlauf/suche", { method: "POST", ...json({ frage, treffer }) });
  } catch {
    /* Verlauf ist Beiwerk der Suche */
  }
}

export async function vorliebeSetzen(schluessel: string, wert: string): Promise<void> {
  meins.vorlieben = { ...meins.vorlieben, [schluessel]: wert };
  if (!wert) delete meins.vorlieben[schluessel];
  try {
    await hole("/meins/vorlieben/" + encodeURIComponent(schluessel), { method: "PUT", ...json({ wert }) });
  } catch {
    /* bleibt bis zum Neuladen auf diesem Gerät */
  }
}

/** Zeitpunkt wie im Entwurf: "heute 02:41", "gestern 21:10", sonst "29.10." (dieses Jahr) oder "29.10.2025". */
export function wann(iso: string): string {
  const d = new Date(iso);
  const heute = new Date();
  const tag = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const tage = Math.round((tag(heute) - tag(d)) / 86_400_000);
  const uhr = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  if (tage === 0) return `heute ${uhr}`;
  if (tage === 1) return `gestern ${uhr}`;
  const datum = `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;
  return d.getFullYear() === heute.getFullYear() ? datum : datum + d.getFullYear();
}
