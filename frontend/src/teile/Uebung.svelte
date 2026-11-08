<script lang="ts">
  // Eine Aufgabe eines Übungsbuchs (freeCodeCamp, WIKI-66): oben Kurs, Block und Stelle im Block, dann Beschreibung und
  // Anleitung, die Prüfpunkte (was erfüllt sein muss, der Test dazu aufklappbar), der Startcode zum Kopieren und die
  // Lösung hinter einem Knopf (erst selbst probieren). Unten die Nachbarn im Block; Pfeiltasten blättern.
  import { kopieren } from "appkern-oberflaeche";
  import { tick } from "svelte";
  import { codeEinfaerben } from "../lib/einfaerben";
  import type { Artikel, Uebungscode } from "../lib/typen";
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

  // nach jedem Wechsel der Aufgabe: Lösung wieder zu, Code eingefärbt, oben anfangen
  $effect(() => {
    void artikel.pfad;
    loesungOffen = false;
    void tick().then(() => {
      if (!feld) return;
      for (const el of feld.querySelectorAll<HTMLElement>("[data-sprache-hinweis]")) codeEinfaerben(el, el.dataset.spracheHinweis);
      feld.scrollTop = 0;
    });
  });
  $effect(() => {
    if (loesungOffen) void tick().then(() => feld && codeEinfaerben(feld.querySelector<HTMLElement>(".ueb-loesung") ?? feld, sprache(u.loesungen[0])));
  });

  async function codeKopieren(i: number, code: string) {
    await kopieren(code);
    kopiert = i;
    setTimeout(() => (kopiert = -1), 1500);
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

<svelte:window onkeydown={taste} />

<div class="rollfeld" style="padding: 0" bind:this={feld}>
  <article class="ueb-seite artikel-text">
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

    {#if u.hinweise.length}
      <section class="ueb-abschnitt">
        <h2><i class="fa-solid fa-circle-check"></i>Prüfpunkte</h2>
        <ol class="ueb-pruefpunkte">
          {#each u.hinweise as p, i (i)}
            <li>
              <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert -->
              <div class="ueb-text">{@html p.html}</div>
              {#if p.test}
                <details class="ueb-test"><summary>Test ansehen</summary>
                  <div data-sprache-hinweis="javascript"><pre><code>{p.test}</code></pre></div></details>
              {/if}
            </li>
          {/each}
        </ol>
      </section>
    {/if}

    {#each u.startcode as c, i (i)}
      <section class="ueb-abschnitt">
        <h2><i class="fa-solid fa-code"></i>Startcode{#if u.startcode.length > 1} {i + 1}{/if}
          <button class="knopf still ueb-kopieren" onclick={() => codeKopieren(i, c.code)}>
            <i class="fa-{kopiert === i ? 'solid fa-check' : 'regular fa-copy'}"></i>Kopieren</button></h2>
        <div class="ueb-code" data-sprache-hinweis={sprache(c)}><pre><code>{c.code}</code></pre></div>
      </section>
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
  </article>
</div>
