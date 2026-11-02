<script lang="ts">
  // Notiz im Lesen (Entwurf mockups/telefon-themen.html, Blatt von unten): am Telefon ein Blatt über die ganze Breite,
  // am Rechner schwebt es unten rechts über dem Text, damit die Stelle sichtbar bleibt. Fertig, Escape und ein Tippen
  // daneben schließen und speichern, was aussteht (WIKI-37); ein Tippen auf eine Markierung wechselt zu deren Notiz.
  import { onMount, tick } from "svelte";
  import type { Notiz, NotizNeu } from "../lib/meins.svelte";
  import NotizBearbeiten from "./NotizBearbeiten.svelte";

  let { notiz = null, entwurf = null, schreiben = false, zurStelle, onzu }: {
    notiz?: Notiz | null;
    entwurf?: NotizNeu | null;
    schreiben?: boolean;          // gleich ins Feld (neu angelegt); zum Ansehen bleibt die Tastatur zu
    zurStelle?: () => void;
    onzu: () => void;
  } = $props();

  let editor = $state<NotizBearbeiten>();
  let blattEl = $state<HTMLElement>();
  // Erst nach dem Tippen, das das Blatt geöffnet hat: dasselbe Ereignis soll es nicht gleich wieder schließen
  let bereit = false;
  onMount(() => {
    const t = setTimeout(() => (bereit = true));
    return () => clearTimeout(t);
  });

  /** Der Weg des Klicks zählt, wie er beim Tippen war: ein Knopf im Blatt, der sich beim Klick selbst ersetzt (Löschen
   *  wird zur Rückfrage), hängt danach nicht mehr im Blatt und gälte sonst als daneben. */
  function daneben(e: MouseEvent) {
    const weg = e.composedPath();
    const innen = (el: EventTarget) => el === blattEl || (el instanceof Element && el.matches(".auswahl-leiste, mark.notiz, .notiz-marke"));
    if (!bereit || weg.some(innen)) return;
    void fertig();
  }
  const anStelle = $derived(!!(notiz?.zitat ?? entwurf?.zitat));

  async function fertig() {
    await editor?.jetztSpeichern();
    onzu();
  }

  // Neu angelegt: gleich schreiben
  $effect(() => {
    if (entwurf || schreiben) void tick().then(() => editor?.fokus());
  });
</script>

<!-- Escape schließt das Blatt, außer die Bildansicht darüber hat es schon für sich genommen -->
<svelte:window onkeydown={(e) => e.key === "Escape" && !e.defaultPrevented && fertig()} />
<svelte:document onclick={daneben} />
<div class="notizblatt" bind:this={blattEl} role="dialog" aria-label={anStelle ? "Notiz zur Stelle" : "Notiz zum Artikel"}>
  <div class="blatt-griff"></div>
  <div class="blatt-kopf"><b>{anStelle ? "Notiz zur Stelle" : "Notiz zum Artikel"}</b><button class="knopf primaer" onclick={fertig}>Fertig</button></div>
  <NotizBearbeiten bind:this={editor} {notiz} {entwurf} {zurStelle} onweg={onzu} />
</div>
