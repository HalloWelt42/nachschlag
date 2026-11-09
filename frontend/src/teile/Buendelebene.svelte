<script lang="ts">
  // Ein Bündel als eigene Ebene in einer Bücherliste (WIKI-83, etwa FreeCodeCamp): der Kopf öffnet das Gesamtbuch mit
  // allen Themen (Entscheidung des Nutzers), darunter jedes Thema als Kachel. Steht über die volle Breite des Rasters.
  import { datum, zahl } from "../lib/bibliothek.svelte";
  import { themaTitel } from "../lib/buendel";
  import type { Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";
  import Buchkachel from "./Buchkachel.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";

  let { titel, gesamt, themen }: { titel: string; gesamt: Buch | null; themen: Buch[] } = $props();
</script>

<section class="buendel-ebene" aria-label={`Bündel ${titel}`}>
  {#if gesamt}
    <button class="buendel-kopf" title="Alle Themen zusammen öffnen" onclick={() => lesen(gesamt.kennung, gesamt.startseite)}>
      <i class="fa-solid fa-layer-group"></i><b>{titel}</b>
      <span class="buendel-angabe">{themen.length} Themen · {zahl(gesamt.artikel)} Aufgaben · Stand {datum(gesamt.stand)}</span>
      <Sprachmarke kuerzel={gesamt.sprache} /><span class="buendel-oeffnen">alle öffnen<i class="fa-solid fa-arrow-right"></i></span>
    </button>
  {:else}
    <div class="buendel-kopf"><i class="fa-solid fa-layer-group"></i><b>{titel}</b><span class="buendel-angabe">{themen.length} Themen</span></div>
  {/if}
  <div class="buecher">
    {#each themen as t (t.kennung)}<Buchkachel buch={t} titel={themaTitel(t)} />{/each}
  </div>
</section>
