// Meins in der Oberfläche: Merkzettel, Notizen, Verlauf mit Lesestand, Vorlieben des Kontos (auf allen Geräten gleich,
// der Server hält sie). Eine Stelle für alle Seiten: Artikel (Merken, Notizen, Lesestand), Start (Weiterlesen,
// Merkzettel), Suche (gesucht), Merkzettel, Notizen und Verlauf.
import { hole, json } from "appkern-oberflaeche";
import type { Beleg } from "./typen";

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

/** Ein Bild an einer Notiz (WIKI-51); die Datei liegt in der Kellerwolke, Nachschlag liefert sie aus. */
export interface Notizbild {
  id: string;
  knoten: string;
  name: string;
  typ: string;
  groesse: number;
  angelegt: string;
}

/** Notiz am ganzen Artikel (ohne Zitat) oder an einer markierten Stelle; ohne Text ist sie eine Markierung. */
export interface Notiz {
  id: string;
  buch_name: string;
  buch: string;
  pfad: string;
  titel: string;
  bild: string;
  abschnitt: string;
  zitat: string;
  davor: string;
  text: string;
  belege: Beleg[];                 // Recherchemodus: Belege der Stelle (WIKI-31)
  quelle_url: string;              // Recherchemodus: der Artikel im Netz
  bilder: Notizbild[];             // Bilder an der Notiz (WIKI-51)
  angelegt: string;
  geaendert: string;
}

export type NotizNeu = Pick<Notiz, "buch" | "pfad" | "titel" | "bild" | "abschnitt" | "zitat" | "davor" | "text">
  & Partial<Pick<Notiz, "belege" | "quelle_url">>;

export const meins = $state<{ merkzettel: Merkeintrag[]; notizen: Notiz[]; geladen: boolean; vorlieben: Record<string, string> }>({
  merkzettel: [], notizen: [], geladen: false, vorlieben: {} });

let laufend: Promise<void> | null = null;

/** Merkzettel, Notizen und Vorlieben einmal laden (danach hält diese Stelle sie aktuell). */
export function meinsLaden(neu = false): Promise<void> {
  if (laufend && !neu) return laufend;
  laufend = Promise.all([hole<Merkeintrag[]>("/meins/merkzettel"), hole<Notiz[]>("/meins/notizen"),
                         hole<Record<string, string>>("/meins/vorlieben")])
    .then(([liste, notizen, vorlieben]) => {
      meins.merkzettel = liste;
      meins.notizen = notizen;
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

export async function notieren(neu: NotizNeu): Promise<Notiz> {
  const notiz = await hole<Notiz>("/meins/notizen", { method: "POST", ...json(neu) });
  meins.notizen = [notiz, ...meins.notizen];
  return notiz;
}

// Notizen, deren Löschen läuft oder durch ist: ein Speichern, das erst danach antwortet, holt sie nicht in die Liste
// zurück (sonst stünde die Markierung nach dem Löschen wieder da)
const geloescht = new Set<string>();

export async function notizAendern(id: string, text: string): Promise<Notiz> {
  const notiz = await hole<Notiz>("/meins/notizen/" + encodeURIComponent(id), { method: "PATCH", ...json({ text }) });
  if (!geloescht.has(id)) meins.notizen = [notiz, ...meins.notizen.filter((n) => n.id !== id)];
  return notiz;
}

/** so lange darf das Hochladen eines Bilds dauern (Fotos vom Telefon über ein langsames Netz) */
const HOCHLADEN_MS = 120_000;

/** Ein Bild an die Notiz (aus der Zwischenablage oder einer Datei); die Notiz kommt mit ihrer neuen Liste zurück. */
export async function notizBildAnfuegen(id: string, datei: File): Promise<Notiz> {
  const formular = new FormData();
  formular.append("datei", datei, datei.name || "Bild");
  const notiz = await hole<Notiz>(`/meins/notizen/${encodeURIComponent(id)}/bilder`,
                                  { method: "POST", body: formular, zeitgrenzeMs: HOCHLADEN_MS });
  if (!geloescht.has(id)) meins.notizen = [notiz, ...meins.notizen.filter((n) => n.id !== id)];
  return notiz;
}

export async function notizBildEntfernen(id: string, bild: string): Promise<void> {
  await hole(`/meins/notizen/${encodeURIComponent(id)}/bilder/${encodeURIComponent(bild)}`, { method: "DELETE" });
  meins.notizen = meins.notizen.map((n) => (n.id === id ? { ...n, bilder: n.bilder.filter((b) => b.id !== bild) } : n));
}

/** Adresse eines Bilds für <img> (Lesezugang über das Cookie unter /api/v1/inhalt) */
export const notizBildAdresse = (id: string, bild: string) =>
  `/api/v1/inhalt/notizbilder/${encodeURIComponent(id)}/${encodeURIComponent(bild)}`;

/** Bilder aus Einfügen oder Ablegen (Zwischenablage, Ziehen); andere Dateien und Text bleiben, wo sie hingehören. */
export function bilderAus(daten: DataTransfer | null | undefined): File[] {
  return Array.from(daten?.files ?? []).filter((f) => f.type.startsWith("image/"));
}

export async function notizLoeschen(id: string): Promise<void> {
  geloescht.add(id);
  try {
    await hole("/meins/notizen/" + encodeURIComponent(id), { method: "DELETE" });
  } catch (f) {
    geloescht.delete(id);
    throw f;
  }
  meins.notizen = meins.notizen.filter((n) => n.id !== id);
}

// Die letzte Meldung des Lesestands: wer den Verlauf liest, wartet sie ab (sonst zeigte die Startseite direkt nach
// dem Verlassen eines Artikels noch den alten Stand)
let meldung: Promise<void> = Promise.resolve();

export async function verlaufHolen(anzahl = 50, ab = 0, art = ""): Promise<Verlaufseintrag[]> {
  await meldung;
  return hole<Verlaufseintrag[]>(`/meins/verlauf?${new URLSearchParams({ anzahl: String(anzahl), ab: String(ab), art })}`);
}

/** Lesestand melden (die Artikelseite ruft das gedrosselt beim Lesen und beim Verlassen). Fehler stören das Lesen nie. */
export function lesestandMelden(stand: { buch: string; pfad: string; titel: string; bild: string; abschnitt: string;
                                         anteil: number; sekunden: number }): Promise<void> {
  meldung = hole("/meins/verlauf/lesestand", { method: "PUT", ...json(stand) }).then(
    () => undefined,
    () => undefined,                                   // der nächste Stand kommt ohnehin
  );
  return meldung;
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
