<script lang="ts">
  // Ein Zufallsfund als Bildkarte (WIKI-89, Entwurf mockups/kacheln/bildkarte.html): das erste Bild des Artikels oben,
  // das Symbol des Buchs oben links darauf; ohne Bild die Farbe der Art mit dem Anfangsbuchstaben. Auszug in drei
  // Zeilen, unten das Buch und die Knöpfe.
  import { ART_FARBE } from "../lib/arten";
  import type { Buch } from "../lib/typen";
  import Buchzeichen from "./Buchzeichen.svelte";
  import Kachel from "./Kachel.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";

  export interface Fund { pfad: string; titel: string; einleitung: string; bild: string }

  let { buch: b, fund: f, lesen, neu }: { buch: Buch; fund: Fund | undefined; lesen: () => void; neu: () => void } = $props();
</script>

<Kachel art="hoch" class="fundkarte" bild={f?.bild ?? ""} titel={f?.titel ?? "sucht ..."} style="--artfarbe: {ART_FARBE[b.art]}">
  {#snippet zeichen()}<span class="fund-ohne-bild"><span class="wasser">{(f?.titel ?? b.titel).trim().charAt(0)}</span></span>{/snippet}
  {#snippet marke()}<Buchzeichen buch={b} />{/snippet}
  {#snippet ecke()}<Sprachmarke kuerzel={b.sprache} />{/snippet}
  {#if f?.einleitung}<span class="auszug">{f.einleitung}</span>{/if}
  {#snippet fuss()}
    <span class="fund-fuss">
      <span class="fund-buch">{b.titel}</span>
      <button class="rund" title="Lesen" aria-label="Lesen" disabled={!f} onclick={lesen}><i class="fa-solid fa-book-open"></i></button>
      <button class="rund" title="Neuer Zufall aus diesem Buch" aria-label="Neuer Zufall" onclick={neu}><i class="fa-solid fa-rotate"></i></button>
    </span>
  {/snippet}
</Kachel>
