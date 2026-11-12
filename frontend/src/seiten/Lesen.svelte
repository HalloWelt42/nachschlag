<script lang="ts">
  // Artikel lesen, Variante A (Entwurf mockups/artikel-a.html): ruhige Lesespalte, Inhalt links mitlaufend mit
  // Lesestand, Steckbrief rechts im Text. Weg: /lesen/<buch>/<pfad>?frage=&abschnitt=&anker=&notiz=. Bücher ohne eigenes
  // Lesedesign zeigen ihre Seite unverändert (Originalansicht). Verweise im Text bleiben in der App.
  import Buchmarke from "../teile/Buchmarke.svelte";
  import { gehe, navigation, seitenFehler } from "appkern-oberflaeche";
  import { tick, untrack } from "svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, buch as buchVon, datum, hauptbuch, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, artikelstandHolen, artikelUebersetzen, stellenstandHolen, stelleUebersetzen, zufallHolen,
           rueckverweiseHolen, type Artikelstand, type Rueckverweise } from "../lib/schnittstelle";
  import { deutsch, deutschMerken, uebersetzt } from "../lib/deutsch.svelte";
  import { ANSICHTEN, ansichtMerken, leseansicht } from "../lib/ansicht.svelte";
  import type { Artikel } from "../lib/typen";
  import { lesen, lesenZiel, suchen, verweisZiel } from "../lib/ziele";
  import { Auswahl } from "appkern-oberflaeche";
  import { kopieren } from "appkern-oberflaeche";
  import { RUECKMELDUNG_MS, zitatMitHerkunft } from "../lib/zitat";
  import { istCode } from "../lib/code";
  import { codeEinfaerben, spracheAus } from "../lib/einfaerben";
  import { htmlSprache, spracheInWorten } from "../lib/sprache";
  import { gemerkt, lesestandMelden, meins, meinsLaden, merken, notieren, notizLoeschen, vergessen, verlaufHolen, vorliebeSetzen, wann,
           type Notiz, type NotizNeu } from "../lib/meins.svelte";
  import { markieren, stelleAus, type Stelle } from "../lib/stellen";
  import { geraet } from "appkern-oberflaeche";
  import NotizBlatt from "../teile/NotizBlatt.svelte";
  import ThemaWahl from "../teile/ThemaWahl.svelte";
  import Lesegroesse from "../teile/Lesegroesse.svelte";
  import { groesseFuer } from "../lib/lesegroesse.svelte";
  import { istRahmenmeldung, lesenWeg, OHNE_HERKUNFT, ortNormal, ortVon, rahmenZiel } from "../lib/originalrahmen";
  import Kachel from "../teile/Kachel.svelte";
  import Anleitung from "../teile/Anleitung.svelte";
  import Fragekarte from "../teile/Fragekarte.svelte";
  import Anleitungssuche from "../teile/Anleitungssuche.svelte";
  import Geraeteseite from "../teile/Geraeteseite.svelte";
  import Uebung from "../teile/Uebung.svelte";
  import Uebungen from "../teile/Uebungen.svelte";
  import Kategorieseite from "../teile/Kategorieseite.svelte";
  import Codeansicht from "../teile/Codeansicht.svelte";
  import { ausprobierstand, beispieleHolen, beispielLoeschen, codeSprache, type Beispiel, type Codesprache,
           type Probe } from "../lib/ausprobieren";
  import { belegeDerAuswahl, recherche, rechercheUmschalten } from "../lib/recherche.svelte";
  import { VorleseKnopf, vorleser } from "appkern-oberflaeche";
  import { hervorhebungWeg, satzHervorheben, vorlesetext } from "../lib/mitlesen";
  import { kommentareSetzen } from "../lib/kommentare";
  import Leuchtkasten from "../teile/Leuchtkasten.svelte";
  import { medienImArtikel, type Medium } from "../lib/medien";
  import { themenLaden } from "../lib/themen.svelte";
  import { anwenden as fassungAnwenden, bekannte as bekannteFassungen, fassungenAus, gemerkt as fassungGemerkt, merken as fassungMerken,
           type Fassungen } from "../lib/fassung";

  const WOERTER_JE_MINUTE = 200;
  const NACHFRAGE_MS = 4000;              // so lange fragt ein Löschknopf nach, bevor er wieder harmlos ist
  const MITLAUF_ABSTAND_PX = 90;          // eine Überschrift gilt als erreicht, sobald sie so nah am oberen Rand steht

  let artikel = $state.raw<Artikel | null>(null);   // was gezeigt wird (Original oder Übersetzung); nur lesen, ohne Proxy
  let quelle = $state.raw<Artikel | null>(null);    // der Artikel, wie ihn die Quelle liefert
  let ue = $state.raw<Artikelstand | null>(null);   // Stand der Übersetzung (WIKI-8)
  let fehler = $state("");
  let laedt = $state(false);
  let original = $state(false);
  let rollfeld = $state<HTMLElement>();
  let text = $state<HTMLElement>();
  let aktiv = $state("");
  let anteil = $state(0);
  let woerter = $state(0);
  let artikelEl = $state<HTMLElement>();
  let fassungen = $state.raw<Fassungen | null>(null);   // Fassungen, die die Seite nennt (Dokumentation)
  let meineFassung = $state("");
  let gibtEsInFassung = $state(true);

  const buchKennung = $derived(navigation.teile[0] ?? "");
  const pfad = $derived(navigation.teile.slice(1).join("/"));
  const zusatz = $derived(new URLSearchParams(navigation.suche));
  const frage = $derived(zusatz.get("frage") ?? "");
  const abschnitt = $derived(zusatz.get("abschnitt") ?? "");
  const weg = $derived(zusatz.get("weg") ?? "");
  const anker = $derived(zusatz.get("anker") ?? "");
  const notizZiel = $derived(zusatz.get("notiz") ?? "");
  const buch = $derived(buchVon(buchKennung));
  const zeigeOriginal = $derived(!!artikel && (artikel.darstellung === "original" || original));
  const aufDeutsch = $derived(!!artikel && !!quelle && artikel !== quelle);
  // Sprache des gezeigten Texts (lang): Silbentrennung, Rechtschreibung und die Stimme beim Vorlesen
  const textSprache = $derived(aufDeutsch ? "de" : buch ? htmlSprache(buch.sprache) : "");
  // Ziel der Rubrik im Pfad: ihre eigene Seite, sonst die Startseite des Buchs, gefiltert auf die Rubrik
  const rubrikZiel = $derived(!artikel?.rubrik || !buch ? ""
    : artikel.rubrik_pfad ? lesenZiel(artikel.buch, artikel.rubrik_pfad)
    : `${lesenZiel(artikel.buch, buch.startseite)}?filter=${encodeURIComponent(artikel.rubrik)}`);
  const uebersetzbar = $derived(!!ue && ue.zustand !== "nicht_noetig" && ue.zustand !== "nicht_moeglich");
  // Ansicht C (WIKI-7): nur das Blatt, über der Schale; Werkzeuge schwebend, Inhalt als Tafel auf Abruf
  const nurBlatt = $derived(leseansicht.wert === "c" && artikel?.darstellung === "lesedesign" && !zeigeOriginal);
  let inhaltTafel = $state(false);
  // Ansicht B (WIKI-7): rechts die Wissensleiste mit Reitern; Medien erst, wenn ihr Reiter offen ist
  const mitWissen = $derived(leseansicht.wert === "b" && artikel?.darstellung === "lesedesign" && !zeigeOriginal);
  let reiter = $state<"steckbrief" | "notizen" | "medien">("steckbrief");
  const reiterJetzt = $derived(reiter === "steckbrief" && !artikel?.steckbrief ? "notizen" : reiter);
  let wissenMedien = $state.raw<Medium[] | null>(null);
  $effect(() => {
    const a = artikel;
    if (!mitWissen || reiterJetzt !== "medien" || !a) return;
    let aktuell = true;
    wissenMedien = null;
    medienImArtikel(a.buch, a.pfad).then((m) => aktuell && (wissenMedien = m)).catch(() => aktuell && (wissenMedien = []));
    return () => { aktuell = false; };
  });
  const restMinuten = $derived(Math.max(1, Math.round((woerter * (1 - anteil)) / WOERTER_JE_MINUTE)));

  // Lesegröße dieses Buchs auf diesem Gerät (WIKI-29) als Zoom des Lesebereichs, auch in der Originalseite
  const zoom = $derived(buch ? groesseFuer(buch.name) / 100 : 1);

  // Ohne Buch im Weg (Eintrag "Artikel" der Seitenleiste): der zuletzt gelesene Artikel aus dem Verlauf, auf allen
  // Geräten derselbe (WIKI-94); ohne Verlauf die Startseite des Hauptbuchs. Mit Buch, aber ohne Seite (lesen/<buch>,
  // etwa der Verweis eines Auftrags, WIKI-50): die Startseite dieses Buchs
  $effect(() => {
    if (buchKennung && pfad) return;
    const kennung = buchKennung;
    untrack(async () => {
      await bibliothekLaden();
      if (!kennung) {
        const [letzter] = await verlaufHolen(1, 0, "artikel").catch(() => []);
        // das Buch des Eintrags, nach dem Umschalten auf eine neue Fassung dasselbe Buch unter neuer Kennung
        const b = letzter && (buchVon(letzter.buch) ?? bibliothek.buecher.find((x) => x.name === letzter.buch_name));
        if (letzter && b) return gehe(lesenZiel(b.kennung, letzter.pfad), true);
      }
      const ziel = kennung ? buchVon(kennung) : hauptbuch();
      if (ziel) gehe(lesenZiel(ziel.kennung, ziel.startseite), true);
    });
  });

  // Der Artikel zu Buch und Pfad (Frage und Anker laden nicht neu)
  $effect(() => {
    const b = buchKennung, p = pfad;
    if (!b || !p) return;
    const abruf = new AbortController();
    untrack(() => laden(b, p, abruf.signal));
    return () => abruf.abort();
  });

  async function laden(b: string, p: string, signal: AbortSignal) {
    laedt = true;
    probe = null;
    fehler = "";
    original = false;
    blatt = null;
    textwahl = null;
    bilder = null;
    filterText = zusatz.get("filter") ?? "";      // aus dem Pfad: die Startseite gefiltert auf eine Rubrik
    void bibliothekLaden();
    ue = null;
    try {
      // Artikel und Stand der Übersetzung zugleich: will dieses Gerät Deutsch und liegt sie ab, steht sie gleich da
      const [neu, stand] = await Promise.all([artikelHolen(b, p, signal), artikelstandHolen(b, p, signal).catch(() => null)]);
      quelle = neu;
      ue = neu.darstellung !== "lesedesign" ? null
        : neu.pfad === p ? stand : await artikelstandHolen(b, neu.pfad, signal).catch(() => null);   // Weiterleitung
      await zeigen(ue?.zustand === "fertig" && ue.uebersetzung && deutsch.an ? uebersetzt(neu, ue.uebersetzung) : neu);
      zurStelle();
    } catch (f) {
      if (!signal.aborted) fehler = seitenFehler(f);
    } finally {
      if (!signal.aborted) laedt = false;
    }
  }

  /** Einen Artikel zeigen (Original oder Übersetzung) und seinen Text aufbereiten: Code färben, Knöpfe, Symbole,
   *  Fassungen; danach stehen auch die Markierungen der Notizen. */
  async function zeigen(a: Artikel) {
    text?.querySelectorAll(".beispiel.eigen").forEach((e) => e.remove());   // gehören nicht zum Text des Artikels
    artikel = a;
    navigation.titel = a.titel;
    await tick();
    woerter = text?.innerText.split(/\s+/).length ?? 0;
    if (text) {
      // Sprache des Codes aus den Schlagwörtern (Frage und Antwort); sonst erkennt sie sich am Inhalt
      codeEinfaerben(text, spracheAus([...text.querySelectorAll(".schlagwoerter :is(span, a)")].map((e) => e.textContent ?? "")));
      kopierknoepfe(text);
      kommentarSchalter(text);
      void ausprobierenAnbringen(text, a);
      if (geraet.mobil) codeGrossKnoepfe(text);
      symboleAnbringen(text);
    }
    await Promise.all([bibliothekLaden(), meinsLaden(), themenLaden()]);   // Buch (sein Name), Meins und Themen des Kontos
    const aufDerSeite = artikelEl ? fassungenAus(artikelEl) : null;
    meineFassung = aufDerSeite && buch ? (meins.vorlieben[`fassung:${buch.name}`] ?? fassungGemerkt(buch.name)) : "";
    fassungen = aufDerSeite && buch
      ? { ...aufDerSeite, optionen: bekannteFassungen(buch.name, [...aufDerSeite.optionen, meineFassung]) }
      : aufDerSeite;
    if (artikelEl && fassungen) {
      gibtEsInFassung = fassungAnwenden(artikelEl, meineFassung, fassungen.produkt);
    }
    await tick();                                              // Markierungen der Notizen stehen
  }

  // --- Übersetzen (WIKI-8): Artikel aus Quellen in anderer Sprache auf Deutsch, immer als Übersetzung gekennzeichnet ---
  const NACHSEHEN_MS = 2000;

  /** Zwischen Original und Übersetzung wechseln; die Stelle, an der man liest, bleibt (Anker sind dieselben). */
  async function sprachwechsel(nachDeutsch: boolean) {
    const a = quelle, u = ue?.uebersetzung;
    if (!a || (nachDeutsch && !u)) return;
    const stelle = aktiv;
    await zeigen(nachDeutsch ? uebersetzt(a, u!) : a);
    if (stelle) text?.querySelector<HTMLElement>(`#${CSS.escape(stelle)}`)?.scrollIntoView({ block: "start" });
  }

  async function deutschUmschalten() {
    if (!quelle || !ue) return;
    if (aufDeutsch) {
      deutschMerken(false);
      await sprachwechsel(false);
      return;
    }
    deutschMerken(true);
    if (ue.zustand === "fertig") await sprachwechsel(true);
    else await anstossen();
  }

  async function anstossen() {
    const a = quelle;
    if (!a) return;
    try {
      const stand = await artikelUebersetzen(a.buch, a.pfad);
      if (quelle === a) ue = stand;
    } catch (f) {
      if (quelle === a) ue = { zustand: "fehler", auftrag: "", anteil: null, schritt: "", grund: seitenFehler(f), uebersetzung: null };
    }
  }

  // Solange übersetzt wird, nachsehen; fertig wechselt die Seite von selbst (nur wenn dieses Gerät Deutsch will)
  $effect(() => {
    if (ue?.zustand !== "laeuft") return;
    const a = untrack(() => quelle);
    if (!a) return;
    const takt = setInterval(async () => {
      try {
        const stand = await artikelstandHolen(a.buch, a.pfad);
        if (quelle !== a) return;
        ue = stand;
        if (stand.zustand === "fertig" && deutsch.an) await sprachwechsel(true);
      } catch {
        // beim nächsten Takt wieder
      }
    }, NACHSEHEN_MS);
    return () => clearInterval(takt);
  });

  // Ein anderer Anker im selben Artikel (Verweis auf einen Abschnitt, Inhaltsverzeichnis)
  $effect(() => {
    void anker;
    void notizZiel;
    if (untrack(() => artikel && !laedt)) untrack(zurStelle);
  });

  function ueberschrift(titel: string): HTMLElement | null {
    const gesucht = titel.trim().toLowerCase();
    return [...(text?.querySelectorAll<HTMLElement>("h2, h3, h4") ?? [])].find((h) => h.innerText.trim().toLowerCase() === gesucht) ?? null;
  }

  /** Springt zu einer Notiz (aus der Seite Notizen), zum Anker (aus dem Weg oder der Weiterleitung) oder zur
   *  Fundstelle aus der Suche; sonst nach oben. */
  function zurStelle() {
    if (!rollfeld || !text) return;
    text.querySelectorAll(".fundstelle").forEach((e) => e.classList.remove("fundstelle"));
    if (notizZiel) {
      const n = meins.notizen.find((x) => x.id === notizZiel);
      if (n) blatt = { notiz: n, entwurf: null };
      const mark = text.querySelector<HTMLElement>(`mark[data-notiz="${CSS.escape(notizZiel)}"]`);
      if (mark) {
        stelleZeigen(mark, "instant");
        mitlaufen();
        return;
      }
    }
    const ziel = anker || artikel?.anker || "";
    let el: HTMLElement | null = ziel ? text.querySelector<HTMLElement>(`#${CSS.escape(ziel)}`) : null;
    if (!el && abschnitt) {
      const h = ueberschrift(abschnitt);
      const absatz = h?.nextElementSibling;
      if (absatz instanceof HTMLElement && absatz.tagName === "P") absatz.classList.add("fundstelle");
      el = h;
    }
    if (el) el.scrollIntoView({ block: "start" });
    else roller().scrollTop = 0;
    mitlaufen();
  }

  /** Was beim Lesen tatsächlich rollt: am Rechner das Rollfeld des Artikels, am Telefon der Inhalt der Schale (dort
   *  wächst das Rollfeld mit). Eine Stelle für Lesestand, Mitlauf und Sprünge. */
  function roller(): HTMLElement {
    let el: HTMLElement | null = rollfeld ?? null;
    while (el && !(/(auto|scroll)/.test(getComputedStyle(el).overflowY) && el.scrollHeight > el.clientHeight)) el = el.parentElement;
    return el ?? (document.scrollingElement as HTMLElement);
  }

  // Rollen hören, wo immer es geschieht (Scroll-Ereignisse steigen nicht auf; im Einfangen kommen sie an)
  $effect(() => {
    const hoeren = () => mitlaufen();
    document.addEventListener("scroll", hoeren, { capture: true, passive: true });
    return () => document.removeEventListener("scroll", hoeren, { capture: true });
  });

  function mitlaufen() {
    if (!rollfeld || !text || !artikel) return;
    const r = roller();
    const sichtbar = r === document.scrollingElement ? 0 : r.getBoundingClientRect().top;
    // Lage der Überschriften im sichtbaren Bereich (offsetTop bezöge sich auf das nächste positionierte Element)
    const oben = sichtbar + MITLAUF_ABSTAND_PX;
    let jetzt = "";
    for (const a of artikel.abschnitte) {
      const h = text.querySelector<HTMLElement>(`#${CSS.escape(a.anker)}`);
      if (h && h.getBoundingClientRect().top <= oben) jetzt = a.anker;
    }
    aktiv = jetzt;
    const weit = r.scrollHeight - r.clientHeight;
    anteil = weit > 0 ? Math.min(1, r.scrollTop / weit) : 1;
  }

  function springen(ziel: string) {
    gehe(lesenZiel(buchKennung, pfad, { frage, abschnitt, weg }, ziel), true);
  }

  /** Verweise im Text bleiben in der App; Orte und Online-Verweise gibt es im Text nicht (stehen in "Über"). Eine
   *  markierte Stelle öffnet ihre Notiz (in einem Verweis nur über ihr Zeichen). */
  function klick(e: MouseEvent) {
    const img = (e.target as HTMLElement).closest("img");
    if (img && !img.closest("a") && !e.ctrlKey && !e.metaKey) {
      e.preventDefault();
      void bildZeigen(img.getAttribute("src") ?? "");
      return;
    }
    const stelle = (e.target as HTMLElement).closest<HTMLElement>(".notiz-marke, mark.notiz");
    if (stelle && (stelle.classList.contains("notiz-marke") || !stelle.closest("a")) && !window.getSelection()?.toString()) {
      const n = meins.notizen.find((x) => x.id === stelle.dataset.notiz);
      if (n) {
        e.preventDefault();
        notizZeigen(n);
        return;
      }
    }
    const a = (e.target as HTMLElement).closest("a");
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
    const ziel = verweisZiel(a.getAttribute("href") ?? "");
    if (!ziel) return;
    e.preventDefault();
    gehe(ziel.ziel);
  }

  /** Kopieren an Code und Signaturen (Entwurf: Knopf im Kopf des Beispiels, oben rechts an der Signatur). Der Text
   *  des Artikels kommt fertig vom Baustein; die Knöpfe sind Bedienung und gehören darum hierher. */
  function kopierknoepfe(wurzel: HTMLElement) {
    for (const kasten of wurzel.querySelectorAll<HTMLElement>(".beispiel, .signatur")) {
      const code = kasten.classList.contains("signatur") ? kasten : kasten.querySelector<HTMLElement>("pre:not(.ausgabe)");
      if (!code || kasten.querySelector(".kopieren")) continue;
      const inhalt = code.innerText;          // vor dem Knopf festhalten, sonst käme seine Beschriftung mit
      const knopf = document.createElement("button");
      knopf.className = "knopf still kopieren";
      knopf.title = "Kopieren";
      knopf.innerHTML = '<i class="fa-regular fa-copy"></i><span class="wort">Kopieren</span>';
      knopf.addEventListener("click", async () => {
        await kopieren(inhalt);
        knopf.querySelector("i")!.className = "fa-solid fa-check";
        setTimeout(() => (knopf.querySelector("i")!.className = "fa-regular fa-copy"), 1500);
      });
      if (kasten.classList.contains("signatur")) kasten.prepend(knopf);
      else werkzeugleiste(code).append(knopf);
    }
  }

  /** Der Ort für Knöpfe an einem Codeblock: der Kopf seines Beispiels, sonst eine Leiste oben rechts im Kasten (Beispiel
   *  ohne Kopf) oder in einem Rahmen um den Block (Code im Text, etwa in Antworten). */
  function werkzeugleiste(pre: HTMLElement): HTMLElement {
    const kasten = pre.closest<HTMLElement>(".beispiel");
    const kopf = kasten?.querySelector<HTMLElement>(".bkopf");
    if (kopf) return kopf;
    let halter = kasten ?? (pre.parentElement?.classList.contains("code-rahmen") ? pre.parentElement : null);
    if (!halter) {
      halter = document.createElement("div");
      halter.className = "code-rahmen";
      pre.replaceWith(halter);
      halter.append(pre);
    }
    let leiste = halter.querySelector<HTMLElement>(":scope > .bwerkzeuge");
    if (!leiste) {
      leiste = document.createElement("div");
      leiste.className = "bwerkzeuge";
      halter.append(leiste);
    }
    return leiste;
  }

  /** Ein Knopf an Code (Symbol, Wort, Erklärung); Beschriftung nur aus festen Texten. */
  function codeKnopf(symbol: string, wort: string, titel: string, klasse = ""): HTMLButtonElement {
    const knopf = document.createElement("button");
    knopf.className = `knopf still ${klasse}`.trim();
    knopf.title = titel;
    knopf.innerHTML = `<i class="${symbol}"></i><span class="wort">${wort}</span>`;
    return knopf;
  }

  /** Kommentare im Code (WIKI-8): Gibt es übersetzte Kommentare, bekommt jeder Codeabschnitt mit welchen einen Schalter
   *  "Kommentare"; er tauscht nur diesen Abschnitt. Auf Deutsch gezeigt beginnen sie deutsch, sonst im Original. */
  function kommentarSchalter(wurzel: HTMLElement) {
    const paare = ue?.uebersetzung?.kommentare ?? [];
    if (!paare.length) return;
    const pres = [...wurzel.querySelectorAll<HTMLElement>("pre")];
    for (const [nr, pre] of pres.entries()) {
      const eigene = paare.filter((p) => p.block === nr);
      if (!eigene.length || pre.dataset.kommentare) continue;
      pre.dataset.kommentare = "ja";                 // jeder Abschnitt bekommt seinen Schalter genau einmal
      let deutsch = aufDeutsch;
      if (deutsch) kommentareSetzen(pre, eigene, true);
      const knopf = document.createElement("button");
      knopf.className = "knopf still kommentar-schalter";
      const beschriften = () => {
        knopf.title = deutsch ? "Kommentare im Original zeigen" : "Kommentare auf Deutsch zeigen";
        knopf.innerHTML = `<i class="fa-solid fa-language"></i><span class="wort">Kommentare ${deutsch ? "Deutsch" : "Original"}</span>`;
        knopf.classList.toggle("an", deutsch);
      };
      beschriften();
      knopf.addEventListener("click", () => {
        deutsch = !deutsch;
        kommentareSetzen(pre, eigene, deutsch);
        beschriften();
      });
      const kopf = pre.closest(".beispiel")?.querySelector<HTMLElement>(".bkopf");
      if (kopf) kopf.append(knopf);
      else pre.before(knopf);
    }
  }

  /** Am Telefon bekommt jeder Codeblock "Code groß" (WIKI-30): die Codeansicht über den ganzen Schirm, ohne Umbruch. Der
   *  Knopf steht in einem Rahmen um den Block, damit Text und Stellen des Codes unberührt bleiben. */
  let codeGross = $state.raw<{ html: string; text: string; sprache: string } | null>(null);
  function codeGrossKnoepfe(wurzel: HTMLElement) {
    for (const pre of wurzel.querySelectorAll<HTMLElement>("pre:not(.ausgabe)")) {
      if (pre.parentElement?.classList.contains("code-rahmen") || !pre.textContent?.trim()) continue;
      const rahmen = document.createElement("div");
      rahmen.className = "code-rahmen";
      pre.replaceWith(rahmen);
      rahmen.append(pre);
      const knopf = document.createElement("button");
      knopf.className = "knopf still code-gross";
      knopf.title = "Code groß, ohne Umbruch";
      knopf.innerHTML = '<i class="fa-solid fa-up-right-and-down-left-from-center"></i><span class="wort">Groß</span>';
      knopf.addEventListener("click", () => {
        const code = pre.querySelector("code") ?? pre;
        const sprache = pre.dataset.gefaerbt && pre.dataset.gefaerbt !== "schlicht" ? pre.dataset.gefaerbt : "";
        codeGross = { html: code.innerHTML, text: code.textContent ?? "", sprache };
      });
      rahmen.append(knopf);
    }
  }

  // --- Ausprobieren (WIKI-48, Bauplan docs/AUSPROBIEREN.md): Code in der Sandbox der Codeschmiede ausführen und
  // debuggen, an einer Kopie; behaltene Kopien stehen als eigene Beispiele unter dem Code, aus dem sie stammen ---
  let probe = $state.raw<Probe | null>(null);
  let eigene = $state.raw<Beispiel[]>([]);
  let laufbar = $state.raw<Codesprache[]>([]);      // was die Sandbox gerade kann; am Telefon nichts (nur am Rechner)

  /** Codeblöcke des Artikels in ihrer Reihenfolge (wie die Kommentare sie zählen); eigene Beispiele zählen nicht mit. */
  function codebloecke(wurzel: HTMLElement): HTMLElement[] {
    return [...wurzel.querySelectorAll<HTMLElement>("pre")].filter((pre) => !pre.closest(".beispiel.eigen"));
  }

  async function ausprobierenAnbringen(wurzel: HTMLElement, a: Artikel) {
    const [stand, liste] = await Promise.all([geraet.mobil ? null : ausprobierstand(),
                                              beispieleHolen(a.buch, a.pfad).catch(() => [] as Beispiel[])]);
    if (artikel !== a) return;                        // inzwischen ein anderer Text
    laufbar = stand?.bereit ? stand.sprachen.map((s) => s.sprache) : [];
    probierknoepfe(wurzel);
    eigene = liste;
    eigeneZeigen();
  }

  /** Codeblöcke in Sprachen, die die Sandbox kann, bekommen "Ausprobieren" vor den anderen Knöpfen. */
  function probierknoepfe(wurzel: HTMLElement) {
    for (const [block, pre] of codebloecke(wurzel).entries()) {
      const sprache = codeSprache(pre);
      if (!sprache || !laufbar.includes(sprache) || pre.dataset.probe) continue;
      pre.dataset.probe = "ja";
      const titel = vorlageTitel(wurzel, pre, block);
      const knopf = probierKnopf(() => ({ titel, sprache, code: codeText(pre), block, eigen: null }));
      const leiste = werkzeugleiste(pre);
      const erster = leiste.querySelector(":scope > button");
      if (erster) erster.before(knopf);
      else leiste.append(knopf);
    }
  }

  /** `fassung` (PHP): die eines eigenen Beispiels, sonst gilt Meine Fassung des Buchs */
  function probierKnopf(was: () => Pick<Probe, "titel" | "sprache" | "code" | "block" | "eigen"> & Partial<Pick<Probe, "fassung">>): HTMLButtonElement {
    const knopf = codeKnopf("fa-solid fa-play", "Ausprobieren", "Ausprobieren: eine Kopie ausführen und debuggen", "ausprobieren");
    knopf.addEventListener("click", () => {
      if (artikel) probe = { fassung: meineFassung, ...was(), buch: artikel.buch, pfad: artikel.pfad, quelle: buch ? bezeichnung(buch) : artikel.buch };
    });
    return knopf;
  }

  function codeText(pre: HTMLElement): string {
    return ((pre.querySelector("code") ?? pre).textContent ?? "").replace(/\n+$/, "");
  }

  /** Wie ein Codeblock heißt: der Kopf seines Beispiels, sonst die Überschrift davor, sonst seine Nummer. */
  function vorlageTitel(wurzel: HTMLElement, pre: HTMLElement, block: number): string {
    const kopf = pre.closest(".beispiel")?.querySelector(".bkopf");
    if (kopf) {
      const kopie = kopf.cloneNode(true) as HTMLElement;
      kopie.querySelectorAll("button").forEach((b) => b.remove());
      if (kopie.textContent?.trim()) return kopie.textContent.trim();
    }
    for (let el: Element | null = pre; el && el !== wurzel; el = el.parentElement) {
      for (let davor = el.previousElementSibling; davor; davor = davor.previousElementSibling) {
        if (/^H[2-4]$/.test(davor.tagName) && davor.textContent?.trim()) return `Code unter ${davor.textContent.trim()}`;
      }
    }
    return `Codeblock ${block + 1}`;
  }

  /** Eigene Beispiele unter dem Codeblock, aus dem sie stammen, in der Reihenfolge des Anlegens; gibt es den Block
   *  nicht mehr (neue Fassung des Buchs), stehen sie am Ende des Texts. */
  function eigeneZeigen() {
    if (!text) return;
    text.querySelectorAll(".beispiel.eigen").forEach((e) => e.remove());
    const bloecke = codebloecke(text);
    const zuletzt = new Map<number, Element>();
    for (const b of eigene) {
      const el = eigenesBeispiel(b);
      const pre = b.block >= 0 ? bloecke[b.block] : undefined;
      const nach = pre ? zuletzt.get(b.block) ?? pre.closest(".beispiel, .code-rahmen") ?? pre : null;
      if (nach) {
        nach.after(el);
        zuletzt.set(b.block, el);
      } else {
        text.append(el);
      }
    }
  }

  function eigenesBeispiel(b: Beispiel): HTMLElement {
    const kasten = document.createElement("div");
    kasten.className = "beispiel eigen";
    const kopf = document.createElement("div");
    kopf.className = "bkopf";
    const symbol = document.createElement("i");
    symbol.className = "fa-solid fa-user-pen";
    const titel = document.createElement("span");
    titel.className = "eigen-titel";
    titel.textContent = `Dein Beispiel: ${b.titel}`;
    const marke = document.createElement("span");
    marke.className = "eigen-marke";
    marke.textContent = `von dir · ${wann(b.geaendert)}`;
    if (b.vorlage) marke.title = `abgewandelt aus ${b.vorlage}`;
    kopf.append(symbol, titel, marke);
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.textContent = b.code;
    pre.append(code);
    kasten.append(kopf, pre);
    codeEinfaerben(kasten, b.sprache);
    // die Knöpfe als Gruppe: in schmalen Spalten rücken sie zusammen unter den Titel
    const knoepfe = document.createElement("span");
    knoepfe.className = "eigen-knoepfe";
    if (laufbar.includes(b.sprache)) {
      knoepfe.append(probierKnopf(() => ({ titel: b.vorlage || b.titel, sprache: b.sprache, code: b.code, block: b.block, eigen: b,
                                           ...(b.fassung ? { fassung: b.fassung } : {}) })));
    }
    const kopierer = codeKnopf("fa-regular fa-copy", "Kopieren", "Kopieren", "kopieren");
    kopierer.addEventListener("click", async () => {
      await kopieren(b.code);
      kopierer.querySelector("i")!.className = "fa-solid fa-check";
      setTimeout(() => (kopierer.querySelector("i")!.className = "fa-regular fa-copy"), RUECKMELDUNG_MS);
    });
    knoepfe.append(kopierer, loeschKnopf(b));
    kopf.append(knoepfe);
    return kasten;
  }

  /** Löschen in zwei Klicks: der erste fragt im Knopf nach, der zweite löscht (ohne Dialog des Browsers). Beide
   *  Beschriftungen liegen übereinander, so bleibt der Knopf gleich breit und der zweite Klick trifft. */
  function loeschKnopf(b: Beispiel): HTMLButtonElement {
    const knopf = codeKnopf("fa-solid fa-trash", "", "Dein Beispiel löschen");
    const wort = knopf.querySelector(".wort")!;
    wort.classList.add("wort-paar");
    wort.innerHTML = "<span>Löschen</span><span>Wirklich?</span>";
    let scharf = 0;
    knopf.addEventListener("click", async () => {
      if (!scharf) {
        knopf.classList.add("scharf");
        scharf = window.setTimeout(() => {
          scharf = 0;
          knopf.classList.remove("scharf");
        }, NACHFRAGE_MS);
        return;
      }
      clearTimeout(scharf);
      knopf.disabled = true;
      try {
        await beispielLoeschen(b.id);
        eigene = eigene.filter((x) => x.id !== b.id);
        eigeneZeigen();
      } catch (f) {
        knopf.disabled = false;
        scharf = 0;
        knopf.classList.remove("scharf");
        wort.textContent = "Löschen ging nicht";
        knopf.title = f instanceof Error ? f.message : String(f);
      }
    });
    return knopf;
  }

  /** Aus der Ebene behalten: neu am Ende seines Blocks, geändert an seiner Stelle. */
  function beispielBehalten(b: Beispiel) {
    eigene = eigene.some((x) => x.id === b.id) ? eigene.map((x) => (x.id === b.id ? b : x)) : [...eigene, b];
    eigeneZeigen();
  }

  // Vorlesen mit Mitlesen (WIKI-8): ab dem Abschnitt, in dem man liest; der gesprochene Satz ist hervorgehoben und rollt
  // in Sicht, solange der Vorleser diesen Artikel liest
  const vorleseKennung = $derived(artikel ? `artikel:${artikel.buch}/${artikel.pfad}` : "");
  $effect(() => {
    const satz = vorleser.kennung === vorleseKennung ? vorleser.satz : null;
    untrack(() => {
      if (!satz || !text) return hervorhebungWeg();
      const el = satzHervorheben(text, satz.text);
      if (el) stelleZeigen(el, "smooth");
    });
  });

  /** Symbole aus dem Entwurf an Teilen, die der Baustein liefert (Haken an der akzeptierten Antwort). Die Bausteine
   *  liefern nur Inhalt und Klassen; Symbole gehören zur Oberfläche. */
  function symboleAnbringen(wurzel: HTMLElement) {
    for (const marke of wurzel.querySelectorAll<HTMLElement>(".akz-marke")) {
      if (!marke.querySelector("i")) marke.insertAdjacentHTML("afterbegin", '<i class="fa-solid fa-circle-check"></i>');
    }
    for (const stimmen of wurzel.querySelectorAll<HTMLElement>(".antwort.akzeptiert .qa-stimmen")) {
      if (!stimmen.querySelector(".haken")) stimmen.insertAdjacentHTML("beforeend", '<span class="haken" title="akzeptierte Antwort"><i class="fa-solid fa-check"></i></span>');
    }
  }

  function fassungWaehlen(f: string) {
    meineFassung = f;
    if (buch) {
      fassungMerken(buch.name, f);                       // sofort auf diesem Gerät
      void vorliebeSetzen(`fassung:${buch.name}`, f);    // und für alle Geräte des Kontos
    }
    if (artikelEl && fassungen) gibtEsInFassung = fassungAnwenden(artikelEl, f, fassungen.produkt);
  }

  // --- Merken und Lesestand (Meins) ---
  const LESESTAND_TAKT_MS = 20_000;
  const eintrag = $derived(buch && artikel ? gemerkt(buch.name, artikel.pfad) : undefined);

  async function merkenUmschalten() {
    if (!artikel) return;
    try {
      if (eintrag) await vergessen(eintrag.id);
      else await merken(artikel.buch, artikel.pfad, artikel.titel, artikel.bild);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // Lesestand: gedrosselt beim Lesen, dazu beim Verlassen der Seite (nur Seiten im Lesedesign)
  $effect(() => {
    const a = artikel;
    if (!a || a.darstellung !== "lesedesign") return;
    let seit = Date.now();
    const melden = () => {
      const jetzt = Date.now();
      const sekunden = Math.round((jetzt - seit) / 1000);
      seit = jetzt;
      const stelle = untrack(() => a.abschnitte.find((x) => x.anker === aktiv)?.titel ?? "");
      void lesestandMelden({ buch: a.buch, pfad: a.pfad, titel: a.titel, bild: a.bild, abschnitt: stelle,
                             anteil: Math.round(untrack(() => anteil) * 100) / 100, sekunden });
    };
    const takt = setInterval(melden, LESESTAND_TAKT_MS);
    addEventListener("pagehide", melden);
    return () => {
      clearInterval(takt);
      removeEventListener("pagehide", melden);
      melden();
    };
  });

  // --- Filter der Übersicht: Rubriken, Fragen und Kacheln nach ihrem Titel, sofort beim Tippen ---
  let filterText = $state("");
  const gefiltert = $derived.by(() => {
    const a = artikel, wort = filterText.trim().toLowerCase();
    const passt = (titel: string) => !wort || titel.toLowerCase().includes(wort);
    const gruppen = (a?.gruppen ?? []).map((g) => ({ ...g, eintraege: passt(g.titel) ? g.eintraege : g.eintraege.filter((e) => passt(e.titel)) }))
      .filter((g) => g.eintraege.length);
    const fragen = (a?.fragen ?? []).filter((f) => passt(f.titel));
    const kacheln = (a?.kacheln ?? []).filter((k) => passt(k.titel));
    const gesamt = (a?.gruppen ?? []).reduce((n, g) => n + g.eintraege.length, 0) + (a?.fragen.length ?? 0) + (a?.kacheln.length ?? 0);
    return { gruppen, fragen, kacheln, gesamt, zahl: gruppen.reduce((n, g) => n + g.eintraege.length, 0) + fragen.length + kacheln.length };
  });

  // --- Notizen und Markierungen ---
  const TEXTWAHL_WARTEN_MS = 250;
  const LEISTE_ABSTAND_PX = 10;
  const STELLE_OBEN_ANTEIL = 0.2;

  let blatt = $state<{ notiz: Notiz | null; entwurf: NotizNeu | null; schreiben?: boolean } | null>(null);

  // Verweist hierher (WIKI-20): erst geholt, wenn "Über diesen Artikel" aufgeht; je Artikel einmal
  let hierher = $state.raw<Rueckverweise | null>(null);
  let hierherFuer = "";
  async function rueckverweiseLaden() {
    if (!artikel) return;
    const fuer = `${artikel.buch}/${artikel.pfad}`;
    if (hierherFuer === fuer) return;
    hierherFuer = fuer;
    hierher = null;
    try {
      const r = await rueckverweiseHolen(artikel.buch, artikel.pfad);
      if (hierherFuer === fuer) hierher = r;
    } catch {
      hierherFuer = "";
    }
  }
  // `markiert`: Notizen, deren Markierung die Auswahl berührt (dann entfernt die Leiste, statt doppelt zu markieren)
  let textwahl = $state<{ stelle: Stelle; markiert: Notiz[]; belege: number[]; x: number; y: number; unten: boolean } | null>(null);
  let kopiert = $state<"" | "ja" | "nein">("");
  let wahlLeiste = $state<HTMLElement>();
  let wahlWarten: ReturnType<typeof setTimeout> | undefined;

  const artikelNotizen = $derived(buch && artikel ? meins.notizen.filter((n) => n.buch_name === buch.name && n.pfad === artikel!.pfad) : []);

  // Markierungen im Text, sobald Text oder Notizen sich ändern (nur im Lesedesign; die Originalseite bleibt unberührt)
  $effect(() => {
    const t = text, notizen = artikelNotizen;
    if (t && artikel?.darstellung === "lesedesign") untrack(() => markieren(t, notizen));
  });

  /** Eine Auswahl im Text bietet die Werkzeugleiste an (über der Auswahl, am Telefon darunter, weil dort das Menü
   *  des Geräts über ihr steht). */
  function auswahlGeaendert() {
    clearTimeout(wahlWarten);
    wahlWarten = setTimeout(() => {
      const wahl = window.getSelection();
      const stelle = text ? stelleAus(text, wahl) : null;
      if (!stelle || !wahl) {
        textwahl = null;
        return;
      }
      const bereich = wahl.getRangeAt(0);
      const r = bereich.getBoundingClientRect();
      const unten = geraet.mobil || r.top < 140;
      const ids = new Set([...text!.querySelectorAll<HTMLElement>("mark.notiz")].filter((m) => bereich.intersectsNode(m)).map((m) => m.dataset.notiz));
      const markiert = artikelNotizen.filter((n) => ids.has(n.id));
      const belege = recherche.an ? belegeDerAuswahl(text!, bereich) : [];
      textwahl = { stelle, markiert, belege, x: r.left + r.width / 2, y: unten ? r.bottom + LEISTE_ABSTAND_PX : r.top - LEISTE_ABSTAND_PX, unten };
    }, TEXTWAHL_WARTEN_MS);
  }

  // Leiste ganz im Fenster halten
  const wahlLinks = $derived.by(() => {
    if (!textwahl) return 0;
    const breite = wahlLeiste?.offsetWidth ?? 0;
    return Math.min(Math.max(textwahl.x - breite / 2, 8), innerWidth - breite - 8);
  });

  function wahlBeenden() {
    textwahl = null;
    window.getSelection()?.removeAllRanges();
  }

  /** Markieren (und mit Blatt: gleich schreiben). Liegt die Stelle schon markiert vor, gilt die vorhandene Notiz: so
   *  entstehen keine doppelten Markierungen, die nach dem Löschen der einen weiter zu sehen wären. */
  async function anStelle(mitBlatt: boolean) {
    if (!artikel || !textwahl) return;
    const { stelle, belege } = textwahl;
    wahlBeenden();
    // Recherchemodus: die Belege des Absatzes und der Artikel im Netz kommen mit
    const recherchiert = recherche.an
      ? { belege: artikel.belege.filter((b) => belege.includes(b.nummer)), quelle_url: artikel.quelle_url } : {};
    try {
      const n = artikelNotizen.find((x) => x.zitat === stelle.zitat && x.davor === stelle.davor)
        ?? await notieren({ buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild, ...stelle, text: "",
                            ...recherchiert });
      if (mitBlatt) blatt = { notiz: n, entwurf: null, schreiben: true };
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  /** Markierungen in der Auswahl entfernen: ohne Text sofort, mit Text über das Blatt (dort mit Rückfrage). */
  async function entfernen() {
    if (!textwahl) return;
    const { markiert } = textwahl;
    wahlBeenden();
    try {
      for (const n of markiert.filter((x) => !x.text.trim())) await notizLoeschen(n.id);
    } catch (f) {
      fehler = seitenFehler(f);
    }
    const mitText = markiert.find((x) => x.text.trim());
    if (mitText) notizZeigen(mitText);
  }

  // Markierte Stelle übersetzen (WIKI-47): ins Deutsche, in deutschem Text ins Englische; das Ergebnis steht in der Leiste,
  // bis die Auswahl sich ändert. Den Knopf gibt es nur, wenn die Leitstelle da ist.
  let stellenBereit = $state(false);
  let wahlUebersetzung = $state<{ fuer: string; laeuft: boolean; text: string; grund: string } | null>(null);
  let uebersetzungKopiert = $state<"" | "ja" | "nein">("");
  $effect(() => {
    stellenstandHolen().then((s) => (stellenBereit = s.bereit)).catch(() => (stellenBereit = false));
  });
  async function stelleUebersetzenKlick() {
    if (!textwahl) return;
    const fuer = textwahl.stelle.zitat;
    wahlUebersetzung = { fuer, laeuft: true, text: "", grund: "" };
    try {
      const u = await stelleUebersetzen(fuer.slice(0, 4000), textSprache === "de" ? "en" : "de");
      if (wahlUebersetzung?.fuer === fuer) wahlUebersetzung = { fuer, laeuft: false, text: u.text, grund: u.grund };
    } catch (f) {
      if (wahlUebersetzung?.fuer === fuer) wahlUebersetzung = { fuer, laeuft: false, text: "", grund: seitenFehler(f) };
    }
  }
  async function uebersetzungKopieren() {
    uebersetzungKopiert = wahlUebersetzung?.text && (await kopieren(wahlUebersetzung.text)) ? "ja" : "nein";
    setTimeout(() => (uebersetzungKopiert = ""), RUECKMELDUNG_MS);
  }

  /** Zitat mit Herkunft in die Zwischenablage; die Leiste sagt kurz, ob es geklappt hat, und geht dann zu. */
  async function zitieren() {
    if (!artikel || !textwahl) return;
    const { zitat, abschnitt } = textwahl.stelle;
    kopiert = (await kopieren(zitatMitHerkunft(zitat, artikel.titel, abschnitt, buch ? bezeichnung(buch) : ""))) ? "ja" : "nein";
    setTimeout(() => {
      kopiert = "";
      wahlBeenden();
    }, RUECKMELDUNG_MS);
  }

  function notizZumArtikel() {
    if (!artikel) return;
    blatt = { notiz: null, entwurf: { buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild,
                                      abschnitt: "", zitat: "", davor: "", text: "",
                                      ...(recherche.an ? { quelle_url: artikel.quelle_url } : {}) } };
  }

  function notizZeigen(n: Notiz) {
    blatt = { notiz: n, entwurf: null };
    const mark = text?.querySelector<HTMLElement>(`mark[data-notiz="${CSS.escape(n.id)}"]`);
    if (mark) stelleZeigen(mark, "smooth");
  }

  /** Eine Stelle ins obere Fünftel rollen: darunter steht das Blatt der Notiz und soll sie nicht verdecken. */
  function stelleZeigen(el: HTMLElement, wie: ScrollBehavior) {
    const r = roller();
    const oben = r === document.scrollingElement ? 0 : r.getBoundingClientRect().top;
    r.scrollBy({ top: el.getBoundingClientRect().top - oben - r.clientHeight * STELLE_OBEN_ANTEIL, behavior: wie });
  }

  // --- Große Bildansicht: alle Bilder des Artikels, beim angetippten beginnend ---
  let bilder = $state.raw<{ medien: Medium[]; start: number } | null>(null);

  async function bildZeigen(quelle: string) {
    if (!artikel) return;
    try {
      const medien = await medienImArtikel(artikel.buch, artikel.pfad);
      bilder = { medien, start: Math.max(0, medien.findIndex((m) => m.bild === quelle)) };
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // Originalseite (WIKI-85): sie läuft mit ihren Skripten abgeschirmt ohne eigene Herkunft und kommt nicht an die App;
  // beide sprechen nur über die Brücke (lib/originalrahmen.ts). Die App setzt den Rahmen an ihren Ort, ohne neuen
  // Eintrag im Verlauf (den hat die App schon); geht die Seite selbst weiter (eigene Skripte, Formulare), folgt die App.
  // Der Rahmen füllt die Fläche und rollt selbst, auch am Telefon: Seiten mit eigener Bedienung (feste Kopfzeilen,
  // Dialoge, Höhen nach dem Fenster) brauchen ein Fenster wie im Browser.
  let rahmen = $state<HTMLIFrameElement>();
  const kopfSchmal = $derived(artikel?.darstellung === "original");
  let kopfOffen = $state(false);
  const rahmenAdresse = $derived(zeigeOriginal && artikel?.original
    ? rahmenZiel(artikel.original, zusatz.get("abfrage") ?? "", anker || artikel.anker) : "");

  $effect(() => {
    const r = rahmen, ziel = rahmenAdresse;
    if (!r || !ziel || laedt || r.dataset.ort === ortVon(ziel)) return;   // die Seite ist schon dort (ging selbst hin)
    r.dataset.ort = ortVon(ziel);
    r.contentWindow?.location.replace(ziel);
  });

  $effect(() => {
    const z = zoom;
    untrack(() => rahmenSenden({ art: "zoom", wert: z }));
  });

  // die Seite hat keine Herkunft, an die man schreiben könnte: Nachrichten gehen an den Rahmen selbst, und nur seine zählen
  function rahmenSenden(nachricht: Record<string, unknown>) {
    rahmen?.contentWindow?.postMessage({ nachschlag: 1, ...nachricht }, "*");
  }

  function rahmenNachricht(e: MessageEvent) {
    const r = rahmen;
    if (!r || e.source !== r.contentWindow || e.origin !== OHNE_HERKUNFT || !istRahmenmeldung(e.data)) return;
    const ort = ortNormal(e.data.ort);
    if (e.data.art === "verweis") {
      gehe(lesenWeg(e.data.ort));
      return;
    }
    r.dataset.ort = ort;
    rahmenSenden({ art: "zoom", wert: zoom });
    if (rahmenAdresse && ort !== ortVon(rahmenAdresse)) gehe(lesenWeg(e.data.ort), true);
  }

  async function zufall() {
    try {
      const z = await zufallHolen(buchKennung);
      lesen(z.buch, z.pfad);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // Inhalt wie im Entwurf: Abschnitte und ihre Unterabschnitte (tiefere Ebenen laufen über ihren Unterabschnitt mit)
  const INHALT_BIS_EBENE = 3;
  const inhalt = $derived((artikel?.abschnitte ?? []).filter((a) => a.ebene <= INHALT_BIS_EBENE));
  const aktivImInhalt = $derived.by(() => {
    const alle = artikel?.abschnitte ?? [];
    for (let i = alle.findIndex((a) => a.anker === aktiv); i >= 0; i--) if (alle[i].ebene <= INHALT_BIS_EBENE) return alle[i].anker;
    return "";
  });
  const indexAktiv = $derived(inhalt.findIndex((a) => a.anker === aktivImInhalt));
  const nummern = $derived.by(() => {
    let n = 0;
    return inhalt.map((a) => (a.ebene === 2 ? String(++n) : ""));
  });
</script>

<div class="inhalt-stufe" class:nur-blatt={nurBlatt} data-schrift="klein">
{#if fehler && !artikel}
  <div class="seiten-kopf"><h1>Artikel</h1></div>
  <div class="rollfeld"><div class="karte"><div class="fehlertext">{fehler}</div></div></div>
{:else if !artikel}
  <div class="laden">Lädt ...</div>
{:else}
  <!-- Bücher, die nur im Original laufen (eigene Seite mit eigener Bedienung, WIKI-85): der Kopf ist eine schmale Zeile mit
       dem Pfad, Titel und Werkzeuge klappt ein Knopf auf (wie ein Menü), damit die Seite fast die ganze Fläche hat -->
  <div class="artikel-kopf" class:schmal={kopfSchmal} class:offen={kopfOffen}>
    <!-- der Pfad ist anklickbar (WIKI-49): Quelle zur Startseite, Rubrik zu ihrer Seite (oder gefiltert auf der Startseite),
         der Titel nach oben -->
    <nav class="pfad" aria-label="Pfad"><i class="fa-solid fa-book"></i>
      <a href={buch ? "/" + lesenZiel(artikel.buch, buch.startseite) : undefined}
         onclick={(e) => { if (!buch) return; e.preventDefault(); lesen(artikel!.buch, buch.startseite); }}><b><Buchmarke kennung={artikel.buch} symbol={false} /></b></a>
      {#if buch?.archiv}<span class="pille-archiv" title="Diese Quelle liegt im Archiv (Startseite, Bibliothek, Archiv)"><i class="fa-solid fa-box-archive"></i>Archiv</span>{/if}
      <i class="fa-solid fa-chevron-right"></i>
      {#if artikel.rubrik}
        <a href={rubrikZiel ? "/" + rubrikZiel : undefined} onclick={(e) => { if (!rubrikZiel) return; e.preventDefault(); gehe(rubrikZiel); }}>{artikel.rubrik}</a>
        <i class="fa-solid fa-chevron-right"></i>
      {/if}
      <a href="#oben" onclick={(e) => { e.preventDefault(); roller().scrollTo({ top: 0, behavior: "smooth" }); }}>{artikel.titel}</a>
      {#if kopfSchmal}
        <button class="knopf still kopf-schalter" aria-expanded={kopfOffen} onclick={() => (kopfOffen = !kopfOffen)}
                title={kopfOffen ? "Titel und Werkzeuge einklappen" : "Titel und Werkzeuge zeigen: Merken, Notiz, Thema, Zufall, Lesegröße"}>
          <i class="fa-solid {kopfOffen ? 'fa-xmark' : 'fa-bars'}"></i></button>
      {/if}</nav>
    <h1 class:code-titel={artikel.titelart === "code"}>{artikel.titel}</h1>
    <div class="werkzeuge">
      <button class="knopf" class:an={!!eintrag} title={eintrag ? "Vom Merkzettel nehmen" : "Auf den Merkzettel"} onclick={merkenUmschalten}>
        <i class="fa-{eintrag ? 'solid' : 'regular'} fa-bookmark"></i><span class="wort">{eintrag ? "Gemerkt" : "Merken"}</span></button>
      <button class="knopf" title="Notiz zum ganzen Artikel; für eine Stelle den Text markieren" onclick={notizZumArtikel}>
        <i class="fa-regular fa-note-sticky"></i><span class="wort">Notiz</span>{#if artikelNotizen.length}<span class="zahl">{artikelNotizen.length}</span>{/if}</button>
      {#if buch}<ThemaWahl artikel={{ buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild }} buchName={buch.name} />{/if}
      {#if artikel.darstellung !== "original" && artikel.original}<!-- ohne Original: Seiten, die das Buch nicht selbst hat (Kategorien aus den Datenabzügen) -->
        <button class="knopf" class:an={original} title="Die Seite so, wie sie in der Quelle steht" onclick={() => (original = !original)}>
          <i class="fa-solid fa-file-code"></i><span class="wort">Original</span></button>
      {/if}
      <button class="knopf still" title="Ein zufälliger Artikel aus dieser Quelle" onclick={zufall}>
        <i class="fa-solid fa-dice"></i><span class="wort">Zufall</span></button>
      {#if artikel.darstellung === "lesedesign"}
        <VorleseKnopf kennung={vorleseKennung} beschriftung={geraet.mobil ? "" : "Vorlesen"} titel="Ab dem Abschnitt vorlesen, in dem du liest"
                      daten={{ sprache: textSprache || "de" }} text={() => (text ? vorlesetext(text, aktiv) : "")} />
      {/if}
      {#if uebersetzbar && !zeigeOriginal}
        <button class="knopf" class:an={aufDeutsch || (deutsch.an && ue?.zustand === "laeuft")} onclick={deutschUmschalten}
                title={aufDeutsch && ue?.uebersetzung
                  ? `Von uns übersetzt aus dem ${ue.uebersetzung.aus}; Code, Namen und Zahlen unverändert${ue.uebersetzung.im_original ? `, ${ue.uebersetzung.im_original} ${ue.uebersetzung.im_original === 1 ? "Stelle" : "Stellen"} im Original` : ""}. Antippen: wieder ${buch ? spracheInWorten(buch.sprache) : "im Original"}`
                  : "Auf Deutsch übersetzen (gekennzeichnet; Code, Namen und Zahlen bleiben)"}>
          <i class="fa-solid fa-language"></i><span class="wort">Deutsch</span></button>
      {/if}
      {#if artikel.belege.length || artikel.quelle_url}
        <button class="knopf" class:an={recherche.an} onclick={rechercheUmschalten}
                title={recherche.an ? "Recherche an: Markierungen und Notizen nehmen ihre Belege mit" : "Recherche: Belege mit den Notizen sammeln"}>
          <i class="fa-solid fa-graduation-cap"></i><span class="wort">Recherche</span></button>
      {/if}
      <div class="rechts">
        {#if fassungen && !zeigeOriginal}
          <Auswahl wert={meineFassung} symbol="fa-code-branch" titel="Meine Fassung, bleibt für diese Quelle eingestellt" onwahl={fassungWaehlen}
                   optionen={[{ wert: "", titel: "Alle Fassungen" },
                              ...fassungen.optionen.map((f) => ({ wert: f, titel: `Meine Fassung: ${fassungen!.produkt} ${f}` }))]} />
        {/if}
        {#if artikel.darstellung === "lesedesign" && !zeigeOriginal}
          <!-- am Telefon hat die Wissensleiste keinen Platz: dort nur A und C -->
          <Auswahl wert={geraet.mobil && leseansicht.wert === "b" ? "a" : leseansicht.wert} symbol="fa-table-columns"
                   titel="Ansicht, bleibt auf diesem Gerät eingestellt" onwahl={ansichtMerken}
                   optionen={geraet.mobil ? ANSICHTEN.filter((a) => a.wert !== "b") : ANSICHTEN} />
        {/if}
        {#if buch}<Lesegroesse buchName={buch.name} buchTitel={buch.titel} />{/if}
      </div>
    </div>
  </div>
  <!-- Der Filter zeigt sich an der Auswahl "Meine Fassung" und an den Markierungen im Text (Nutzer: kein Band); ein Band
       nur, wenn es die Seite in der gewählten Fassung gar nicht gibt -->
  {#if fassungen && meineFassung && !zeigeOriginal && !gibtEsInFassung}
    <div class="fundband fassung warn">
      <i class="fa-solid fa-triangle-exclamation"></i>
      <span><b>Diese Seite gibt es in {fassungen.produkt} {meineFassung} nicht.</b> Die Fassungen, in denen es sie gibt, nennt der Steckbrief.</span>
      <button class="knopf still" onclick={() => fassungWaehlen("")}><i class="fa-solid fa-xmark"></i>Filter aus</button>
    </div>
  {/if}
  {#if uebersetzbar && !zeigeOriginal && ue}
    <!-- übersetzt zeigt es der angeschaltete Knopf "Deutsch" (Nutzer: kein eigenes Band); Bänder nur für Arbeit und Fehler -->
    {#if ue.zustand === "laeuft" && deutsch.an && !aufDeutsch}
      <div class="fundband uebersetzt">
        <i class="fa-solid fa-spinner fa-spin-pulse"></i>
        <span><b>Wird übersetzt</b>{ue.schritt ? `: ${ue.schritt}` : ""}{ue.anteil !== null ? ` (${Math.round(ue.anteil * 100)} %)` : ""}. Die Seite wechselt von selbst.</span>
      </div>
    {:else if ue.zustand === "fehler" && deutsch.an}
      <div class="fundband warn">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <span><b>Übersetzung gescheitert:</b> {ue.grund}</span>
        <button class="knopf still" onclick={anstossen}><i class="fa-solid fa-rotate-right"></i>Nochmal</button>
      </div>
    {/if}
  {/if}
  {#if frage}
    <div class="fundband">
      <i class="fa-solid {weg === 'bedeutung' ? 'fa-wand-magic-sparkles' : 'fa-magnifying-glass'}"></i>
      <span>Gefunden zu <span class="frage">"{frage}"</span>{abschnitt ? ` im Abschnitt ${abschnitt}` : ""}</span>
      <span class="weg">{weg === "bedeutung" ? "Bedeutung" : "Index"}</span>
      {#if abschnitt}<button class="knopf still" onclick={zurStelle}><i class="fa-solid fa-arrow-down"></i>Zur Stelle</button>{/if}
      <button class="knopf still" onclick={() => suchen(frage)}><i class="fa-solid fa-list"></i>Alle Treffer</button>
    </div>
  {/if}
  {#if artikel.darstellung === "uebersicht" && !original}
    <!-- Übersicht (etwa Startseite eines Buchs): Kacheln als Karten wie im Entwurf start-a.html -->
    <div class="rollfeld" style="padding: 0" style:zoom={zoom}>
      <!-- Filter der Übersicht (WIKI-17, docs/SUCHE.md Punkt 2): sofort in der Liste, darunter die Suche im ganzen Buch -->
      <div class="uebersicht-filter">
        <label class="suchfeld"><i class="fa-solid fa-filter"></i>
          <input name="filter-text" type="search" bind:value={filterText} placeholder="In dieser Übersicht filtern" aria-label="In dieser Übersicht filtern" /></label>
        {#if filterText.trim()}
          <button class="knopf" onclick={() => suchen(filterText.trim(), artikel!.buch, true)}><i class="fa-solid fa-magnifying-glass"></i>In der ganzen Quelle suchen</button>
          <span class="filter-stand">{gefiltert.zahl} von {gefiltert.gesamt}</span>
        {/if}
      </div>
      {#if filterText.trim() && !gefiltert.zahl}
        <p class="leer-hinweis uebersicht-leer">Nichts in dieser Übersicht passt zu "{filterText.trim()}". "In der ganzen Quelle suchen" findet es auch in den Seiten selbst.</p>
      {/if}
      {#if gefiltert.gruppen.length}
        <!-- Handbuch: die Rubriken der Gliederung mit ihren Seiten -->
        <div class="rubriken">
          {#each gefiltert.gruppen as g, gi (gi)}
            <section class="rubrik">
              <h2 class="rubrik-titel">{g.titel}<span class="zahl">{g.eintraege.length}</span></h2>
              <ol class="code-liste">
                {#each g.eintraege as e, ei (ei)}
                  <li><a class:code={istCode(e.titel)} href={"/" + lesenZiel(artikel.buch, e.pfad)}
                         onclick={(k) => { k.preventDefault(); lesen(artikel!.buch, e.pfad); }}>{e.titel}</a></li>
                {/each}
              </ol>
            </section>
          {/each}
        </div>
      {/if}
      {#if gefiltert.fragen.length}
        <!-- Fragenliste (Frage und Antwort): Karten mit Stimmen und Antworten, Blättern über die Seiten der Quelle -->
        <div class="fragenliste">
          {#each gefiltert.fragen as f, fi (fi)}
            <Fragekarte buch={artikel.buch} frage={f} />
          {/each}
          {#if artikel.zurueck || artikel.weiter}
            <div class="blaettern">
              {#if artikel.zurueck}<button class="knopf" onclick={() => lesen(artikel!.buch, artikel!.zurueck)}><i class="fa-solid fa-chevron-left"></i>Zurück</button>{/if}
              {#if artikel.weiter}<button class="knopf weiter" onclick={() => lesen(artikel!.buch, artikel!.weiter)}>Weiter<i class="fa-solid fa-chevron-right"></i></button>{/if}
            </div>
          {/if}
        </div>
      {/if}
      <div class="uebersicht">
        {#each gefiltert.kacheln as k, ki (ki)}
          <Kachel bild={k.bild} titel={k.titel} adresse={"/" + lesenZiel(artikel.buch, k.pfad)} ziel={() => lesen(artikel!.buch, k.pfad)} />
        {/each}
      </div>
    </div>
  {:else if artikel.darstellung === "anleitung" && artikel.anleitung && !original}
    <!-- Anleitung (iFixit, WIKI-64): Lesen oder Werkstatt -->
    <Anleitung {artikel} notizen={artikelNotizen} onnotiz={notizZumArtikel} onnotizzeigen={notizZeigen} />
  {:else if artikel.darstellung === "anleitungen" && artikel.geraet && !original}
    <!-- Startseite eines Anleitungsbuchs: Anleitungen finden, ohne Filter die Kategorien (WIKI-64) -->
    <Anleitungssuche {artikel} />
  {:else if artikel.darstellung === "uebung" && artikel.uebung && !original}
    <!-- Aufgabe eines Übungsbuchs (freeCodeCamp, WIKI-66) -->
    <Uebung {artikel} />
  {:else if artikel.darstellung === "uebungen" && artikel.kurse && !original}
    <!-- Startseite eines Übungsbuchs: Kurse, Blöcke, Aufgaben -->
    <Uebungen {artikel} />
  {:else if artikel.darstellung === "kategorie" && artikel.kategorie && !original}
    <!-- Kategorie eines Buchs mit Kategorien (WIKI-75): Ober-, Unterkategorien, alle Seiten -->
    <Kategorieseite {artikel} />
  {:else if artikel.darstellung === "geraet" && artikel.geraet && !original}
    <!-- Gerät oder Kategorie eines Anleitungsbuchs (WIKI-64) -->
    <Geraeteseite {artikel} />
  {:else if zeigeOriginal}
    <!-- mit ihren Skripten, abgeschirmt ohne eigene Herkunft (WIKI-85; dieselben Rechte setzt die Seite selbst): sie kommt
         nicht an Speicher und Cookies der App; die App setzt den Ort, die Seite meldet sich über die Brücke -->
    <iframe class="original" title="Originalseite: {artikel.titel}" bind:this={rahmen} allow="fullscreen; clipboard-write"
            sandbox="allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads"></iframe>
  {:else}
    <div class="rollfeld" style="padding: 0" bind:this={rollfeld}>
      <div class="lesen" class:ohne-inhalt={!inhalt.length && !artikel.nachbarn.length} class:mit-wissen={mitWissen} data-art={buch?.art} style:zoom={zoom}>
        {#if inhalt.length || artikel.nachbarn.length}
          <nav class="inhalt" aria-label="Inhalt">
            <div class="inhalt-titel">Inhalt</div>
            <ol>
              {#each inhalt as a, i (a.anker)}
                <li class:unter={a.ebene > 2} class:aktiv={a.anker === aktivImInhalt} class:gelesen={indexAktiv > i}>
                  <a href="#{a.anker}" onclick={(e) => { e.preventDefault(); springen(a.anker); }}>
                    {#if a.ebene === 2}<span class="nr">{nummern[i]}</span>{/if}{a.titel}</a>
                </li>
              {/each}
            </ol>
            <div class="lesestand"><span style="width: {Math.round(anteil * 100)}%"></span></div>
            <div class="lesestand-text">{Math.round(anteil * 100)} % gelesen · noch {restMinuten} Min</div>
            {#if artikel.nachbarn.length}
              <!-- Nachbarn in der Rubrik (Dokumentation): die Seite selbst hervorgehoben -->
              <div class="inhalt-titel nachbarn-titel">Nachbarn in {artikel.rubrik}</div>
              <ol class="code-liste">
                {#each artikel.nachbarn as n, ni (ni)}
                  <li class:aktiv={n.pfad === artikel.pfad}><a class:code={istCode(n.titel)} href={"/" + lesenZiel(artikel.buch, n.pfad)}
                      onclick={(e) => { e.preventDefault(); lesen(artikel!.buch, n.pfad); }}>{n.titel}</a></li>
                {/each}
              </ol>
            {/if}
          </nav>
        {/if}
        {#if nurBlatt}<h1 class="blatt-titel" class:code-titel={artikel.titelart === "code"}>{artikel.titel}</h1>{/if}
        <article class="artikel" bind:this={artikelEl}>
          {#if artikel.steckbrief}
            <aside class="steckbrief">
              <div class="steckbrief-kopf" class:code-titel={artikel.steckbrief.code}>{artikel.steckbrief.titel}</div>
              <!-- vom Baustein gesäubert: nur erlaubte Elemente und Attribute, Verweise auf Wege der App -->
              <div role="presentation" onclick={klick} onkeydown={() => {}}>{@html artikel.steckbrief.html}</div>
            </aside>
          {/if}
          <div class="artikel-text" lang={textSprache || undefined} bind:this={text} role="presentation"
               onclick={klick} onkeydown={() => {}}>{@html artikel.html}</div>
          {#if artikel.kategorien?.length}
            <!-- Kategorien der Seite, wie das Buch sie nennt (WIKI-75) -->
            <nav class="artikel-kategorien" aria-label="Kategorien">
              <i class="fa-solid fa-folder-tree"></i>
              {#each artikel.kategorien as k (k.pfad)}
                <a class="chip" href={"/" + lesenZiel(artikel.buch, k.pfad)}
                   onclick={(e) => { if (e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); lesen(artikel!.buch, k.pfad); } }}>{k.titel}</a>
              {/each}
            </nav>
          {/if}
          {#if artikelNotizen.length}
            <section class="deine-notizen">
              <h2><i class="fa-solid fa-note-sticky"></i>Deine Notizen<span class="zahl">{artikelNotizen.length}</span></h2>
              {#each artikelNotizen as n (n.id)}
                <button class="notiz-karte" onclick={() => notizZeigen(n)}>
                  {#if n.zitat}<span class="zitat">"{n.zitat}"</span>{/if}
                  <span class="text">{n.text || "Markierung ohne Notiz"}</span>
                  <span class="wann">{wann(n.geaendert)} · {n.zitat ? `Abschnitt ${n.abschnitt || "Einleitung"}` : "am ganzen Artikel"}</span>
                </button>
              {/each}
            </section>
          {/if}
          <details class="artikel-ueber" ontoggle={(e) => (e.currentTarget as HTMLDetailsElement).open && rueckverweiseLaden()}>
            <summary><i class="fa-solid fa-circle-info"></i>Über diesen Artikel<span>Quelle, Verweise</span></summary>
            <dl>
              <dt>Quelle</dt><dd>{buch ? bezeichnung(buch) : artikel.buch}{buch ? `, Stand ${datum(buch.stand)}` : ""}</dd>
              {#if buch?.beschreibung}<dt>Quelle</dt><dd>{buch.beschreibung}</dd>{/if}
              <dt>Verweise</dt><dd>{artikel.verweise.intern} in der Quelle{artikel.verweise.ohne_ziel ? `, ${artikel.verweise.ohne_ziel} ohne Ziel in der Quelle (nur Text)` : ""}{artikel.verweise.koordinaten ? `, ${artikel.verweise.koordinaten} Orte` : ""}</dd>
              {#if artikel.online.length}
                <dt>Im Netz</dt>
                <dd><ul>{#each artikel.online as o}<li><a href={o} target="_blank" rel="noopener noreferrer">{o}</a></li>{/each}</ul></dd>
              {/if}
              {#if hierher?.bekannt}
                <!-- Rückverweise aus dem eigenen Index (WIKI-20) -->
                <dt>Verweist hierher</dt>
                <dd>{#if hierher.gesamt}<ul class="hierher">{#each hierher.seiten as s (s.pfad)}<li><a href={"/" + lesenZiel(artikel.buch, s.pfad)}
                      onclick={(e) => { if (e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); lesen(artikel!.buch, s.pfad); } }}>{s.titel}</a></li>{/each}</ul>
                    {#if hierher.gesamt > hierher.seiten.length}<span class="blass">und {hierher.gesamt - hierher.seiten.length} weitere</span>{/if}
                  {:else}keine Seite der Quelle{/if}</dd>
              {/if}
              <dt>Aufbereitet</dt><dd>Baustein {artikel.baustein === "enzyklopaedie" ? "Enzyklopädie" : artikel.baustein}</dd>
              {#if aufDeutsch && ue?.uebersetzung}
                <dt>Übersetzung</dt><dd>von uns, über die Leitstelle{ue.uebersetzung.modell ? ` (${ue.uebersetzung.modell})` : ""}, {wann(ue.uebersetzung.wann)}</dd>
              {/if}
            </dl>
          </details>
        </article>
        {#if mitWissen}
          <!-- Ansicht B: Wissensleiste neben dem Text (Entwurf artikel-b.html); unter 1180 px wie A -->
          <aside class="wissen" aria-label="Wissen zum Artikel">
            <div class="reiter" role="tablist">
              {#if artikel.steckbrief}
                <button role="tab" aria-selected={reiterJetzt === "steckbrief"} class:aktiv={reiterJetzt === "steckbrief"} onclick={() => (reiter = "steckbrief")}>
                  <i class="fa-solid fa-id-card"></i>Steckbrief</button>
              {/if}
              <button role="tab" aria-selected={reiterJetzt === "notizen"} class:aktiv={reiterJetzt === "notizen"} onclick={() => (reiter = "notizen")}>
                <i class="fa-solid fa-note-sticky"></i>Notizen{#if artikelNotizen.length}<span class="zahl">{artikelNotizen.length}</span>{/if}</button>
              <button role="tab" aria-selected={reiterJetzt === "medien"} class:aktiv={reiterJetzt === "medien"} onclick={() => (reiter = "medien")}>
                <i class="fa-solid fa-images"></i>Medien</button>
            </div>
            <div class="wissen-inhalt">
              {#if reiterJetzt === "steckbrief" && artikel.steckbrief}
                <div class="steckbrief">
                  <div class="steckbrief-kopf" class:code-titel={artikel.steckbrief.code}>{artikel.steckbrief.titel}</div>
                  <div role="presentation" onclick={klick} onkeydown={() => {}}>{@html artikel.steckbrief.html}</div>
                </div>
              {:else if reiterJetzt === "notizen"}
                {#each artikelNotizen as n (n.id)}
                  <button class="notiz-karte" onclick={() => notizZeigen(n)}>
                    {#if n.zitat}<span class="zitat">"{n.zitat}"</span>{/if}
                    <span class="text">{n.text || "Markierung ohne Notiz"}</span>
                    <span class="wann">{wann(n.geaendert)} · {n.zitat ? `Abschnitt ${n.abschnitt || "Einleitung"}` : "am ganzen Artikel"}</span>
                  </button>
                {:else}
                  <p class="leer-hinweis">Noch keine Notizen zu diesem Artikel. Für eine Stelle den Text markieren, für den ganzen Artikel oben "Notiz".</p>
                {/each}
              {:else if wissenMedien === null}
                <div class="laden">Lädt ...</div>
              {:else if !wissenMedien.length}
                <p class="leer-hinweis">Keine Bilder in diesem Artikel.</p>
              {:else}
                <div class="wissen-medien">
                  {#each wissenMedien as m, i (m.bild)}
                    <button title={m.unterschrift} onclick={() => (bilder = { medien: wissenMedien!, start: i })}>
                      <img src={m.bild} alt={m.unterschrift} loading="lazy" decoding="async" /></button>
                  {/each}
                </div>
              {/if}
            </div>
          </aside>
        {/if}
      </div>
    </div>
    {#if nurBlatt}
      <!-- Ansicht C: schmaler Kopf mit dem Lesestand als Linie, Werkzeuge schwebend unten, Inhalt als Tafel -->
      <header class="ruhe-kopf">
        <button class="rund" title="Zurück" onclick={() => history.back()}><i class="fa-solid fa-arrow-left"></i></button>
        <span class="titel" class:code-titel={artikel.titelart === "code"}>{artikel.titel}</span>
        <span class="buch"><Buchmarke kennung={artikel.buch} symbol={false} /></span>
        {#if aufDeutsch}<span class="pille-uebersetzt" title="Von uns übersetzt; Code, Namen und Zahlen unverändert"><i class="fa-solid fa-language"></i>übersetzt</span>{/if}
        <div class="rechts">
          <button class="rund" title="Zurück zur Ansicht mit Schale" onclick={() => ansichtMerken("a")}><i class="fa-solid fa-table-columns"></i></button>
        </div>
        <span class="fortschritt" style:width="{Math.round(anteil * 100)}%"></span>
      </header>
      {#if inhaltTafel && inhalt.length}
        <nav class="inhalt-tafel" aria-label="Inhalt">
          <ol>
            {#each inhalt as a, i (a.anker)}
              <li class:unter={a.ebene > 2} class:aktiv={a.anker === aktivImInhalt}>
                <a href="#{a.anker}" onclick={(e) => { e.preventDefault(); inhaltTafel = false; springen(a.anker); }}>
                  {#if a.ebene === 2}<span class="nr">{nummern[i]}</span>{/if}{a.titel}</a>
              </li>
            {/each}
          </ol>
        </nav>
      {/if}
      <div class="schwebeleiste" role="toolbar" aria-label="Werkzeuge">
        {#if inhalt.length}
          <button class="knopf still" class:an={inhaltTafel} onclick={() => (inhaltTafel = !inhaltTafel)}><i class="fa-solid fa-list"></i><span class="wort">Inhalt</span></button>
        {/if}
        <VorleseKnopf kennung={vorleseKennung} beschriftung={geraet.mobil ? "" : "Vorlesen"} titel="Ab dem Abschnitt vorlesen, in dem du liest"
                      daten={{ sprache: textSprache || "de" }} text={() => (text ? vorlesetext(text, aktiv) : "")} />
        <button class="knopf still" class:an={!!eintrag} title={eintrag ? "Vom Merkzettel nehmen" : "Auf den Merkzettel"} onclick={merkenUmschalten}>
          <i class="fa-{eintrag ? 'solid' : 'regular'} fa-bookmark"></i></button>
        <button class="knopf still" title="Notiz zum ganzen Artikel; für eine Stelle den Text markieren" onclick={notizZumArtikel}>
          <i class="fa-regular fa-note-sticky"></i></button>
        {#if uebersetzbar}
          <button class="knopf still" class:an={aufDeutsch} title={aufDeutsch ? "Wieder in der Sprache der Quelle" : "Auf Deutsch übersetzen"} onclick={deutschUmschalten}>
            <i class="fa-solid fa-language"></i></button>
        {/if}
        {#if buch}<Lesegroesse buchName={buch.name} buchTitel={buch.titel} />{/if}
        <span class="trenner"></span>
        <button class="knopf still" title="Zurück zur Ansicht mit Schale" onclick={() => ansichtMerken("a")}>
          <i class="fa-solid fa-table-columns"></i><span class="wort">Schale</span></button>
      </div>
    {/if}
  {/if}
{/if}
{#if bibliothek.meldung && !artikel}<div class="fehlertext">{bibliothek.meldung}</div>{/if}
</div>

<svelte:document onselectionchange={auswahlGeaendert} />
<svelte:window onmessage={rahmenNachricht} />
{#if textwahl}
  <!-- die Auswahl bleibt beim Tippen auf die Leiste bestehen -->
  <div class="auswahl-leiste" class:unten={textwahl.unten} bind:this={wahlLeiste} role="toolbar" tabindex="-1" aria-label="Stelle"
       style="left: {wahlLinks}px; top: {textwahl.y}px" onpointerdown={(e) => e.preventDefault()} onmousedown={(e) => e.preventDefault()}>
    {#if textwahl.markiert.length}
      <button onclick={entfernen}><i class="fa-solid fa-eraser"></i>Entfernen</button>
    {:else}
      <button onclick={() => anStelle(false)}><i class="fa-solid fa-highlighter"></i>Markieren</button>
    {/if}
    <button onclick={() => anStelle(true)}><i class="fa-solid fa-note-sticky"></i>Notiz</button>
    <button class:kopiert-ok={kopiert === "ja"} onclick={zitieren} title="Zitat mit Artikel, Abschnitt und Quelle in die Zwischenablage">
      <i class="fa-solid {kopiert === 'ja' ? 'fa-check' : kopiert === 'nein' ? 'fa-triangle-exclamation' : 'fa-quote-right'}"></i>{kopiert === "ja" ? "Kopiert" : kopiert === "nein" ? "Geht nicht" : "Zitieren"}</button>
    <button onclick={() => { const z = textwahl!.stelle.zitat; textwahl = null; suchen(z.slice(0, 200)); }}><i class="fa-solid fa-magnifying-glass"></i>Suchen</button>
    {#if stellenBereit}
      <button class:an={wahlUebersetzung?.fuer === textwahl.stelle.zitat} onclick={stelleUebersetzenKlick}
              title={textSprache === "de" ? "Ins Englische übersetzen" : "Ins Deutsche übersetzen"}><i class="fa-solid fa-language"></i>Übersetzen</button>
    {/if}
    {#if wahlUebersetzung && wahlUebersetzung.fuer === textwahl.stelle.zitat}
      <div class="wahl-uebersetzung" aria-live="polite">
        {#if wahlUebersetzung.laeuft}<span class="laeuft"><i class="fa-solid fa-spinner fa-spin-pulse"></i>Übersetzt ...</span>
        {:else if wahlUebersetzung.grund}<span class="grund">{wahlUebersetzung.grund}</span>
        {:else}
          <span class="text">{wahlUebersetzung.text}</span>
          <button class="kopieren" class:kopiert-ok={uebersetzungKopiert === "ja"} onclick={uebersetzungKopieren}>
            <i class="fa-{uebersetzungKopiert === 'ja' ? 'solid fa-check' : 'regular fa-copy'}"></i>{uebersetzungKopiert === "ja" ? "Kopiert" : "Kopieren"}</button>
        {/if}
      </div>
    {/if}
  </div>
{/if}
{#if bilder && artikel}
  <Leuchtkasten medien={bilder.medien} start={bilder.start} titel={`in ${artikel.titel}`} onzu={() => (bilder = null)} />
{/if}
{#if probe}
  <!-- erst beim Öffnen geladen: Editor und Debugger (CodeMirror) braucht nur, wer etwas ausprobiert -->
  {#await import("../teile/Ausprobieren.svelte") then { default: Ausprobieren }}
    <Ausprobieren {probe} onzu={() => (probe = null)} onbehalten={beispielBehalten} />
  {/await}
{/if}
{#if codeGross}
  <Codeansicht html={codeGross.html} text={codeGross.text} sprache={codeGross.sprache} onzu={() => (codeGross = null)} />
{/if}
{#if blatt}
  <NotizBlatt notiz={blatt.notiz} entwurf={blatt.entwurf} schreiben={blatt.schreiben} onzu={() => (blatt = null)} />
{/if}
