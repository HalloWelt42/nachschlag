<script lang="ts">
  // Eine Frage als Karte (Frage und Antwort): Stimmen, Antworten (grün, wenn eine akzeptiert ist), Titel, Auszug,
  // Schlagwörter und wann gefragt. Eine Stelle für die Fragenliste eines Buchs und das Register (WIKI-39); im Register
  // über mehrere Bücher sagt die Buchmarke, woher die Frage kommt.
  import { zahl } from "../lib/bibliothek.svelte";
  import type { Fragekarte } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Buchmarke from "./Buchmarke.svelte";

  let { buch, frage, mitBuch = false }: { buch: string; frage: Fragekarte; mitBuch?: boolean } = $props();
</script>

<a class="fragekarte" href={"/" + lesenZiel(buch, frage.pfad)} onclick={(e) => { e.preventDefault(); lesen(buch, frage.pfad); }}>
  <span class="fk-zahlen">
    <span class="fk-stimmen"><b>{zahl(frage.stimmen)}</b>Stimmen</span>
    <span class="fk-antworten" class:akzeptiert={frage.akzeptiert}><b>{frage.antworten}</b>{frage.antworten === 1 ? "Antwort" : "Antworten"}</span>
  </span>
  <span class="fk-text">
    <span class="t">{frage.titel}</span>
    {#if frage.auszug}<span class="u">{frage.auszug}</span>{/if}
    <span class="fk-fuss">
      <span class="schlagwoerter">{#each frage.schlagwoerter as s (s)}<span>{s}</span>{/each}</span>
      {#if mitBuch}<Buchmarke kennung={buch} />{/if}
      {#if frage.gefragt}<span class="fk-wann">gefragt {frage.gefragt}</span>{/if}
    </span>
  </span>
</a>
