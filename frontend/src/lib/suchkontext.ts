// Der Ort der Suche (WIKI-17, docs/SUCHE.md Punkt 1): in einem Buch (Artikel, Übersicht) stehen seine Treffer zuerst;
// auf Start, Bibliothek und den Seiten von Meins sucht sie in allen Büchern gleich. Der Ort steht im Weg selbst
// (/lesen/<buch>/..., /suche?buch=...), darum braucht er keinen eigenen Zustand.
import { navigation } from "appkern-oberflaeche";

/** Kennung des Buchs, in dem man gerade ist; leer: kein Buch (dann alle gleich). */
export function kontextBuch(): string {
  if (navigation.seite === "lesen") return navigation.teile[0] ?? "";
  if (navigation.seite === "suche") return new URLSearchParams(navigation.suche).get("buch") ?? "";
  return "";
}
