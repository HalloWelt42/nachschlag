<script lang="ts">
  // Ein Blatt im Kleinen (Entwurf export.html, Wahl der Vorlage): zeigt, wie eine Seite nach der Vorlage aussieht,
  // aus ihrem Aufbau gelesen (Kasten für Auf einen Blick und eigene Kästen, Bild nach der Gestaltung, Fragen, zwei
  // Spalten von A bis Z). Reine Darstellung.
  import { teileVon, type Vorlage } from "../lib/buecher.svelte";

  let { vorlage }: { vorlage: Vorlage } = $props();
  const teile = $derived(teileVon(vorlage));
  const bild = $derived(vorlage.gestaltung.bilder !== "ohne");
</script>

<div class="exp-blatt" aria-hidden="true">
  <i class="h"></i>
  {#if vorlage.aufbau.gliederung === "abc"}
    <div class="spalten"><span><i></i><i></i><i class="k"></i><i></i></span><span><i></i><i class="k"></i><i></i><i></i></span></div>
    <i class="h zweite"></i>
    <div class="spalten"><span><i></i><i class="k"></i></span><span><i></i><i></i></span></div>
  {:else}
    {#if teile.has("blick")}<div class="kasten"><i></i><i class="k"></i></div>{/if}
    {#if bild && vorlage.gestaltung.bilder === "eins_gross"}<div class="bild"></div>{/if}
    <i></i><i class="k"></i><i></i>
    {#if bild && vorlage.gestaltung.bilder === "im_text"}<div class="bild"></div>{/if}
    {#if teile.has("kasten")}<div class="kasten"><i></i><i class="kurz"></i></div>{/if}
    <i class="kurz"></i>
    {#if teile.has("fragen")}<i class="frage"></i><i class="frage"></i>{/if}
  {/if}
</div>
