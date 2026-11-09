<script lang="ts">
  // Kategorien (WIKI-74): die Bücher der Bibliothek nach Art (Nachschlagewerk, Dokumentation, Frage und Antwort,
  // Anleitungen ...). Oben die Arten mit Zahl der Bücher als Wahl, darunter die Bücher der gewählten Art (ohne Wahl
  // alle, nach Art gruppiert). Die Wahl steht im Pfad (/kategorien/<art>). Archivierte Bücher stehen nicht hier.
  import { gehe, navigation } from "appkern-oberflaeche";
  import { onMount } from "svelte";
  import { ART_NAME, ART_SYMBOL } from "../lib/arten";
  import { bibliothek, bibliothekLaden, zahl } from "../lib/bibliothek.svelte";
  import type { Art, Buch } from "../lib/typen";
  import Buchkachel from "../teile/Buchkachel.svelte";
  import Buendelebene from "../teile/Buendelebene.svelte";
  import { ordnen } from "../lib/buendel";

  onMount(() => void bibliothekLaden());

  const aktive = $derived(bibliothek.buecher.filter((b) => !b.archiv));
  /** Je Art ihre Bücher, nur Arten mit Büchern, in der Reihenfolge der Namen */
  const arten = $derived.by(() => {
    const je = new Map<Art, Buch[]>();
    for (const b of aktive) je.set(b.art, [...(je.get(b.art) ?? []), b]);
    return [...je.entries()].sort((x, y) => ART_NAME[x[0]].localeCompare(ART_NAME[y[0]], "de"));
  });
  const gewaehlt = $derived((navigation.teile[0] ?? "") as Art | "");
  const sichtbar = $derived(gewaehlt ? arten.filter(([a]) => a === gewaehlt) : arten);

  $effect(() => {
    navigation.titel = gewaehlt ? ART_NAME[gewaehlt] ?? "Kategorien" : "Kategorien";
  });
</script>

<div class="inhalt-stufe">
  <div class="rollfeld">
    <div class="kat-seite">
      <div class="kat-wahl" role="tablist" aria-label="Art der Bücher">
        <button role="tab" class="chip wahl" class:an={!gewaehlt} aria-selected={!gewaehlt} onclick={() => gehe("kategorien")}>
          <i class="fa-solid fa-shapes"></i>Alle<span class="kat-zahl">{zahl(aktive.length)}</span></button>
        {#each arten as [art, buecher] (art)}
          <button role="tab" class="chip wahl" class:an={gewaehlt === art} aria-selected={gewaehlt === art} onclick={() => gehe(`kategorien/${art}`)}>
            <i class="fa-solid {ART_SYMBOL[art]}"></i>{ART_NAME[art]}<span class="kat-zahl">{zahl(buecher.length)}</span></button>
        {/each}
      </div>
      {#if bibliothek.geladen && !aktive.length}
        <p class="leer-hinweis">Noch keine Bücher in der Bibliothek. Neue gibt es im Katalog.</p>
      {/if}
      {#each sichtbar as [art, buecher] (art)}
        <section class="kat-gruppe">
          {#if !gewaehlt}<h2><i class="fa-solid {ART_SYMBOL[art]}"></i>{ART_NAME[art]}<span class="kat-zahl">{zahl(buecher.length)}</span></h2>{/if}
          <div class="buecher">{#each ordnen(buecher) as e (e.art === "buch" ? e.buch.kennung : e.kennung)}
            {#if e.art === "buch"}<Buchkachel buch={e.buch} />{:else}<Buendelebene titel={e.titel} gesamt={e.gesamt} themen={e.themen} />{/if}
          {/each}</div>
        </section>
      {/each}
    </div>
  </div>
</div>
