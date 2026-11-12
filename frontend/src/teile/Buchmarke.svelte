<script lang="ts">
  // Ein Buch in einer Zeile: Titel mit der Flagge seiner Sprache (statt "(Deutsch)" dahinter). Für Pfade, Listen und
  // Gruppenköpfe; ein Buch, das es nicht mehr gibt, steht mit seinem gemerkten Namen ohne Flagge. `flaggeVorn`: die
  // Flagge vor dem Titel, wo Titel untereinander stehen und umbrechen (Quellenliste der Suche, WIKI-103).
  import { buch as buchVon } from "../lib/bibliothek.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";

  let { kennung, ersatz = "", symbol = true, flaggeVorn = false }: { kennung: string; ersatz?: string; symbol?: boolean;
        flaggeVorn?: boolean } = $props();

  const b = $derived(kennung ? buchVon(kennung) : undefined);
</script>

<span class="buchmarke">
  {#if symbol}<i class="fa-solid fa-book" aria-hidden="true"></i>{/if}
  {#if b && flaggeVorn}<Sprachmarke kuerzel={b.sprache} />{/if}
  <span class="buchtitel">{b?.titel ?? (ersatz || kennung)}</span>
  {#if b && !flaggeVorn}<Sprachmarke kuerzel={b.sprache} />{/if}
</span>
