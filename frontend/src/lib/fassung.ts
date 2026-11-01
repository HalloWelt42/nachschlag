// Fassungsfilter einer Dokumentation (Entwurf doku-php.html, Nutzer 01.11.2026: "Versionsfilter spielt hier größere
// Rolle, den man ggf. dauerhafter einstellt"). Die Fassungen stehen in der Seite (Steckbrief: "PHP 4 >= 4.0.6",
// "PHP 8"; Änderungen: "8.0.0"); gewählt wird je Buch und gemerkt unter dem Namen des Buchs ohne Datum, damit die Wahl
// neue Fassungen des Buchs übersteht.

export interface Fassungen {
  produkt: string;            // "PHP" (aus den Angaben der Seite)
  optionen: string[];         // "8.3", "8", "7.4" ... absteigend
}

const SCHLUESSEL = "nachschlag.fassung.";
const BEKANNT = "nachschlag.fassungen.";

/** Absteigend nach Fassung ("8.3" vor "8" vor "7.4"). */
function absteigend(liste: Iterable<string>): string[] {
  return [...new Set(liste)].filter(Boolean).sort((a, b) => (hoechstens(a, b) && a !== b ? 1 : -1));
}

/** Die Fassungen, die das Buch auf allen besuchten Seiten genannt hat, um die der aktuellen Seite ergänzt; so lässt
 *  sich jede schon gesehene Fassung überall wählen. */
export function bekannte(buchname: string, seite: string[]): string[] {
  let alle: string[] = [];
  try {
    alle = JSON.parse(localStorage.getItem(BEKANNT + buchname) ?? "[]");
  } catch {
    alle = [];
  }
  const neu = absteigend([...alle, ...seite]);
  try {
    localStorage.setItem(BEKANNT + buchname, JSON.stringify(neu));
  } catch {
    /* ohne Speicher im Browser nur die der Seite */
  }
  return neu;
}

/** Zahlen einer Fassung zum Vergleichen: "8.3" -> [8, 3], "4.0.6" -> [4, 0, 6]. */
function teile(fassung: string): number[] {
  return fassung.split(".").map((t) => Number.parseInt(t, 10)).filter((n) => !Number.isNaN(n));
}

/** a <= b nach Fassung, nur so genau wie a angegeben ist ("8" <= "8.3"). */
function hoechstens(a: string, b: string): boolean {
  const x = teile(a), y = teile(b);
  for (let i = 0; i < x.length; i++) {
    if ((y[i] ?? 0) !== x[i]) return (y[i] ?? 0) > x[i];
  }
  return true;
}

export function gemerkt(buchname: string): string {
  try {
    return localStorage.getItem(SCHLUESSEL + buchname) ?? "";
  } catch {
    return "";
  }
}

export function merken(buchname: string, fassung: string): void {
  try {
    if (fassung) localStorage.setItem(SCHLUESSEL + buchname, fassung);
    else localStorage.removeItem(SCHLUESSEL + buchname);
  } catch {
    /* ohne Speicher im Browser gilt die Wahl bis zum Neuladen */
  }
}

/** Welche Fassungen die Seite nennt (Steckbrief und Änderungen); ohne Angaben keine. */
export function fassungenAus(wurzel: ParentNode): Fassungen | null {
  const angaben = [...wurzel.querySelectorAll<HTMLElement>(".steckbrief .versionen span")].map((s) => s.dataset.fassung ?? s.textContent ?? "");
  const aenderungen = [...wurzel.querySelectorAll<HTMLElement>(".aenderungen tbody td:first-child")].map((td) => td.textContent?.trim() ?? "");
  if (!angaben.length && !aenderungen.length) return null;
  const produkt = angaben.map((a) => a.match(/^\s*([A-Za-z]+)/)?.[1]).find(Boolean) ?? "";
  const nummern = new Set<string>();
  for (const a of angaben) {
    const m = a.match(/(\d+)(?:\.\d+)*/);
    if (m) nummern.add(m[1]);
  }
  for (const a of aenderungen) {
    const m = a.match(/^(\d+)\.(\d+)/);
    if (m) {
      nummern.add(`${m[1]}.${m[2]}`);
      nummern.add(m[1]);
    }
  }
  return { produkt, optionen: absteigend(nummern) };
}

/** Gibt es die Seite in der Fassung? Steckbrief "PHP 4 >= 4.0.6" heißt: ab 4.0.6 in Hauptfassung 4. */
function gibtEsIn(angabe: string, fassung: string): boolean {
  const haupt = angabe.match(/(\d+)/)?.[1];
  const ab = angabe.match(/>=\s*([\d.]+)/)?.[1];
  if (!haupt || teile(fassung)[0] !== Number(haupt)) return false;
  return !ab || teile(fassung).length < 2 || hoechstens(ab.split(".").slice(0, teile(fassung).length).join("."), fassung);
}

/** Fassung anwenden: eigene hervorheben, andere blass; Änderungen bis zur Fassung gelten, spätere blass. Liefert, ob
 *  es die Seite in der Fassung gibt (ohne Angaben: ja). */
export function anwenden(wurzel: ParentNode, fassung: string, produkt: string): boolean {
  let gibtEs = true;
  const angaben = [...wurzel.querySelectorAll<HTMLElement>(".steckbrief .versionen span")];
  for (const s of angaben) {
    s.dataset.fassung ??= s.textContent ?? "";
    const meine = !!fassung && gibtEsIn(s.dataset.fassung, fassung);
    s.classList.toggle("deine", meine);
    s.classList.toggle("blass", !!fassung && !meine);
    s.textContent = meine ? `${s.dataset.fassung} · deine` : s.dataset.fassung;
  }
  if (fassung && angaben.length) gibtEs = angaben.some((s) => gibtEsIn(s.dataset.fassung ?? "", fassung));
  for (const zeile of wurzel.querySelectorAll<HTMLTableRowElement>(".aenderungen tbody tr")) {
    const zelle = zeile.cells[0];
    if (!zelle) continue;
    zelle.querySelector(".gilt-marke")?.remove();
    const version = zelle.textContent?.trim() ?? "";
    const gilt = !!fassung && hoechstens(version.split(".").slice(0, Math.max(2, teile(fassung).length)).join("."), fassung);
    zeile.classList.toggle("gilt", gilt);
    zeile.classList.toggle("blass", !!fassung && !gilt);
    if (gilt) zelle.insertAdjacentHTML("beforeend", ` <span class="gilt-marke">gilt für ${produkt ? produkt + " " : ""}${fassung}</span>`);
  }
  return gibtEs;
}
