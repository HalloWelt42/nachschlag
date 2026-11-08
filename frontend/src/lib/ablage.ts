// Wo Nachschlag Dateien ablegt (WIKI-11): in der Kellerwolke, wenn eine eingetragen ist, sonst im Ordner ablage des
// Datenordners. Die Wörter dazu stehen hier an einer Stelle; die Art meldet der Server in den App-Angaben.
import { sitzung } from "appkern-oberflaeche";

export const inKellerwolke = (): boolean => sitzung.app?.ablage !== "ordner";

/** "in der Kellerwolke" oder "im Datenordner" */
export const ablageIn = (): string => (inKellerwolke() ? "in der Kellerwolke" : "im Datenordner");

/** "in die Kellerwolke" oder "in den Datenordner" */
export const ablageHinein = (): string => (inKellerwolke() ? "in die Kellerwolke" : "in den Datenordner");

/** Was beim Löschen mit den Dateien geschieht, als Satzteil nach "Die Datei" oder "Die Dateien" */
export const geloeschtWird = (mehrere: boolean): string =>
  inKellerwolke() ? `${mehrere ? "gehen" : "geht"} in den Papierkorb der Kellerwolke` : `${mehrere ? "werden" : "wird"} im Datenordner gelöscht`;
