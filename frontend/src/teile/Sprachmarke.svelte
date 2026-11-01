<script lang="ts">
  // Sprache auf einen Blick: die Flagge je Sprache (mehrsprachig: Weltkugel), der Name beim Überfahren oder mit `name`
  // daneben. Eine Stelle für alle Seiten, das Wissen über Sprachen steht in lib/sprache.ts.
  import { sprachen } from "../lib/sprache";

  let { kuerzel, name = false }: { kuerzel: string; name?: boolean } = $props();

  const liste = $derived(sprachen(kuerzel));
</script>

{#if liste.length}
  <span class="sprachmarke" title={liste.map((s) => s.name).join(", ")}>
    {#each liste as s (s.name)}
      {#if s.flagge}<span class="fi fi-{s.flagge}" aria-hidden="true"></span>{:else}<i class="fa-solid fa-globe" aria-hidden="true"></i>{/if}
    {/each}
    {#if name}<span class="sprachname">{liste.map((s) => s.name).join(", ")}</span>{:else}<span class="nur-lesen">{liste.map((s) => s.name).join(", ")}</span>{/if}
  </span>
{/if}
