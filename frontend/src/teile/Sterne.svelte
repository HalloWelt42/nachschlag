<script lang="ts">
  // Eigene Bewertung als Sterne (WIKI-71): 1 bis 5, ein Tipp auf den gewählten nimmt sie weg. `klein`: nur anzeigen.
  let { sterne = 0, klein = false, onwahl }: { sterne?: number; klein?: boolean; onwahl?: (n: number) => void } = $props();
  const NAMEN = ["", "schlecht", "mäßig", "in Ordnung", "gut", "sehr gut"];
</script>

{#if klein}
  {#if sterne}<span class="sterne-klein" title="Meine Bewertung: {NAMEN[sterne]}"><i class="fa-solid fa-star"></i>{sterne}</span>{/if}
{:else}
  <span class="sterne" role="radiogroup" aria-label="Meine Bewertung">
    {#each [1, 2, 3, 4, 5] as n (n)}
      <button role="radio" aria-checked={sterne === n} class:an={n <= sterne} title={sterne === n ? "Bewertung wegnehmen" : `${n}: ${NAMEN[n]}`}
              onclick={() => onwahl?.(sterne === n ? 0 : n)}><i class="fa-{n <= sterne ? 'solid' : 'regular'} fa-star"></i></button>
    {/each}
    {#if sterne}<span class="sterne-name">{NAMEN[sterne]}</span>{/if}
  </span>
{/if}
