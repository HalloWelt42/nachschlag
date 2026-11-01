<script lang="ts">
  // Artikel lesen, Variante A (Entwurf mockups/artikel-a.html): ruhige Lesespalte, Inhalt links mitlaufend mit
  // Lesestand, Steckbrief rechts im Text. Weg: /lesen/<buch>/<pfad>?frage=&abschnitt=&anker=. Bücher ohne eigenes
  // Lesedesign zeigen ihre Seite unverändert (Originalansicht). Verweise im Text bleiben in der App.
  import { gehe, navigation, seitenFehler } from "appkern-oberflaeche";
  import { tick, untrack } from "svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, buch as buchVon, datum, hauptbuch } from "../lib/bibliothek.svelte";
  import { artikelHolen, zufallHolen } from "../lib/schnittstelle";
  import type { Artikel } from "../lib/typen";
  import { lesen, lesenZiel, suchen, verweisZiel } from "../lib/ziele";

  const WOERTER_JE_MINUTE = 200;
  const MITLAUF_ABSTAND_PX = 90;          // eine Überschrift gilt als erreicht, sobald sie so nah am oberen Rand steht
  const LESEGROESSE = "nachschlag.lesegroesse";

  let artikel = $state.raw<Artikel | null>(null);   // nur lesen, ohne Proxy
  let fehler = $state("");
  let laedt = $state(false);
  let original = $state(false);
  let rollfeld = $state<HTMLElement>();
  let text = $state<HTMLElement>();
  let aktiv = $state("");
  let anteil = $state(0);
  let woerter = $state(0);
  let gross = $state(lesegroesseLesen());

  const buchKennung = $derived(navigation.teile[0] ?? "");
  const pfad = $derived(navigation.teile.slice(1).join("/"));
  const zusatz = $derived(new URLSearchParams(navigation.suche));
  const frage = $derived(zusatz.get("frage") ?? "");
  const abschnitt = $derived(zusatz.get("abschnitt") ?? "");
  const weg = $derived(zusatz.get("weg") ?? "");
  const anker = $derived(zusatz.get("anker") ?? "");
  const buch = $derived(buchVon(buchKennung));
  const zeigeOriginal = $derived(!!artikel && (artikel.darstellung === "original" || original));
  const restMinuten = $derived(Math.max(1, Math.round((woerter * (1 - anteil)) / WOERTER_JE_MINUTE)));

  function lesegroesseLesen(): boolean {
    try {
      return localStorage.getItem(LESEGROESSE) === "gross";
    } catch {
      return false;
    }
  }

  $effect(() => {
    if (gross) document.documentElement.dataset.lesegroesse = "gross";
    else delete document.documentElement.dataset.lesegroesse;
    try {
      localStorage.setItem(LESEGROESSE, gross ? "gross" : "normal");
    } catch {
      /* ohne Speicher im Browser gilt die Wahl nur bis zum Neuladen */
    }
  });

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
    void bibliothekLaden();
    try {
      const neu = await artikelHolen(b, p, signal);
      artikel = neu;
      navigation.titel = neu.titel;
      await tick();
      woerter = text?.innerText.split(/\s+/).length ?? 0;
      if (text) kopierknoepfe(text);
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
    if (untrack(() => artikel && !laedt)) untrack(zurStelle);
  });

  function ueberschrift(titel: string): HTMLElement | null {
    const gesucht = titel.trim().toLowerCase();
    return [...(text?.querySelectorAll<HTMLElement>("h2, h3, h4") ?? [])].find((h) => h.innerText.trim().toLowerCase() === gesucht) ?? null;
  }

  /** Springt zu Anker (aus dem Weg oder der Weiterleitung) oder zur Fundstelle aus der Suche; sonst nach oben. */
  function zurStelle() {
    if (!rollfeld || !text) return;
    text.querySelectorAll(".fundstelle").forEach((e) => e.classList.remove("fundstelle"));
    const ziel = anker || artikel?.anker || "";
    let el: HTMLElement | null = ziel ? text.querySelector<HTMLElement>(`#${CSS.escape(ziel)}`) : null;
    if (!el && abschnitt) {
      const h = ueberschrift(abschnitt);
      const absatz = h?.nextElementSibling;
      if (absatz instanceof HTMLElement && absatz.tagName === "P") absatz.classList.add("fundstelle");
      el = h;
    }
    if (el) el.scrollIntoView({ block: "start" });
    else rollfeld.scrollTop = 0;
    mitlaufen();
  }

  function mitlaufen() {
    if (!rollfeld || !text || !artikel) return;
    // Lage der Überschriften im sichtbaren Rollfeld (offsetTop bezöge sich auf das nächste positionierte Element)
    const oben = rollfeld.getBoundingClientRect().top + MITLAUF_ABSTAND_PX;
    let jetzt = "";
    for (const a of artikel.abschnitte) {
      const h = text.querySelector<HTMLElement>(`#${CSS.escape(a.anker)}`);
      if (h && h.getBoundingClientRect().top <= oben) jetzt = a.anker;
    }
    aktiv = jetzt;
    const weit = rollfeld.scrollHeight - rollfeld.clientHeight;
    anteil = weit > 0 ? Math.min(1, rollfeld.scrollTop / weit) : 1;
  }

  function springen(ziel: string) {
    gehe(lesenZiel(buchKennung, pfad, { frage, abschnitt, weg }, ziel), true);
  }

  /** Verweise im Text bleiben in der App; Orte und Online-Verweise gibt es im Text nicht (stehen in "Über"). */
  function klick(e: MouseEvent) {
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

  /** In die Zwischenablage; ohne sicheren Zusammenhang (http im Heimnetz) über ein Textfeld im Klick. */
  async function kopieren(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const feld = document.createElement("textarea");
      feld.value = text;
      document.body.append(feld);
      feld.select();
      document.execCommand("copy");
      feld.remove();
    }
  }

  /** Ein Eintrag ist ein Name aus dem Code (Funktion, Klasse, Methode), wenn er Zeichen aus dem Code trägt, klein
   *  beginnt (basename) oder Binnengroßbuchstaben hat (ArrayObject); nur dann steht er in der Schrift des Editors.
   *  Kapitelnamen ("Getting Started", "Types") bleiben Text. */
  function istCode(titel: string): boolean {
    const name = titel.replace(/\s*\((class|interface|enum|trait)\)$/, "");
    if (/\s/.test(name)) return false;
    return /[_$\\]|::|->|\(\)$/.test(name) || /^[a-z]/.test(name) || /[a-z][A-Z]/.test(name);
  }

  const ORIGINAL = "/api/v1/inhalt/original/";

  /** Verweise in der Originalseite führen in die App: eine Seite desselben Buchs öffnet im Lesen (mit eigenem
   *  Baustein, wenn sie einer liest); Online-Verweise öffnen neu. Der Rahmen hat die Herkunft der App, aber keine
   *  Skripte; darum hört die App selbst auf seine Klicks. */
  function rahmenGeladen(e: Event) {
    const doc = (e.currentTarget as HTMLIFrameElement).contentDocument;
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
    <div class="pfad"><i class="fa-solid fa-book"></i><b>{buch ? bezeichnung(buch) : artikel.buch}</b><i class="fa-solid fa-chevron-right"></i>
      {#if artikel.rubrik}<span>{artikel.rubrik}</span><i class="fa-solid fa-chevron-right"></i>{/if}
      <span>{artikel.titel}</span></div>
    <h1 class:code-titel={artikel.titelart === "code"}>{artikel.titel}</h1>
    <div class="werkzeuge">
      {#if artikel.darstellung !== "original"}
        <button class="knopf" class:an={original} title="Die Seite so, wie sie im Buch steht" onclick={() => (original = !original)}>
          <i class="fa-solid fa-file-code"></i><span class="wort">Original</span></button>
      {/if}
      <button class="knopf still" title="Ein zufälliger Artikel aus diesem Buch" onclick={zufall}>
        <i class="fa-solid fa-dice"></i><span class="wort">Zufall</span></button>
      <div class="rechts">
        {#if !zeigeOriginal}
          <button class="rund" class:an={gross} title={gross ? "Lesegröße normal" : "Größer lesen"} onclick={() => (gross = !gross)}>
            <i class="fa-solid fa-text-height"></i></button>
        {/if}
      </div>
    </div>
  </div>
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
    <div class="rollfeld" style="padding: 0">
      {#if artikel.gruppen.length}
        <!-- Handbuch: die Rubriken der Gliederung mit ihren Seiten -->
        <div class="rubriken">
          {#each artikel.gruppen as g, gi (gi)}
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
      <div class="uebersicht">
        {#each artikel.kacheln as k, ki (ki)}
          <a class="leskarte" href={"/" + lesenZiel(artikel.buch, k.pfad)} onclick={(e) => { e.preventDefault(); lesen(artikel!.buch, k.pfad); }}>
            <span class="bildflaeche">
              {#if k.bild}<img src={k.bild} alt="" loading="lazy" />{:else}<i class="fa-solid fa-file-lines"></i>{/if}
            </span>
            <span class="koerper"><span class="t">{k.titel}</span></span>
          </a>
        {/each}
      </div>
    </div>
  {:else if zeigeOriginal}
    <!-- ohne Skripte, mit Herkunft der App: Stile und Bilder laden mit dem Lesezugang, die Seite kann nichts in der App tun -->
    <iframe class="original" src={artikel.original} title="Originalseite: {artikel.titel}" sandbox="allow-same-origin allow-popups"
            onload={rahmenGeladen}></iframe>
  {:else}
    <div class="rollfeld" style="padding: 0" bind:this={rollfeld} onscroll={mitlaufen}>
      <div class="lesen" class:ohne-inhalt={!inhalt.length && !artikel.nachbarn.length}>
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
        <article class="artikel">
          {#if artikel.steckbrief}
            <aside class="steckbrief">
              <div class="steckbrief-kopf" class:code-titel={artikel.steckbrief.code}>{artikel.steckbrief.titel}</div>
              <!-- vom Baustein gesäubert: nur erlaubte Elemente und Attribute, Verweise auf Wege der App -->
              <div role="presentation" onclick={klick} onkeydown={() => {}}>{@html artikel.steckbrief.html}</div>
            </aside>
          {/if}
          <div class="artikel-text" bind:this={text} role="presentation" onclick={klick} onkeydown={() => {}}>{@html artikel.html}</div>
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
