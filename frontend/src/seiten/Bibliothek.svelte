<script lang="ts">
  // Bibliothek (WIKI-57, Entwürfe mockups/bibliothek.html, katalog.html, fassungen.html): drei Reiter. Meine Bücher zeigt
  // jede Quelle mit Darstellung (eigene Ansicht oder, wo sie fehlt, Originalansicht) und Abo; Katalog das Verzeichnis der
  // Bücher in den gewählten Sprachen mit allem, was neu ist; Fassungen und Laden die Abos mit vorige, aktiv, neu, den Platz
  // und die Durchsicht. Wege: /bibliothek, /bibliothek/katalog, /bibliothek/laden. Fortschritt steht nur bei den Aufträgen.
  import { gehe, geraet, navigation } from "appkern-oberflaeche";
  import { onMount } from "svelte";
  import { bibliothek, bibliothekLaden } from "../lib/bibliothek.svelte";
  import { lader, laderLaden } from "../lib/buecherlader.svelte";
  import BibliothekKatalog from "../teile/BibliothekKatalog.svelte";
  import BibliothekLaden from "../teile/BibliothekLaden.svelte";
  import BibliothekMeine from "../teile/BibliothekMeine.svelte";

  onMount(() => {
    void bibliothekLaden(true);
    void laderLaden(true);
  });

  const reiter = $derived(navigation.teile[0] === "katalog" ? "katalog" : navigation.teile[0] === "laden" ? "laden" : "meine");
  const ladend = $derived(lader.stand?.abos.some((a) => a.zustand === "laedt") ?? false);
  const wartend = $derived(lader.stand?.abos.filter((a) => a.zustand === "wartet_auf_umschalten").length ?? 0);

  $effect(() => {
    navigation.titel = reiter === "katalog" ? "Katalog" : reiter === "laden" ? "Fassungen und Laden" : "Bibliothek";
  });
</script>

<div class="inhalt-stufe bib-seite" data-schrift="klein">
  <div class="seiten-kopf">
    {#if !geraet.mobil}<h1>Bibliothek</h1>{/if}
  </div>
  <div class="reiterleiste bib-reiter" role="tablist">
    <button role="tab" aria-selected={reiter === "meine"} class:aktiv={reiter === "meine"} onclick={() => gehe("bibliothek")}>
      Meine Bücher <span class="zahl">{bibliothek.buecher.length}</span></button>
    <button role="tab" aria-selected={reiter === "katalog"} class:aktiv={reiter === "katalog"} onclick={() => gehe("bibliothek/katalog")}>
      Katalog{#if lader.stand?.neu_ungesehen}<span class="neu-fassung" title="neu seit der letzten Durchsicht">{lader.stand.neu_ungesehen} neu</span>{/if}</button>
    <button role="tab" aria-selected={reiter === "laden"} class:aktiv={reiter === "laden"} onclick={() => gehe("bibliothek/laden")}>
      Fassungen und Laden{#if ladend}<span class="reiter-punkt" title="lädt"></span>{/if}{#if wartend}<span class="neu-fassung"
        title="neue Fassungen warten aufs Umschalten">{wartend}</span>{/if}</button>
  </div>
  <div class="rollfeld">
    {#if lader.meldung}<div class="fehlertext">{lader.meldung}</div>{/if}
    {#if reiter === "katalog"}
      <BibliothekKatalog />
    {:else if reiter === "laden"}
      <BibliothekLaden />
    {:else}
      <BibliothekMeine />
    {/if}
  </div>
</div>
