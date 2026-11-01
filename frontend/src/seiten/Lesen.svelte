<script lang="ts">
  // Artikel lesen, Variante A (Entwurf mockups/artikel-a.html): ruhige Lesespalte, Inhalt links mitlaufend mit
  // Lesestand, Steckbrief rechts im Text. Weg: /lesen/<buch>/<pfad>?frage=&abschnitt=&anker=&notiz=. Bücher ohne eigenes
  // Lesedesign zeigen ihre Seite unverändert (Originalansicht). Verweise im Text bleiben in der App.
  import Buchmarke from "../teile/Buchmarke.svelte";
  import { gehe, navigation, seitenFehler } from "appkern-oberflaeche";
  import { tick, untrack } from "svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, buch as buchVon, datum, hauptbuch, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, zufallHolen } from "../lib/schnittstelle";
  import type { Artikel } from "../lib/typen";
  import { lesen, lesenZiel, suchen, verweisZiel } from "../lib/ziele";
  import { Auswahl } from "appkern-oberflaeche";
  import { kopieren } from "appkern-oberflaeche";
  import { RUECKMELDUNG_MS, zitatMitHerkunft } from "../lib/zitat";
  import { istCode } from "../lib/code";
  import { codeEinfaerben, spracheAus } from "../lib/einfaerben";
  import { htmlSprache } from "../lib/sprache";
  import { gemerkt, lesestandMelden, meins, meinsLaden, merken, notieren, notizLoeschen, vergessen, vorliebeSetzen, wann,
           type Notiz, type NotizNeu } from "../lib/meins.svelte";
  import { markieren, stelleAus, type Stelle } from "../lib/stellen";
  import { geraet } from "appkern-oberflaeche";
  import NotizBlatt from "../teile/NotizBlatt.svelte";
  import ThemaWahl from "../teile/ThemaWahl.svelte";
  import Lesegroesse from "../teile/Lesegroesse.svelte";
  import { groesseFuer } from "../lib/lesegroesse.svelte";
  import Kachel from "../teile/Kachel.svelte";
  import Fragekarte from "../teile/Fragekarte.svelte";
  import Leuchtkasten from "../teile/Leuchtkasten.svelte";
  import { medienImArtikel, type Medium } from "../lib/medien";
  import { themenLaden } from "../lib/themen.svelte";
  import { anwenden as fassungAnwenden, bekannte as bekannteFassungen, fassungenAus, gemerkt as fassungGemerkt, merken as fassungMerken,
           type Fassungen } from "../lib/fassung";

  const WOERTER_JE_MINUTE = 200;
  const MITLAUF_ABSTAND_PX = 90;          // eine Überschrift gilt als erreicht, sobald sie so nah am oberen Rand steht

  let artikel = $state.raw<Artikel | null>(null);   // nur lesen, ohne Proxy
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
  const restMinuten = $derived(Math.max(1, Math.round((woerter * (1 - anteil)) / WOERTER_JE_MINUTE)));

  // Lesegröße dieses Buchs auf diesem Gerät (WIKI-29) als Zoom des Lesebereichs, auch in der Originalseite
  const zoom = $derived(buch ? groesseFuer(buch.name) / 100 : 1);

  // Ohne Buch im Weg: die Startseite des Hauptbuchs
  $effect(() => {
    if (buchKennung) return;
    untrack(async () => {
      await bibliothekLaden();
      const haupt = hauptbuch();
      if (haupt) gehe(lesenZiel(haupt.kennung, haupt.startseite), true);
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
    fehler = "";
    original = false;
    blatt = null;
    textwahl = null;
    bilder = null;
    filterText = "";
    void bibliothekLaden();
    try {
      const neu = await artikelHolen(b, p, signal);
      artikel = neu;
      navigation.titel = neu.titel;
      await tick();
      woerter = text?.innerText.split(/\s+/).length ?? 0;
      if (text) {
        // Sprache des Codes aus den Schlagwörtern (Frage und Antwort); sonst erkennt sie sich am Inhalt
        codeEinfaerben(text, spracheAus([...text.querySelectorAll(".schlagwoerter span")].map((e) => e.textContent ?? "")));
        kopierknoepfe(text);
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
      await tick();                                            // Markierungen der Notizen stehen
      zurStelle();
    } catch (f) {
      if (!signal.aborted) fehler = seitenFehler(f);
    } finally {
      if (!signal.aborted) laedt = false;
    }
  }

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
      const kopf = kasten.querySelector<HTMLElement>(".bkopf");
      if (kopf) kopf.append(knopf);
      else kasten.prepend(knopf);
    }
  }

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
  // `markiert`: Notizen, deren Markierung die Auswahl berührt (dann entfernt die Leiste, statt doppelt zu markieren)
  let textwahl = $state<{ stelle: Stelle; markiert: Notiz[]; x: number; y: number; unten: boolean } | null>(null);
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
      textwahl = { stelle, markiert, x: r.left + r.width / 2, y: unten ? r.bottom + LEISTE_ABSTAND_PX : r.top - LEISTE_ABSTAND_PX, unten };
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
    const { stelle } = textwahl;
    wahlBeenden();
    try {
      const n = artikelNotizen.find((x) => x.zitat === stelle.zitat && x.davor === stelle.davor)
        ?? await notieren({ buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild, ...stelle, text: "" });
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
                                      abschnitt: "", zitat: "", davor: "", text: "" } };
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

  const ORIGINAL = "/api/v1/inhalt/original/";

  /** Verweise in der Originalseite führen in die App: eine Seite desselben Buchs öffnet im Lesen (mit eigenem
   *  Baustein, wenn sie einer liest); Online-Verweise öffnen neu. Der Rahmen hat die Herkunft der App, aber keine
   *  Skripte; darum hört die App selbst auf seine Klicks. */
  // Am Telefon rollt der Inhalt der Schale, nicht der Rahmen: dort bekommt die Originalseite die Höhe ihres Inhalts
  // (beim Laden und nach jedem nachgeladenen Bild gemessen); am Rechner füllt sie die Fläche und rollt selbst
  let rahmenHoehe = $state(0);

  let rahmen = $state<HTMLIFrameElement>();

  $effect(() => {
    const z = zoom, doc = rahmen?.contentDocument;
    if (!doc?.documentElement) return;
    doc.documentElement.style.zoom = String(z);
    rahmenHoehe = doc.documentElement.scrollHeight;
  });

  function rahmenGeladen(e: Event) {
    const doc = (e.currentTarget as HTMLIFrameElement).contentDocument;
    const messen = () => (rahmenHoehe = doc?.documentElement.scrollHeight ?? 0);
    if (doc) doc.documentElement.style.zoom = String(zoom);
    messen();
    doc?.addEventListener("load", messen, true);          // Bilder laden nach; "load" steigt nicht auf, im Einfangen kommt es an
    doc?.addEventListener("click", (k) => {
      const a = (k.target as Element | null)?.closest("a");
      if (!a || k.ctrlKey || k.metaKey || k.shiftKey) return;
      const url = new URL(a.getAttribute("href") ?? "", doc.baseURI);
      if (url.origin !== location.origin || !url.pathname.startsWith(ORIGINAL)) return;
      k.preventDefault();
      const anker = decodeURIComponent(url.hash.slice(1));
      gehe(`lesen/${url.pathname.slice(ORIGINAL.length)}${anker ? "?" + new URLSearchParams({ anker }) : ""}`);
    });
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

<div class="inhalt-stufe" data-schrift="klein">
{#if fehler && !artikel}
  <div class="seiten-kopf"><h1>Artikel</h1></div>
  <div class="rollfeld"><div class="karte"><div class="fehlertext">{fehler}</div></div></div>
{:else if !artikel}
  <div class="laden">Lädt ...</div>
{:else}
  <div class="artikel-kopf">
    <div class="pfad"><i class="fa-solid fa-book"></i><b><Buchmarke kennung={artikel.buch} symbol={false} /></b><i class="fa-solid fa-chevron-right"></i>
      {#if artikel.rubrik}<span>{artikel.rubrik}</span><i class="fa-solid fa-chevron-right"></i>{/if}
      <span>{artikel.titel}</span></div>
    <h1 class:code-titel={artikel.titelart === "code"}>{artikel.titel}</h1>
    <div class="werkzeuge">
      <button class="knopf" class:an={!!eintrag} title={eintrag ? "Vom Merkzettel nehmen" : "Auf den Merkzettel"} onclick={merkenUmschalten}>
        <i class="fa-{eintrag ? 'solid' : 'regular'} fa-bookmark"></i><span class="wort">{eintrag ? "Gemerkt" : "Merken"}</span></button>
      <button class="knopf" title="Notiz zum ganzen Artikel; für eine Stelle den Text markieren" onclick={notizZumArtikel}>
        <i class="fa-regular fa-note-sticky"></i><span class="wort">Notiz</span>{#if artikelNotizen.length}<span class="zahl">{artikelNotizen.length}</span>{/if}</button>
      {#if buch}<ThemaWahl artikel={{ buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild }} buchName={buch.name} />{/if}
      {#if artikel.darstellung !== "original"}
        <button class="knopf" class:an={original} title="Die Seite so, wie sie im Buch steht" onclick={() => (original = !original)}>
          <i class="fa-solid fa-file-code"></i><span class="wort">Original</span></button>
      {/if}
      <button class="knopf still" title="Ein zufälliger Artikel aus diesem Buch" onclick={zufall}>
        <i class="fa-solid fa-dice"></i><span class="wort">Zufall</span></button>
      <div class="rechts">
        {#if fassungen && !zeigeOriginal}
          <Auswahl wert={meineFassung} symbol="fa-code-branch" titel="Meine Fassung, bleibt für dieses Buch eingestellt" onwahl={fassungWaehlen}
                   optionen={[{ wert: "", titel: "Alle Fassungen" },
                              ...fassungen.optionen.map((f) => ({ wert: f, titel: `Meine Fassung: ${fassungen!.produkt} ${f}` }))]} />
        {/if}
        {#if buch}<Lesegroesse buchName={buch.name} buchTitel={buch.titel} />{/if}
      </div>
    </div>
  </div>
  {#if fassungen && meineFassung && !zeigeOriginal}
    <div class="fundband fassung" class:warn={!gibtEsInFassung}>
      <i class="fa-solid {gibtEsInFassung ? 'fa-code-branch' : 'fa-triangle-exclamation'}"></i>
      <span>{#if gibtEsInFassung}Gefiltert auf <b>{fassungen.produkt} {meineFassung}</b>: Änderungen für spätere Fassungen sind blass, die Änderungen bis zu deiner sind markiert.
        {:else}<b>Diese Seite gibt es in {fassungen.produkt} {meineFassung} nicht.</b> Die Fassungen, in denen es sie gibt, nennt der Steckbrief.{/if}</span>
      <button class="knopf still" onclick={() => fassungWaehlen("")}><i class="fa-solid fa-xmark"></i>Filter aus</button>
    </div>
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
          <input type="search" bind:value={filterText} placeholder="In dieser Übersicht filtern" aria-label="In dieser Übersicht filtern" /></label>
        {#if filterText.trim()}
          <button class="knopf" onclick={() => suchen(filterText.trim(), artikel!.buch, true)}><i class="fa-solid fa-magnifying-glass"></i>Im ganzen Buch suchen</button>
          <span class="filter-stand">{gefiltert.zahl} von {gefiltert.gesamt}</span>
        {/if}
      </div>
      {#if filterText.trim() && !gefiltert.zahl}
        <p class="leer-hinweis uebersicht-leer">Nichts in dieser Übersicht passt zu "{filterText.trim()}". "Im ganzen Buch suchen" findet es auch in den Seiten selbst.</p>
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
  {:else if zeigeOriginal}
    <!-- ohne Skripte, mit Herkunft der App: Stile und Bilder laden mit dem Lesezugang, die Seite kann nichts in der App tun -->
    <iframe class="original" class:mit-inhalt={geraet.mobil} src={artikel.original} title="Originalseite: {artikel.titel}"
            sandbox="allow-same-origin allow-popups" style:height={geraet.mobil && rahmenHoehe ? `${rahmenHoehe}px` : undefined}
            bind:this={rahmen} onload={rahmenGeladen}></iframe>
  {:else}
    <div class="rollfeld" style="padding: 0" bind:this={rollfeld}>
      <div class="lesen" class:ohne-inhalt={!inhalt.length && !artikel.nachbarn.length} data-art={buch?.art} style:zoom={zoom}>
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
        <article class="artikel" bind:this={artikelEl}>
          {#if artikel.steckbrief}
            <aside class="steckbrief">
              <div class="steckbrief-kopf" class:code-titel={artikel.steckbrief.code}>{artikel.steckbrief.titel}</div>
              <!-- vom Baustein gesäubert: nur erlaubte Elemente und Attribute, Verweise auf Wege der App -->
              <div role="presentation" onclick={klick} onkeydown={() => {}}>{@html artikel.steckbrief.html}</div>
            </aside>
          {/if}
          <div class="artikel-text" lang={buch ? htmlSprache(buch.sprache) || undefined : undefined} bind:this={text} role="presentation"
               onclick={klick} onkeydown={() => {}}>{@html artikel.html}</div>
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
          <details class="ueber">
            <summary><i class="fa-solid fa-circle-info"></i>Über diesen Artikel<span>Quelle, Verweise</span></summary>
            <dl>
              <dt>Quelle</dt><dd>{buch ? bezeichnung(buch) : artikel.buch}{buch ? `, Stand ${datum(buch.stand)}` : ""}</dd>
              {#if buch?.beschreibung}<dt>Buch</dt><dd>{buch.beschreibung}</dd>{/if}
              <dt>Verweise</dt><dd>{artikel.verweise.intern} im Buch{artikel.verweise.ohne_ziel ? `, ${artikel.verweise.ohne_ziel} ohne Ziel im Buch (nur Text)` : ""}{artikel.verweise.koordinaten ? `, ${artikel.verweise.koordinaten} Orte` : ""}</dd>
              {#if artikel.online.length}
                <dt>Im Netz</dt>
                <dd><ul>{#each artikel.online as o}<li><a href={o} target="_blank" rel="noopener noreferrer">{o}</a></li>{/each}</ul></dd>
              {/if}
              <dt>Aufbereitet</dt><dd>Baustein {artikel.baustein === "enzyklopaedie" ? "Enzyklopädie" : artikel.baustein}</dd>
            </dl>
          </details>
        </article>
      </div>
    </div>
  {/if}
{/if}
{#if bibliothek.meldung && !artikel}<div class="fehlertext">{bibliothek.meldung}</div>{/if}
</div>

<svelte:document onselectionchange={auswahlGeaendert} />
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
    <button class:kopiert-ok={kopiert === "ja"} onclick={zitieren} title="Zitat mit Artikel, Abschnitt und Buch in die Zwischenablage">
      <i class="fa-solid {kopiert === 'ja' ? 'fa-check' : kopiert === 'nein' ? 'fa-triangle-exclamation' : 'fa-quote-right'}"></i>{kopiert === "ja" ? "Kopiert" : kopiert === "nein" ? "Geht nicht" : "Zitieren"}</button>
    <button onclick={() => { const z = textwahl!.stelle.zitat; textwahl = null; suchen(z.slice(0, 200)); }}><i class="fa-solid fa-magnifying-glass"></i>Suchen</button>
  </div>
{/if}
{#if bilder && artikel}
  <Leuchtkasten medien={bilder.medien} start={bilder.start} titel={`in ${artikel.titel}`} onzu={() => (bilder = null)} />
{/if}
{#if blatt}
  <NotizBlatt notiz={blatt.notiz} entwurf={blatt.entwurf} schreiben={blatt.schreiben} onzu={() => (blatt = null)} />
{/if}
