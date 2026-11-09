<script lang="ts">
  // Eine Aufgabe eines Übungsbuchs (freeCodeCamp, WIKI-66): oben Kurs, Block und Stelle im Block, dann Beschreibung und
  // Anleitung. Der Kern ist das Selbertesten wie in der Original-Anwendung des Buchs: den Code im Editor selbst schreiben
  // (er beginnt mit dem Startcode), "Tests ausführen" (Strg + Eingabe) lässt jeden Prüfpunkt gegen ihn laufen, und
  // jeder Prüfpunkt zeigt, ob er erfüllt ist; die Ausgabe des eigenen Codes steht darunter. Der Editor ist der des
  // Hausstils (appkern-oberflaeche/code, wie beim Ausprobieren in den Handbüchern). Breite Fenster teilen die Seite (Wunsch
  // des Nutzers): links die Aufgabe, rechts Code, Prüfpunkte und Ergebnis, jede Seite rollt für sich; schmale Fenster
  // zeigen beides untereinander in derselben Reihenfolge (Aufgabe, Code, Prüfpunkte). Sind alle erfüllt, gilt die
  // Aufgabe als gelöst. Die Lösung bleibt hinter einem Knopf (erst selbst probieren). Bringt das Buch keinen Testläufer
  // mit, stehen Prüfpunkte und Startcode nur zum Lesen da. Unten die Nachbarn im Block; Pfeiltasten blättern.
  import { kopieren } from "appkern-oberflaeche";
  import { EditorBereich } from "appkern-oberflaeche/code";
  import { tick } from "svelte";
  import { codeEinfaerben } from "../lib/einfaerben";
  import { pruefen, type Lauf } from "../lib/pruefen";
  import type { Artikel, Uebungscode } from "../lib/typen";
  import { codeMerken, eigenerCode, geloestMerken } from "../lib/uebungsstand";
  import { lesen, lesenZiel } from "../lib/ziele";

  let { artikel }: { artikel: Artikel } = $props();
  const u = $derived(artikel.uebung!);
  /** Sprache eines Codeblocks für die Einfärbung (die Quelle schreibt js, html, css, py ...) */
  const SPRACHE: Record<string, string> = { js: "javascript", jsx: "javascript", ts: "typescript", html: "xml", css: "css",
                                            py: "python", python: "python", sql: "sql", bash: "bash", sh: "bash", json: "json" };
  const sprache = (c: Uebungscode | undefined) => SPRACHE[c?.sprache ?? ""] ?? "javascript";

  let feld = $state<HTMLElement>();
  let loesungOffen = $state(false);
  let kopiert = $state(-1);

  // Selbertesten: nur mit Testläufer des Buchs, Prüfpunkten mit Test und einem Startcode
  const tests = $derived(u.hinweise.filter((h) => h.test));
  const startcode = $derived(u.startcode[0]?.code ?? "");
  const selbertesten = $derived(!!u.pruefer && tests.length > 0 && u.startcode.length > 0);
  let code = $state("");
  let geladenFuer = $state("");                     // für welche Aufgabe `code` gilt (erst dann wird gemerkt)
  let lauf = $state<Lauf | null>(null);
  const KUERZEL = /Mac|iPhone|iPad/.test(navigator.userAgent) ? "Cmd Enter" : "Strg Enter";
  let laeuft = $state(false);
  const erfuellt = $derived(lauf ? lauf.punkte.filter((p) => p.bestanden).length : 0);
  const geloest = $derived(!!lauf && !lauf.fehler && lauf.punkte.length === tests.length && erfuellt === tests.length);
  /** Ergebnis je Prüfpunkt (in der Reihenfolge aller Hinweise; Hinweise ohne Test haben keins) */
  const ergebnis = $derived.by(() => {
    let i = 0;
    return u.hinweise.map((h) => (h.test && lauf ? lauf.punkte[i++] ?? null : null));
  });

  // nach jedem Wechsel der Aufgabe: Lösung wieder zu, eigener Code oder Startcode, kein altes Ergebnis, oben anfangen
  $effect(() => {
    void artikel.pfad;
    loesungOffen = false;
    code = eigenerCode(artikel.buch, artikel.pfad) ?? startcode;
    geladenFuer = artikel.pfad;
    lauf = null;
    void tick().then(() => {
      if (!feld) return;
      for (const el of feld.querySelectorAll<HTMLElement>("[data-sprache-hinweis]")) codeEinfaerben(el, el.dataset.spracheHinweis);
      for (const r of [feld, ...feld.querySelectorAll<HTMLElement>(".ueb-links, .ueb-rechts")]) r.scrollTop = 0;
    });
  });
  $effect(() => {
    if (loesungOffen) void tick().then(() => feld && codeEinfaerben(feld.querySelector<HTMLElement>(".ueb-loesung") ?? feld, sprache(u.loesungen[0])));
  });

  async function codeKopieren(i: number, text: string) {
    await kopieren(text);
    kopiert = i;
    setTimeout(() => (kopiert = -1), 1500);
  }

  async function testen() {
    if (laeuft || !selbertesten) return;
    laeuft = true;
    const pfad = artikel.pfad;
    try {
      const ergebnis = await pruefen(u.pruefer, u.vorher, code, u.nachher, tests.map((h) => h.test));
      if (pfad !== artikel.pfad) return;              // inzwischen eine andere Aufgabe
      lauf = ergebnis;
      if (!ergebnis.fehler && ergebnis.punkte.length && ergebnis.punkte.every((p) => p.bestanden)) geloestMerken(artikel.buch, pfad);
    } finally {
      laeuft = false;
    }
  }

  function zuruecksetzen() {
    code = startcode;
    lauf = null;
  }

  // der eigene Code bleibt im Browser, sobald er zur geladenen Aufgabe gehört
  $effect(() => {
    if (geladenFuer === artikel.pfad) codeMerken(artikel.buch, artikel.pfad, code, startcode);
  });

  /** Tests mit Strg oder Cmd und Enter: vor dem Editor abgefangen, der damit sonst eine Zeile einfügt */
  function tasteVorab(e: KeyboardEvent) {
    if (e.key !== "Enter" || !(e.ctrlKey || e.metaKey) || !(e.target as HTMLElement)?.closest?.(".ueb-editor")) return;
    e.preventDefault();
    e.stopPropagation();
    // erst wenn der Editor die letzte Eingabe übernommen hat (er liest sie gleich nach dem Ereignis), sonst liefe der
    // Test mit dem Stand davor
    setTimeout(() => void testen(), 0);
  }

  function taste(e: KeyboardEvent) {
    if ((e.target as HTMLElement)?.closest("input, textarea, [contenteditable]") || e.metaKey || e.ctrlKey || e.altKey) return;
    const ziel = e.key === "ArrowRight" ? u.naechste : e.key === "ArrowLeft" ? u.vorige : null;
    if (!ziel) return;
    e.preventDefault();
    lesen(artikel.buch, ziel.pfad);
  }
  const ziel = (pfad: string) => "/" + lesenZiel(artikel.buch, pfad);
  function folgen(e: MouseEvent, pfad: string) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    lesen(artikel.buch, pfad);
  }
</script>

<svelte:window onkeydowncapture={tasteVorab} onkeydown={taste} />

<div class="rollfeld" style="padding: 0" bind:this={feld}>
  <article class="ueb-seite artikel-text" class:ueb-geteilt={selbertesten}>
   <div class="ueb-links">
    <nav class="ueb-ort" aria-label="Einordnung">
      <a href={ziel("index.html")} onclick={(e) => folgen(e, "index.html")}><i class="fa-solid fa-graduation-cap"></i>{u.kurs_titel}</a>
      <i class="fa-solid fa-chevron-right"></i><span>{u.block_titel}</span>
      {#if u.nr}<span class="ueb-stelle">Aufgabe {u.nr} von {u.anzahl}</span>{/if}
    </nav>

    {#if u.beschreibung}
      <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert -->
      <section class="ueb-text" data-sprache-hinweis={sprache(u.startcode[0])}>{@html u.beschreibung}</section>
    {/if}
    {#if u.anleitung}
      <section class="ueb-abschnitt">
        <h2><i class="fa-solid fa-list-ol"></i>Anleitung</h2>
        <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert -->
        <div class="ueb-text" data-sprache-hinweis={sprache(u.startcode[0])}>{@html u.anleitung}</div>
      </section>
    {/if}

   </div>
   <div class="ueb-rechts">
    {#if selbertesten}
      <section class="ueb-abschnitt">
        <h2><i class="fa-solid fa-code"></i>Dein Code
          <button class="knopf still ueb-kopieren" onclick={() => codeKopieren(0, code)}>
            <i class="fa-{kopiert === 0 ? 'solid fa-check' : 'regular fa-copy'}"></i>Kopieren</button></h2>
        <div class="ueb-editor">
          <div class="ueb-editor-reiter"><span class="aktiv"><i class="fa-brands fa-js" aria-hidden="true"></i>loesung.js</span>
            {#if code !== startcode}<span class="geaendert">geändert</span>{/if}</div>
          <div class="ueb-editor-code">{#key artikel.pfad}<EditorBereich sprache="javascript" bind:code />{/key}</div>
        </div>
        <div class="ueb-zeile">
          <button class="knopf" onclick={testen} disabled={laeuft} title={KUERZEL}>
            <i class="fa-solid {laeuft ? 'fa-spinner fa-spin' : 'fa-play'}"></i>Tests ausführen</button>
          <button class="knopf still" onclick={zuruecksetzen} disabled={laeuft || code === startcode} title="Zurück zum Startcode">
            <i class="fa-solid fa-rotate-left"></i>Zurücksetzen</button>
          {#if lauf && !lauf.fehler}
            <span class="ueb-stand" class:ueb-geloest={geloest} role="status">
              {#if geloest}<i class="fa-solid fa-circle-check"></i>Alle Prüfpunkte erfüllt, Aufgabe gelöst
              {:else}<i class="fa-solid fa-circle-xmark"></i>{erfuellt} von {tests.length} Prüfpunkten erfüllt{/if}</span>
          {:else if !lauf}<span class="ueb-leise"><kbd>{KUERZEL}</kbd></span>{/if}
        </div>
        {#if lauf?.fehler}<p class="ueb-meldung" role="alert"><i class="fa-solid fa-triangle-exclamation"></i>{lauf.fehler}</p>{/if}
        {#if lauf?.ausgabe.length}
          <div class="ueb-ausgabe" aria-label="Ausgabe"><span class="ueb-leise">Ausgabe</span><pre>{lauf.ausgabe.join("\n")}</pre></div>
        {/if}
      </section>
    {/if}

    {#if u.hinweise.length}
      <section class="ueb-abschnitt">
        <h2><i class="fa-solid fa-circle-check"></i>Prüfpunkte</h2>
        <ol class="ueb-pruefpunkte" class:mit-stand={selbertesten}>
          {#each u.hinweise as p, i (i)}
            {@const e = ergebnis[i]}
            <li class:ueb-ok={e?.bestanden} class:ueb-nein={e && !e.bestanden}>
              {#if selbertesten && p.test}
                <i class="ueb-marke fa-{e ? (e.bestanden ? 'solid fa-circle-check' : 'solid fa-circle-xmark') : 'regular fa-circle'}"
                   aria-label={e ? (e.bestanden ? "erfüllt" : "nicht erfüllt") : "noch nicht geprüft"}></i>
              {/if}
              <div class="ueb-punkt">
                <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert -->
                <div class="ueb-text">{@html p.html}</div>
                {#if e && !e.bestanden && e.meldung}<p class="ueb-leise ueb-grund">{e.meldung}</p>{/if}
                {#if p.test}
                  <details class="ueb-test"><summary>Test ansehen</summary>
                    <div data-sprache-hinweis="javascript"><pre><code>{p.test}</code></pre></div></details>
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      </section>
    {/if}

    {#each u.startcode as c, i (i)}
      {#if !selbertesten || i > 0}
        <section class="ueb-abschnitt">
          <h2><i class="fa-solid fa-code"></i>Startcode{#if u.startcode.length > 1} {i + 1}{/if}
            <button class="knopf still ueb-kopieren" onclick={() => codeKopieren(i + 1, c.code)}>
              <i class="fa-{kopiert === i + 1 ? 'solid fa-check' : 'regular fa-copy'}"></i>Kopieren</button></h2>
          <div class="ueb-code" data-sprache-hinweis={sprache(c)}><pre><code>{c.code}</code></pre></div>
        </section>
      {/if}
    {/each}

    {#if u.loesungen.length}
      <section class="ueb-abschnitt">
        {#if loesungOffen}
          <h2><i class="fa-solid fa-lightbulb"></i>Lösung
            <button class="knopf still ueb-kopieren" onclick={() => (loesungOffen = false)}><i class="fa-solid fa-eye-slash"></i>Verbergen</button></h2>
          <div class="ueb-loesung">
            {#each u.loesungen as c, i (i)}<div class="ueb-code"><pre><code>{c.code}</code></pre></div>{/each}
          </div>
        {:else}
          <div class="ueb-zeile"><button class="knopf" onclick={() => (loesungOffen = true)}><i class="fa-solid fa-lightbulb"></i>Lösung zeigen</button>
            <span class="ueb-leise">erst selbst probieren</span></div>
        {/if}
      </section>
    {/if}

    <nav class="ueb-nachbarn" aria-label="Aufgaben im Block">
      {#if u.vorige}<a class="knopf still" href={ziel(u.vorige.pfad)} onclick={(e) => folgen(e, u.vorige!.pfad)} title="Vorige (Pfeil links)">
        <i class="fa-solid fa-arrow-left"></i><span>{u.vorige.titel}</span></a>{:else}<span></span>{/if}
      {#if u.naechste}<a class="knopf ueb-weiter" href={ziel(u.naechste.pfad)} onclick={(e) => folgen(e, u.naechste!.pfad)} title="Nächste (Pfeil rechts)">
        <span>{u.naechste.titel}</span><i class="fa-solid fa-arrow-right"></i></a>{/if}
    </nav>
   </div>
  </article>
</div>
