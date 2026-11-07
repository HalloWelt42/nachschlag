// Stand des Bücherladers (WIKI-57), geteilt von Navigation (Zahl am Menüpunkt), Startseite (Hinweis auf Neues) und der
// Seite Bibliothek. Neu geholt beim ersten Gebrauch, nach jeder Handlung und sobald ein Auftrag des Bücherladers seinen
// Zustand wechselt (Ereignisstrom der Aufträge, kein Abfragen im Takt).
import { beiAuftrag, seitenFehler } from "appkern-oberflaeche";
import { laderstandHolen } from "./schnittstelle";
import type { Ladefortschritt, Laderstand, Laderzustand } from "./typen";

export const ARTEN = new Set(["buch_laden", "verzeichnis_durchsehen"]);

export const lader = $state<{ stand: Laderstand | null; meldung: string; version: number }>({ stand: null, meldung: "", version: 0 });

/** Was gerade lädt, je Stamm: aus dem Stand übernommen und mit jedem Ereignis des Ladeauftrags nachgeführt. */
export const ladungen = $state<Record<string, Ladefortschritt>>({});

/** Für die Navigation: so viele Bücher laden oder warten aufs Laden; der Anteil des laufenden (null: keins läuft). */
export function ladeZahl(): number {
  return Object.keys(ladungen).length;
}
export function ladeAnteil(): number | null {
  const laufend = Object.values(ladungen).find((l) => l.zustand === "laeuft");
  return laufend ? laufend.fortschritt ?? 0 : null;
}

let laufend: Promise<void> | null = null;

export function laderLaden(neu = false): Promise<void> {
  if (laufend && !neu) return laufend;
  laufend = laderstandHolen()
    .then((s) => {
      lader.stand = s;
      for (const k of Object.keys(ladungen)) delete ladungen[k];
      for (const a of s.abos) if (a.laden) ladungen[a.stamm] = a.laden;
      lader.meldung = "";
      lader.version += 1;          // Seiten, die mehr zeigen (das Verzeichnis), laden mit
    })
    .catch((f) => {
      lader.meldung = seitenFehler(f);
      laufend = null;
    });
  return laufend;
}

let zuletzt = new Map<string, string>();
beiAuftrag((a) => {
  if (!ARTEN.has(a.art)) return;
  const stamm = typeof a.eingabe?.stamm === "string" ? a.eingabe.stamm : "";
  if (a.art === "buch_laden" && stamm) {
    if (a.zustand === "wartet" || a.zustand === "laeuft") {
      ladungen[stamm] = { auftrag: a.id, zustand: a.zustand, fortschritt: a.fortschritt ?? null, schritt: a.schritt,
                          zurueckgestellt: a.zurueckgestellt ?? "" };
    } else if (ladungen[stamm]?.auftrag === a.id) {
      delete ladungen[stamm];
    }
  }
  if (zuletzt.get(a.id) === a.zustand) return;
  if (zuletzt.size > 200) zuletzt = new Map();
  zuletzt.set(a.id, a.zustand);
  void laderLaden(true);
});

export const ZUSTAND: Record<Laderzustand, { text: string; symbol: string; klasse: string }> = {
  nicht_da: { text: "nicht in der Bibliothek", symbol: "fa-circle", klasse: "" },
  aktuell: { text: "aktuell", symbol: "fa-circle-check", klasse: "gut" },
  neuer_da: { text: "neuere Fassung da", symbol: "fa-circle-up", klasse: "neu" },
  laedt: { text: "lädt", symbol: "fa-download", klasse: "laedt" },
  wartet_auf_umschalten: { text: "wartet aufs Umschalten", symbol: "fa-right-left", klasse: "neu" },
};

export const AUSGABE: Record<string, string> = { maxi: "mit Bildern", nopic: "ohne Bilder", mini: "klein", "": "Datei" };

/** Bytes in GB mit deutschem Komma, unter 1 GB in MB. */
export function groesse(bytes: number): string {
  if (bytes < 1024 ** 3) return `${Math.max(1, Math.round(bytes / 1024 ** 2)).toLocaleString("de-DE")} MB`;
  return `${(bytes / 1024 ** 3).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} GB`;
}

/** "2026-10" als "10/2026". */
export function monat(stand: string): string {
  const [j, m] = stand.split("-");
  return m ? `${m}/${j}` : stand;
}
