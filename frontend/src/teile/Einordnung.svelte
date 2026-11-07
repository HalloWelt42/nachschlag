<script lang="ts">
  // Einordnung einer Seite eines Anleitungsbuchs im Gerätebaum (WIKI-64): der Weg von der Startseite über die Kategorien
  // zum Gerät, bei einer Anleitung mit ihrem Bauteil. Dazu der Sprung in die Suche dieses Asts (Anleitungen finden mit
  // gewähltem Gerät). Ohne eigenen Index steht nichts da (die Einordnung kommt aus ihm).
  import { gehe } from "appkern-oberflaeche";
  import { bibliothek } from "../lib/bibliothek.svelte";
  import { einordnungHolen } from "../lib/schnittstelle";
  import type { Einordnung } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";

  let { buch, pfad, geraet = false }: { buch: string; pfad: string; geraet?: boolean } = $props();

  let einordnung = $state.raw<Einordnung | null>(null);
  $effect(() => {
    const [b, p] = [buch, pfad];
    einordnung = null;
    einordnungHolen(b, p).then((e) => { if (b === buch && p === pfad) einordnung = e; }).catch(() => {});
  });

  const start = $derived(bibliothek.buecher.find((b) => b.kennung === buch)?.startseite ?? "");
  /** Der Ast, in dem gesucht wird: das Gerät selbst, bei einer Anleitung ihr Gerät */
  const ast = $derived(geraet ? pfad : (einordnung?.weg.at(-1)?.pfad ?? ""));
  const suche = $derived(start && ast ? lesenZiel(buch, start) + "?" + new URLSearchParams({ geraet: ast, art: "anleitung" }) : "");
  const ziel = (p: string) => "/" + lesenZiel(buch, p);
  function folgen(e: MouseEvent, weiter: () => void) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    weiter();
  }
</script>

{#if einordnung && einordnung.weg.length}
  <nav class="anl-einordnung" aria-label="Einordnung">
    {#each einordnung.weg as s, i (s.pfad)}
      {#if i}<i class="fa-solid fa-chevron-right"></i>{/if}
      <a class="knopf still" href={ziel(s.pfad)} onclick={(e) => folgen(e, () => lesen(buch, s.pfad))}>{#if !i}<i class="fa-solid fa-sitemap"></i>{/if}{s.titel}</a>
    {/each}
    {#if einordnung.bauteil}<i class="fa-solid fa-chevron-right"></i><span class="faehigkeit"><i class="fa-solid fa-microchip"></i>{einordnung.bauteil}</span>{/if}
    {#if suche}
      <a class="knopf still" href={"/" + suche} onclick={(e) => folgen(e, () => gehe(suche))}><i class="fa-solid fa-magnifying-glass"></i>Anleitungen hier finden</a>
    {/if}
  </nav>
{/if}
