<script lang="ts">
  // Ein Buch in einer Zeile: Titel mit der Flagge seiner Sprache (statt "(Deutsch)" dahinter). Für Pfade, Listen und
  // Gruppenköpfe; ein Buch, das es nicht mehr gibt, steht mit seinem gemerkten Namen ohne Flagge.
  import { buch as buchVon } from "../lib/bibliothek.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";

  let { kennung, ersatz = "", symbol = true }: { kennung: string; ersatz?: string; symbol?: boolean } = $props();

  const b = $derived(kennung ? buchVon(kennung) : undefined);
</script>

<span class="buchmarke">
  {#if symbol}<i class="fa-solid fa-book" aria-hidden="true"></i>{/if}
  <span class="buchtitel">{b?.titel ?? (ersatz || kennung)}</span>
  {#if b}<Sprachmarke kuerzel={b.sprache} />{/if}
</span>
