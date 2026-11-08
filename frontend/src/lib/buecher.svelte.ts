// Als Buch (WIKI-45): Typen und Wege der Schnittstelle (/meins/buecher, /buchvorlagen) an einer Stelle, dazu Vorlagen,
// Katalog der Teile und Regal als gemeinsamer Stand für alle Seiten (Als Buch, Probekapitel, Vorlagen, Eigene Bücher).
import { hole, json } from "appkern-oberflaeche";

export type Teilart = "titelseite" | "inhalt" | "kapitel" | "abc" | "kapiteleinleitung" | "blick" | "umgeformt" | "originaltext"
  | "kasten" | "notizen" | "fragen" | "glossar" | "literatur";
export type Herkunft = "thema" | "selbst" | "ki" | "meins" | "buch";
export type FuerWen = "erwachsene" | "jugendliche" | "kinder";
export type Laenge = "original" | "haelfte" | "wichtigste";
export type Ton = "sachlich" | "erzaehlend" | "locker";
export type Farbe = "petrol" | "violett" | "honig" | "koralle" | "stahl";
export type Bildwahl = "im_text" | "eins_gross" | "ohne";
export type Seitengroesse = "a5" | "a4" | "a4_zwei";
export type Wann = "jetzt" | "nachts";

export interface Teil { art: Teilart; titel: string; anweisung: string }
export interface Teilangabe { art: Teilart; titel: string; herkunft: Herkunft; ebene: "buch" | "gliederung" | "kapitel" | "artikel";
  wechsel: Teilart | null; beschreibung: string }
export interface Aufbau { vorn: Teil[]; gliederung: "kapitel" | "abc"; innen: Teil[]; hinten: Teil[] }
export interface Anweisung { ton: Ton; fuer_wen: FuerWen; laenge: Laenge; fragen: number; zusatz: string }
export interface Gestaltung { schrift: "serifen" | "ohne"; farbe: Farbe; bilder: Bildwahl }
export interface Vorlage { kennung: string; titel: string; symbol: string; beschreibung: string; untertitel: string; mitgeliefert: boolean;
  kopiert_aus: string; kopiert_am: string; aufbau: Aufbau; anweisung: Anweisung; gestaltung: Gestaltung; ki: boolean }
export interface Vorlagenliste { vorlagen: Vorlage[]; ordner: string; hinweis: string }
export interface Teilkatalog { teile: Teilangabe[]; regeln: string[] }

export interface Kapitelwahl { bereich: string; an: boolean }
export interface Bestellung { thema: string; vorlage: string; kapitel: Kapitelwahl[]; notizen: boolean; markierungen: boolean; bilder: boolean;
  steckbriefe: boolean; uebersetzung: boolean; fuer_wen: FuerWen; laenge: Laenge; fragen: number; epub: boolean; pdf: boolean;
  seiten: Seitengroesse; titelbild: string; wann: Wann }
export interface Kapitelangabe { bereich: string; titel: string; artikel: number; lesbar: number; bilder: string[] }
export interface Buchwahl { thema: string; titel: string; artikel: number; kapitel: Kapitelangabe[]; notizen: number; markierungen: number;
  bilder: number; steckbriefe: number; fremd: { titel: string; sprache: string; uebersetzt: boolean }[]; titelbilder: string[];
  auszug_titel: string; auszug: string;
  modell: string; leitstelle: boolean; pdf: string; ablage: string; letzte: Bestellung | null }
export interface Schaetzung { artikel: number; kapitel: number; zeichen: number; seiten: number; schritte: { titel: string; sekunden: number }[];
  sekunden: number; tempo: number; gemessen: boolean; modell: string; beginn: string; ende: string; nacht_reicht: boolean;
  probe_titel: string; probe_sekunden: number }

export interface Bild { adresse: string; unterschrift: string; urheber: string; lizenz: string }
export interface Belegt { text: string; belege: number[] }
export interface Kasten { titel: string; punkte: Belegt[] }
export interface Randnotiz { text: string; zitat: string }
export interface Absatz { text: string; html: string; art: "absatz" | "punkt" | "tabelle" | "zitat" | "code"; liste: number; geordnet: boolean;
  ueberschrift: string; ebene: number; belege: number[]; ohne_beleg: string[]; hervorgehoben: boolean; markiert: string[];
  notizen: Randnotiz[]; bilder: Bild[] }
export interface Buchartikel { eintrag: string; titel: string; buch: string; pfad: string; sprache: string; leitbild: Bild | null;
  steckbrief: string; blick: Kasten | null; kaesten: Kasten[]; absaetze: Absatz[]; notizen: Randnotiz[]; zeichen_original: number }
export interface Frage { frage: string; antwort: string; belege: number[] }
export interface Buchkapitel { titel: string; einleitung: Belegt[]; artikel: Buchartikel[]; fragen: Frage[] }
export interface Satzhinweis { artikel: string; absatz: number; text: string; art: "satz" | "zahl" | "beleg" }
export interface Pruefung { zahlen: number; zahlen_gefunden: number; absaetze: number; belegt: number; hinweise: Satzhinweis[] }
export interface Probe { thema: string; eintrag: string; vorlage: string; vorlage_titel: string; fuer_wen: FuerWen; laenge: Laenge;
  quelle: string; zeichen_original: number; original: { nr: number; text: string; ueberschrift: string }[]; artikel: Buchartikel;
  kapitel: Buchkapitel; pruefung: Pruefung; sekunden: number; seiten: number; wann: string }

export interface Baustufe { titel: string; zustand: "offen" | "jetzt" | "fertig"; anteil: number; text: string }
export interface Baustand { auftrag: string; zustand: "wartet" | "laeuft" | "fehler" | "abgebrochen" | "unterbrochen"; grund: string;
  titel: string; beschreibung: string; thema: string; titelbild: string; vorlage_titel: string; begonnen: string; anteil: number;
  tempo: number; fertig_gegen: string; hinweise: number; stufen: Baustufe[] }
export interface Buchformat { format: "epub" | "pdf"; titel: string; pfad: string; groesse: number }
export interface Eigenbuch { id: string; thema: string; titel: string; vorlage: string; vorlage_titel: string; artikel: number; seiten: number;
  gebaut: string; titelbild: string; formate: Buchformat[]; hinweise: Satzhinweis[];
  veraltet: { neu: number; weg: number; text: string; sekunden: number } | null }
export interface Regal { laufend: Baustand[]; fertig: Eigenbuch[]; ablage: string }

// ----- Beschriftungen (die Werte kommen aus dem Backend, die Wörter dazu hier) --------------------------------------------
export const FUER_WEN: { wert: FuerWen; titel: string }[] = [
  { wert: "erwachsene", titel: "Erwachsene" }, { wert: "jugendliche", titel: "Jugendliche" }, { wert: "kinder", titel: "Kinder ab 10" }];
export const LAENGE: { wert: Laenge; titel: string }[] = [
  { wert: "original", titel: "Wie im Original" }, { wert: "haelfte", titel: "Etwa die Hälfte" }, { wert: "wichtigste", titel: "Nur das Wichtigste" }];
export const TON: { wert: Ton; titel: string }[] = [
  { wert: "sachlich", titel: "Sachlich" }, { wert: "erzaehlend", titel: "Erzählend" }, { wert: "locker", titel: "Locker" }];
export const FARBEN: Farbe[] = ["petrol", "violett", "honig", "koralle", "stahl"];
export const BILDER: { wert: Bildwahl; titel: string }[] = [
  { wert: "im_text", titel: "Im Text" }, { wert: "eins_gross", titel: "Eins groß je Artikel" }, { wert: "ohne", titel: "Ohne" }];
export const SEITEN: { wert: Seitengroesse; titel: string; kurz: string }[] = [
  { wert: "a5", titel: "A5", kurz: "A5" }, { wert: "a4", titel: "A4", kurz: "A4" }, { wert: "a4_zwei", titel: "Zwei Seiten je A4", kurz: "A4, zwei je Blatt" }];
export const HERKUNFT: Record<Herkunft, string> = { thema: "aus dem Thema", selbst: "von selbst", ki: "KI", meins: "aus Meins", buch: "aus den Büchern" };
export const titelVon = <T extends string>(liste: { wert: T; titel: string }[], wert: T) => liste.find((x) => x.wert === wert)?.titel ?? wert;

// ----- Gemeinsamer Stand -------------------------------------------------------------------------------------------------
// `entwuerfe`: die Bestellung je Thema, solange man sie auf der Seite Als Buch einstellt (Probekapitel und Vorlagen nehmen
// sie mit); `proben`: der laufende Auftrag des Probekapitels je Thema
export const buecher = $state<{ vorlagen: Vorlage[]; ordner: string; hinweis: string; katalog: Teilkatalog | null; regal: Regal | null;
  entwuerfe: Record<string, Bestellung>; proben: Record<string, string> }>(
  { vorlagen: [], ordner: "", hinweis: "", katalog: null, regal: null, entwuerfe: {}, proben: {} });

export async function vorlagenLaden(): Promise<void> {
  const [liste, katalog] = await Promise.all([hole<Vorlagenliste>("/buchvorlagen"),
    buecher.katalog ? Promise.resolve(buecher.katalog) : hole<Teilkatalog>("/buchvorlagen/teile")]);
  buecher.vorlagen = liste.vorlagen;
  buecher.ordner = liste.ordner;
  buecher.hinweis = liste.hinweis;
  buecher.katalog = katalog;
}

export async function regalLaden(): Promise<Regal> {
  buecher.regal = await hole<Regal>("/meins/buecher");
  return buecher.regal;
}

const thema = (t: string) => encodeURIComponent(t);
export const buchwahlHolen = (t: string) => hole<Buchwahl>(`/meins/buecher/thema/${thema(t)}`);
export const schaetzen = (b: Bestellung, signal?: AbortSignal) => hole<Schaetzung>("/meins/buecher/schaetzung", { method: "POST", ...json(b), signal });
export const bauen = (b: Bestellung) => hole<{ id: string }>("/meins/buecher", { method: "POST", ...json(b) });
export const probeAnstossen = (bestellung: Bestellung, eintrag = "", neu: number[] = []) =>
  hole<{ id: string }>("/meins/buecher/probe", { method: "POST", ...json({ bestellung, eintrag, neu: neu.map((absatz) => ({ absatz })) }) });
export const probeHolen = (t: string) => hole<Probe | null>(`/meins/buecher/probe/${thema(t)}`);
export const leseansichtHolen = (id: string) => hole<{ titel: string; untertitel: string; html: string }>(`/meins/buecher/${encodeURIComponent(id)}/lesen`);
export const nachbauen = (id: string, wann: Wann) => hole<{ id: string }>(`/meins/buecher/${encodeURIComponent(id)}/nachbauen`, { method: "POST", ...json({ wann }) });
export const buchLoeschen = (id: string) => hole(`/meins/buecher/${encodeURIComponent(id)}`, { method: "DELETE" });
export const buchDatei = (id: string, format: string) => `/api/v1/inhalt/buecher/${encodeURIComponent(id)}/${format}`;
export const vorlageDatei = (kennung: string) => `/api/v1/inhalt/buchvorlagen/${encodeURIComponent(kennung)}`;
export const vorlageSpeichern = (v: Vorlage) => hole<Vorlage>(`/buchvorlagen/${encodeURIComponent(v.kennung)}`, { method: "PUT", ...json(v) });
export const vorlageKopieren = (kennung: string, titel: string) =>
  hole<Vorlage>(`/buchvorlagen/${encodeURIComponent(kennung)}/kopie`, { method: "POST", ...json({ titel }) });
export const vorlageLoeschen = (kennung: string) => hole(`/buchvorlagen/${encodeURIComponent(kennung)}`, { method: "DELETE" });

/** Die Bestellung zu einem Thema: die zuletzt gebaute, sonst aus der ersten Vorlage mit KI (oder der ersten) vorbelegt. */
export function bestellungFuer(w: Buchwahl, vorlagen: Vorlage[]): Bestellung {
  // ohne Leitstelle zuerst eine Vorlage, die ohne KI auskommt
  const v = vorlagen.find((x) => x.kennung === w.letzte?.vorlage)
    ?? (w.leitstelle ? vorlagen.find((x) => x.kennung === "lernheft") : vorlagen.find((x) => !x.ki)) ?? vorlagen[0];
  const grund: Bestellung = {
    thema: w.thema, vorlage: v?.kennung ?? "", kapitel: w.kapitel.map((k) => ({ bereich: k.bereich, an: k.bereich !== "" || w.kapitel.length === 1 })),
    notizen: true, markierungen: true, bilder: true, steckbriefe: false, uebersetzung: true, fuer_wen: v?.anweisung.fuer_wen ?? "erwachsene",
    laenge: v?.anweisung.laenge ?? "haelfte", fragen: v?.anweisung.fragen ?? 5, epub: true, pdf: !w.pdf, seiten: "a5",
    titelbild: w.titelbilder[0] ?? "", wann: "nachts" };
  if (!w.letzte) return grund;
  // Kapitel: die gemerkte Reihenfolge, neue Bereiche hinten an (aus), weggefallene fort
  const da = new Set(w.kapitel.map((k) => k.bereich));
  const kapitel = [...w.letzte.kapitel.filter((k) => da.has(k.bereich)),
    ...w.kapitel.filter((k) => !w.letzte!.kapitel.some((x) => x.bereich === k.bereich)).map((k) => ({ bereich: k.bereich, an: false }))];
  return { ...grund, ...w.letzte, kapitel, pdf: w.letzte.pdf && !w.pdf, epub: w.letzte.epub || !!w.pdf };
}

/** Teile einer Vorlage nach Art (für Fragen wie "hat sie Notizen"). */
export const teileVon = (v: Vorlage | undefined): Set<Teilart> =>
  new Set(v ? [...v.aufbau.vorn, ...v.aufbau.innen, ...v.aufbau.hinten].map((t) => t.art) : []);

// ----- Zahlen und Zeiten in Worten ----------------------------------------------------------------------------------------
const ZAHL = new Intl.NumberFormat("de-DE");
export const zahl = (n: number) => ZAHL.format(Math.round(n));

/** Dauer in Worten: 45 s, 2 min, 1 h 2 min. */
export function dauerText(sekunden: number): string {
  const s = Math.max(0, Math.round(sekunden));
  if (s < 60) return `${s} s`;
  const min = Math.round(s / 60);
  if (min < 60) return `${min} min`;
  return `${Math.floor(min / 60)} h ${min % 60} min`;
}

/** Uhrzeit (Ortszeit) aus ISO, etwa 2:05; morgen und später mit Tag. */
export function uhrzeit(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const zeit = d.toLocaleTimeString("de-DE", { hour: "numeric", minute: "2-digit" });
  const heute = new Date();
  const morgen = new Date(heute.getFullYear(), heute.getMonth(), heute.getDate() + 1);
  if (d.toDateString() === heute.toDateString()) return zeit;
  if (d.toDateString() === morgen.toDateString()) return zeit;           // die Nacht von heute auf morgen
  return `${d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" })} ${zeit}`;
}

export const datum = (iso: string) => (iso ? new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" }) : "");
