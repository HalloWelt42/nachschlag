<script lang="ts">
  // Das Zeichen eines Buchs, an einer Stelle für alle Listen (WIKI-88): das Symbol, das das Buch selbst mitbringt;
  // ohne eins, oder wenn es nicht lädt, das Zeichen seiner Art. So unterscheiden sich Bücher derselben Art auf einen Blick.
  import { ART_SYMBOL } from "../lib/arten";
  import type { Buch } from "../lib/typen";

  let { buch }: { buch: Pick<Buch, "art" | "symbol"> } = $props();
  let kaputt = $state(false);
</script>

{#if buch.symbol && !kaputt}
  <img class="buchzeichen" src={buch.symbol} alt="" loading="lazy" onerror={() => (kaputt = true)} />
{:else}
  <i class="fa-solid {ART_SYMBOL[buch.art]}"></i>
{/if}
