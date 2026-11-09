// Selbertesten der Übungen (freeCodeCamp, WIKI-66): der Testläufer, den das Buch mitbringt (ein Web Worker der Quelle),
// prüft den eigenen Code gegen jeden Prüfpunkt, so wie in der Original-Anwendung des Buchs:
//   1. einrichten mit dem ganzen Quelltext (Code davor, eigener Code, Code danach) und dem eigenen Code allein
//      (manche Tests lesen ihn als Text),
//   2. je Prüfpunkt seinen Test ausführen; bestanden ist er, wenn die Antwort `pass` trägt,
//   3. ein Test hat höchstens FRIST_MS; hängt er (etwa eine Endlosschleife im eigenen Code), wird der Läufer beendet,
//      neu gestartet und neu eingerichtet, der Prüfpunkt gilt als nicht bestanden.
// Jeder Lauf bekommt einen frischen Läufer, damit nichts aus einem früheren Lauf hängen bleibt.

export const FRIST_MS = 5000;

export interface Testergebnis { bestanden: boolean; meldung: string }
export interface Lauf { punkte: Testergebnis[]; ausgabe: string[]; fehler: string }

interface Antwort { value?: { pass?: boolean; err?: { message?: string }; logs?: { level: string; msg: string }[] } }

/** Eine Nachricht an den Läufer, die Antwort kommt über einen eigenen Kanal (Protokoll der Quelle). Lässt sich der
 * Läufer nicht laden oder bricht er ab, endet das Warten mit einem Fehler statt nie. */
function senden(laeufer: Worker, nachricht: unknown): Promise<Antwort> {
  return new Promise((fertig, scheitern) => {
    const kanal = new MessageChannel();
    const abbruch = () => { kanal.port1.close(); scheitern(new Error("Der Testläufer des Buchs ließ sich nicht starten")); };
    laeufer.addEventListener("error", abbruch, { once: true });
    kanal.port1.onmessage = (e) => {
      laeufer.removeEventListener("error", abbruch);
      kanal.port1.close();
      fertig(e.data as Antwort);
    };
    laeufer.postMessage(nachricht, [kanal.port2]);
  });
}

function quelltext(vorher: string, code: string, nachher: string): string {
  return [vorher, code, nachher].filter((t) => !!t).join("; ");
}

export async function pruefen(adresse: string, vorher: string, code: string, nachher: string, tests: string[]): Promise<Lauf> {
  const einrichtung = { type: "init", value: { source: quelltext(vorher, code, nachher), code: { contents: code } } };
  let laeufer = new Worker(adresse);
  const lauf: Lauf = { punkte: [], ausgabe: [], fehler: "" };
  try {
    await senden(laeufer, einrichtung);
    for (let i = 0; i < tests.length; i++) {
      let uhr: ReturnType<typeof setTimeout> | undefined;
      const zuLange = new Promise<Antwort>((fertig) => {
        uhr = setTimeout(async () => {
          laeufer.terminate();
          laeufer = new Worker(adresse);
          await senden(laeufer, einrichtung);
          fertig({ value: { err: { message: `Der Test brauchte länger als ${FRIST_MS / 1000} Sekunden (Endlosschleife?)` } } });
        }, FRIST_MS);
      });
      const antwort = await Promise.race([senden(laeufer, { type: "test", value: tests[i] }), zuLange]);
      clearTimeout(uhr);
      const v = antwort.value ?? {};
      lauf.punkte.push({ bestanden: !!v && "pass" in v, meldung: v.err?.message ?? "" });
      // die Ausgabe des eigenen Codes (console.log) steht beim ersten Test, wie in der Original-Anwendung
      if (i === 0) lauf.ausgabe = (v.logs ?? []).map((l) => l.msg);
    }
  } catch (f) {
    lauf.fehler = f instanceof Error ? f.message : String(f);
  } finally {
    laeufer.terminate();
  }
  return lauf;
}
