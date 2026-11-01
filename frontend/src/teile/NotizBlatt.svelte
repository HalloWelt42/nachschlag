<script lang="ts">
  // Notiz im Lesen (Entwurf mockups/telefon-themen.html, Blatt von unten): am Telefon ein Blatt über die ganze Breite,
  // am Rechner schwebt es unten rechts über dem Text, damit die Stelle sichtbar bleibt. Fertig speichert, was aussteht.
  import { tick } from "svelte";
  import type { Notiz, NotizNeu } from "../lib/meins.svelte";
  import NotizBearbeiten from "./NotizBearbeiten.svelte";

  let { notiz = null, entwurf = null, zurStelle, onzu }: {
    notiz?: Notiz | null;
    entwurf?: NotizNeu | null;
    zurStelle?: () => void;
    onzu: () => void;
  } = $props();

  let editor = $state<NotizBearbeiten>();
  const anStelle = $derived(!!(notiz?.zitat ?? entwurf?.zitat));

  async function fertig() {
    await editor?.jetztSpeichern();
    onzu();
  }

  // Neu angelegt: gleich schreiben
  $effect(() => {
    if (entwurf || (notiz && !notiz.text)) void tick().then(() => editor?.fokus());
  });
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && fertig()} />
<div class="notizblatt" role="dialog" aria-label={anStelle ? "Notiz zur Stelle" : "Notiz zum Artikel"}>
  <div class="blatt-griff"></div>
  <div class="blatt-kopf"><b>{anStelle ? "Notiz zur Stelle" : "Notiz zum Artikel"}</b><button class="knopf primaer" onclick={fertig}>Fertig</button></div>
  <NotizBearbeiten bind:this={editor} {notiz} {entwurf} {zurStelle} onweg={onzu} />
</div>
